"""The team Coolify panel and the course-wide Security page.

Everything here talks to Coolify with the team's own API token (Coolify tokens
only see their own team), except server jobs, which also log in to the team's
server over SSH with the key Coolify uses for it (see ssh.py).
"""

import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.http import ExternalServiceError
from app.core.naming import best_match
from app.credentials.service import get_system_credential, get_user_credential
from app.modules.coolify import ssh
from app.modules.coolify.client import CoolifyClient, ResourceKind, dashboard_url
from app.modules.coolify.models import ServerJob
from app.modules.coolify.schemas import (
    ActionResult,
    AppSummary,
    AutoConnectResult,
    CourseSummary,
    Deployment,
    DeploymentDetail,
    EnvVar,
    EnvWrite,
    Finding,
    JobRead,
    LogLine,
    PanelOverview,
    ResourceFindings,
    ResourceInfo,
    SecurityInfo,
    ServerInfo,
    ServerSummary,
    TeamSecurity,
    TeamSummary,
)
from app.teams.credentials import get_team_credential
from app.teams.credentials import save as save_team_credential
from app.teams.models import Team
from app.users.models import User

logger = logging.getLogger(__name__)

TOKEN_KEY = "coolify_team_token"
# A job still "running" after this long was cut off (e.g. the API restarted).
JOB_STALE_AFTER = timedelta(hours=3)
PATCH_KINDS = ("patch_check", "patch_security", "patch_all")
KIND_FROM_TYPE: dict[str, ResourceKind] = {
    "application": "applications",
    "database": "databases",
    "service": "services",
}


class CoolifyError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def client_for(db: Session, team: Team) -> CoolifyClient:
    dashboard = get_system_credential(db, "coolify_url")
    if dashboard is None:
        raise CoolifyError(
            "An administrator needs to add the Coolify dashboard address in System settings."
        )
    token = get_team_credential(db, team.id, TOKEN_KEY)
    if token is None:
        raise CoolifyError(f"Add {team.name}'s Coolify API token first.")
    return CoolifyClient(dashboard, token)


# --- converting Coolify's data ------------------------------------------------


def _security(raw: Any) -> SecurityInfo | None:
    if not isinstance(raw, dict):
        return None
    fields = SecurityInfo.model_fields
    return SecurityInfo.model_validate(
        {k: v for k, v in raw.items() if k in fields and v is not None}
    )


def _environment_names(client: CoolifyClient) -> dict[Any, tuple[str, str]]:
    """environment id (and uuid) -> (project name, environment name)."""
    names: dict[Any, tuple[str, str]] = {}
    for project in client.projects():
        if not project.get("uuid"):
            continue
        for env in client.environments(str(project["uuid"])):
            label = (str(project.get("name", "")), str(env.get("name", "")))
            for key in ("id", "uuid"):
                if env.get(key) is not None:
                    names[env[key]] = label
    return names


def _resource(
    kind: ResourceKind,
    raw: dict[str, Any],
    envs: dict[Any, tuple[str, str]],
    security: SecurityInfo | None,
) -> ResourceInfo:
    project, environment = envs.get(raw.get("environment_id"), ("", ""))
    return ResourceInfo(
        kind=kind,
        uuid=str(raw.get("uuid", "")),
        name=str(raw.get("name") or raw.get("uuid", "")),
        status=str(raw.get("status") or ""),
        project=project,
        environment=environment,
        fqdn=raw.get("fqdn") or None,
        git_repository=raw.get("git_repository") or None,
        git_branch=raw.get("git_branch") or None,
        security=security,
    )


def job_read(db: Session, job: ServerJob) -> JobRead:
    status_ = job.status
    error = job.error
    if status_ == "running" and job.created_at < datetime.now(UTC) - JOB_STALE_AFTER:
        status_, error = "failed", "This job was interrupted (the workbench restarted)."
    started_by = db.get(User, job.started_by_id) if job.started_by_id else None
    try:
        result = json.loads(job.result) if job.result else None
    except ValueError:
        result = None
    return JobRead(
        id=job.id,
        kind=job.kind,
        server_uuid=job.server_uuid,
        server_name=job.server_name,
        status=status_,
        log=job.log,
        result=result if isinstance(result, dict) else None,
        error=error,
        started_by=(started_by.full_name or started_by.email) if started_by else None,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


def _server_infos(
    db: Session, team: Team, client: CoolifyClient, raw_servers: list[dict[str, Any]]
) -> list[ServerInfo]:
    jobs = list(
        db.scalars(
            select(ServerJob).where(ServerJob.team_id == team.id).order_by(ServerJob.id.desc())
        )
    )
    infos = []
    for raw in raw_servers:
        uuid = str(raw.get("uuid", ""))
        raw_settings = raw.get("settings")
        settings: dict[str, Any] = raw_settings if isinstance(raw_settings, dict) else {}
        mine = [j for j in jobs if j.server_uuid == uuid]
        patch = next(
            (j for j in mine if j.kind == "patch_check" or (j.kind in PATCH_KINDS and j.result)),
            None,
        )
        scan = next((j for j in mine if j.kind == "image_scan"), None)
        running = next((j for j in mine if job_read(db, j).status == "running"), None)
        try:
            scanning = client.image_scanning(uuid).get("is_image_scan_enabled")
        except ExternalServiceError:
            scanning = None  # older Coolify, or the token's owner isn't a team admin
        infos.append(
            ServerInfo(
                uuid=uuid,
                name=str(raw.get("name", "")),
                ip=str(raw.get("ip", "")),
                reachable=settings.get("is_reachable"),
                usable=settings.get("is_usable"),
                image_scanning=scanning if isinstance(scanning, bool) else None,
                last_patch_check=job_read(db, patch) if patch else None,
                last_image_scan=job_read(db, scan) if scan else None,
                running_job=job_read(db, running) if running else None,
            )
        )
    return infos


# --- the team panel -----------------------------------------------------------


def overview(db: Session, team: Team, user: User) -> PanelOverview:
    dashboard = get_system_credential(db, "coolify_url")
    token = get_team_credential(db, team.id, TOKEN_KEY)
    result = PanelOverview(
        team_name=team.name,
        token_set=token is not None,
        auto_connect=token is None and can_auto_connect(db, user),
        dashboard_url=dashboard_url(dashboard) if dashboard else None,
    )
    if dashboard is None:
        result.error = (
            "An administrator needs to add the Coolify dashboard address in System settings."
        )
        return result
    if token is None:
        return result
    client = CoolifyClient(dashboard, token)
    try:
        result.coolify_team = str(client.team().get("name") or "") or None
        raw_servers = client.servers()
        kinds: tuple[ResourceKind, ...] = ("applications", "databases", "services")
        raw = {kind: client.resources(kind) for kind in kinds}
        envs = _environment_names(client)
    except ExternalServiceError as err:
        result.error = str(err)
        return result

    security: dict[str, SecurityInfo | None] = {}
    try:
        for item in client.vulnerabilities():
            security[str(item.get("uuid"))] = _security(item.get("security"))
    except ExternalServiceError as err:
        result.security_error = str(err)

    result.servers = _server_infos(db, team, client, raw_servers)
    result.resources = [
        _resource(kind, item, envs, security.get(str(item.get("uuid"))))
        for kind, items in raw.items()
        for item in items
    ]
    return result


def resource_action(
    db: Session, team: Team, kind: ResourceKind, uuid: str, action: str
) -> ActionResult:
    client = client_for(db, team)
    if action == "redeploy":
        # Applications rebuild from scratch (newer base images); services pull the
        # latest images; databases restart.
        if kind == "applications":
            data = client.control(kind, uuid, "start", force=True)
        else:
            data = client.control(kind, uuid, "restart", latest=kind == "services")
    else:
        data = client.control(kind, uuid, action)
    message = str(data.get("message") or f"{action.capitalize()} requested.")
    deployment = data.get("deployment_uuid")
    return ActionResult(message=message, deployment_uuid=str(deployment) if deployment else None)


def logs(db: Session, team: Team, uuid: str, lines: int) -> str:
    return client_for(db, team).logs(uuid, lines=lines)


def _deployment(raw: dict[str, Any]) -> Deployment:
    return Deployment(
        uuid=str(raw.get("deployment_uuid") or raw.get("uuid") or ""),
        status=str(raw.get("status") or ""),
        commit=raw.get("commit"),
        commit_message=raw.get("commit_message"),
        created_at=raw.get("created_at"),
        updated_at=raw.get("updated_at"),
    )


def deployments(db: Session, team: Team, app_uuid: str) -> list[Deployment]:
    return [_deployment(d) for d in client_for(db, team).deployments(app_uuid)]


def parse_deployment_log(raw: Any) -> list[LogLine]:
    """Coolify stores a deployment's log as a JSON list of {output, type, hidden}."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return [LogLine(output=line) for line in raw.splitlines()]
    if not isinstance(raw, list):
        return []
    return [
        LogLine(output=str(item.get("output", "")), type=str(item.get("type") or "stdout"))
        for item in raw
        if isinstance(item, dict) and not item.get("hidden")
    ]


def deployment(db: Session, team: Team, uuid: str) -> DeploymentDetail:
    raw = client_for(db, team).deployment(uuid)
    detail = DeploymentDetail(**_deployment(raw).model_dump())
    detail.log = parse_deployment_log(raw.get("logs"))
    return detail


def cancel_deployment(db: Session, team: Team, uuid: str) -> ActionResult:
    data = client_for(db, team).cancel_deployment(uuid)
    return ActionResult(message=str(data.get("message") or "Deployment cancelled."))


def envs(db: Session, team: Team, app_uuid: str) -> list[EnvVar]:
    out = []
    for raw in client_for(db, team).envs(app_uuid):
        locked = bool(raw.get("is_shown_once"))
        value = raw.get("value")
        out.append(
            EnvVar(
                uuid=str(raw.get("uuid", "")),
                key=str(raw.get("key", "")),
                value=None if locked or value is None else str(value),
                is_buildtime=bool(raw.get("is_buildtime")),
                is_preview=bool(raw.get("is_preview")),
                is_literal=bool(raw.get("is_literal")),
                is_multiline=bool(raw.get("is_multiline")),
                is_shown_once=locked,
            )
        )
    return out


def save_env(db: Session, team: Team, app_uuid: str, body: EnvWrite, *, create: bool) -> None:
    client = client_for(db, team)
    data = body.model_dump()
    if create:
        client.create_env(app_uuid, data)
    else:
        client.update_env(app_uuid, data)


def delete_env(db: Session, team: Team, app_uuid: str, env_uuid: str) -> None:
    client_for(db, team).delete_env(app_uuid, env_uuid)


def findings(db: Session, team: Team, kind: ResourceKind, uuid: str) -> ResourceFindings:
    raw = client_for(db, team).resource_vulnerabilities(kind, uuid)
    images = [str(i.get("image_ref", "")) for i in raw.get("images") or [] if isinstance(i, dict)]
    items = []
    for f in raw.get("findings") or []:
        if not isinstance(f, dict):
            continue
        items.append(
            Finding(
                id=str(f.get("display_id") or f.get("id") or ""),
                title=str(f.get("title") or ""),
                severity=str(f.get("severity") or "unknown"),
                package=str(f.get("package") or ""),
                version=str(f.get("version") or ""),
                fixed_in=str(f.get("fixed_in") or ""),
                state=str(f.get("state") or ""),
                kev=bool(f.get("kev")),
                url=str(f.get("advisory_url") or ""),
                image=str(f.get("image_ref") or ""),
            )
        )
    total = (raw.get("pagination") or {}).get("total")
    return ResourceFindings(
        security=_security(raw.get("security")),
        images=images,
        findings=items,
        total=int(total) if isinstance(total, int) else len(items),
    )


def set_image_scanning(db: Session, team: Team, server_uuid: str, enabled: bool) -> None:
    client_for(db, team).set_image_scanning(server_uuid, enabled)


def docker_cleanup(db: Session, team: Team, server_uuid: str) -> ActionResult:
    data = client_for(db, team).docker_cleanup(server_uuid)
    return ActionResult(message=str(data.get("message") or "Docker cleanup started."))


# --- the course-wide Security page ----------------------------------------------


def course_security(db: Session, teams: list[Team], user: User) -> list[TeamSecurity]:
    """Every team's image-scan results and server patch status, one row per team."""
    dashboard = get_system_credential(db, "coolify_url")
    auto = can_auto_connect(db, user)
    rows = []
    for team in teams:
        token = get_team_credential(db, team.id, TOKEN_KEY)
        row = TeamSecurity(
            team_id=team.id,
            team_name=team.name,
            token_set=token is not None,
            auto_connect=token is None and auto,
        )
        rows.append(row)
        if token is None or dashboard is None:
            continue
        client = CoolifyClient(dashboard, token)
        try:
            for item in client.vulnerabilities():
                kind = KIND_FROM_TYPE.get(str(item.get("type")), "applications")
                row.resources.append(_resource(kind, item, {}, _security(item.get("security"))))
            row.servers = _server_infos(db, team, client, client.servers())
        except ExternalServiceError as err:
            row.error = str(err)
    return rows


# --- server jobs (SSH) ----------------------------------------------------------


def start_job(db: Session, team: Team, server_uuid: str, kind: str, user: User) -> ServerJob:
    client = client_for(db, team)
    since = datetime.now(UTC) - JOB_STALE_AFTER
    busy = db.scalar(
        select(ServerJob).where(
            ServerJob.server_uuid == server_uuid,
            ServerJob.status == "running",
            ServerJob.created_at > since,
        )
    )
    if busy is not None:
        raise CoolifyError(
            "Something is already running on this server. Wait for it to finish.",
            status.HTTP_409_CONFLICT,
        )
    try:
        server = client.server(server_uuid)
    except ExternalServiceError as err:
        raise CoolifyError(str(err), status.HTTP_502_BAD_GATEWAY) from None
    job = ServerJob(
        team_id=team.id,
        server_uuid=server_uuid,
        server_name=str(server.get("name", "")),
        kind=kind,
        started_by_id=user.id,
    )
    db.add(job)
    db.commit()
    return job


def run_job(job_id: int) -> None:
    """Runs in the background after the request that started the job has returned."""
    with SessionLocal() as db:
        job = db.get(ServerJob, job_id)
        team = db.get(Team, job.team_id) if job else None
        if job is None or team is None:
            return
        lines: list[str] = []

        def log(message: str) -> None:
            lines.append(message)
            job.log = "\n".join(lines)
            db.commit()

        try:
            client = client_for(db, team)
            server = client.server(job.server_uuid)
            target = ssh.SshTarget(
                host=str(server.get("ip", "")),
                port=int(server.get("port") or 22),
                user=str(server.get("user") or "root"),
                private_keys=client.private_keys(),
            )
            log(f"Connecting to {target.user}@{target.host} with Coolify's SSH key...")
            shell = ssh.connect(target)
            try:
                if job.kind == "patch_check":
                    result: dict[str, Any] = ssh.check_patches(shell, log).summary()
                elif job.kind in ("patch_security", "patch_all"):
                    after = ssh.apply_patches(
                        shell, log, security_only=job.kind == "patch_security"
                    )
                    result = after.summary()
                else:
                    result = ssh.scan_images(shell, log)
            finally:
                shell.close()
            job.result = json.dumps(result)
            job.status = "succeeded"
            log("Done.")
        except (ExternalServiceError, CoolifyError) as err:
            job.status, job.error = "failed", str(err)
        except Exception as err:
            logger.exception("Server job %s failed", job_id)
            job.status, job.error = "failed", f"Unexpected error: {err}"
        job.finished_at = datetime.now(UTC)
        db.commit()


def get_job(db: Session, team: Team, job_id: int) -> JobRead:
    job = db.get(ServerJob, job_id)
    if job is None or job.team_id != team.id:
        raise CoolifyError("Job not found", status.HTTP_404_NOT_FOUND)
    return job_read(db, job)


# --- connecting teams automatically -----------------------------------------------
#
# Coolify's API can't create API tokens, and each token only sees its own team. So,
# with the user's admin token (from their main Coolify team, the one that owns the
# Coolify server), the workbench reads Coolify's SSH key for its own server, logs in
# to the Coolify server, and runs Coolify's createToken() for the team's Coolify team.

ADMIN_TOKEN_KEY = "coolify_token"
# After the Coolify server refuses a login, wait this long before trying the same keys again.
SSH_RETRY_AFTER_SECONDS = 30 * 60
# (host, hash of the admin token) -> (when, message) of the last refused SSH login.
_ssh_refusals: dict[tuple[str, str], tuple[float, str]] = {}
WORKBENCH_TOKEN_NAME = "course-workbench"
TEAM_TOKEN_ABILITIES = ["read", "read:sensitive", "write", "deploy"]
_IP = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")


def can_auto_connect(db: Session, user: User) -> bool:
    return (
        get_system_credential(db, "coolify_url") is not None
        and get_user_credential(db, user, ADMIN_TOKEN_KEY) is not None
    )


def _droplet_ip(team: Team) -> str | None:
    """The team server's IP from its Coolify link ("BeforeDawn · 167.99.6.42")."""
    link = next((link for link in team.links if link.service_id == "coolify"), None)
    m = _IP.search(link.label) if link else None
    return m.group(1) if m else None


def match_coolify_team(team: Team, coolify_teams: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The Coolify team that owns the team's droplet, or else the one named like the team."""
    ip = _droplet_ip(team)
    if ip:
        by_ip = [t for t in coolify_teams if ip in (t.get("ips") or [])]
        if len(by_ip) == 1:
            return by_ip[0]
    # Never the root team (id 0): that's the course's own, not a student team.
    candidates = [t for t in coolify_teams if t.get("id") != 0]
    return best_match(team.name, candidates, names=lambda t: [str(t.get("name", ""))])


def connect_team(db: Session, team: Team, user: User) -> AutoConnectResult:
    dashboard = get_system_credential(db, "coolify_url")
    admin_token = get_user_credential(db, user, ADMIN_TOKEN_KEY)
    if dashboard is None:
        raise CoolifyError(
            "An administrator needs to add the Coolify dashboard address in System settings."
        )
    if admin_token is None:
        raise CoolifyError(
            "Add your Coolify admin token in System settings to connect teams automatically."
        )
    admin = CoolifyClient(dashboard, admin_token)
    try:
        keys = admin.private_keys()
    except ExternalServiceError as err:
        raise CoolifyError(str(err), status.HTTP_502_BAD_GATEWAY) from None
    if not keys:
        raise CoolifyError(
            "Coolify didn't share its SSH keys with your admin token. Use a token from your "
            "main (root) Coolify team with the root or read:sensitive permission.",
            status.HTTP_502_BAD_GATEWAY,
        )
    host = urlsplit(admin.base).hostname or ""
    # Don't keep knocking with keys the server already refused: repeated failed logins
    # get this machine's address blocked by the server's brute-force protection.
    attempt = (host, hashlib.sha256(admin_token.encode()).hexdigest())
    refused = _ssh_refusals.get(attempt)
    if refused and time.monotonic() - refused[0] < SSH_RETRY_AFTER_SECONDS:
        raise CoolifyError(
            f"{refused[1]} (Not retrying for a while, so the Coolify server doesn't block this "
            "address. Replacing your Coolify admin token retries right away.)",
            status.HTTP_502_BAD_GATEWAY,
        )
    try:
        shell = ssh.connect(ssh.SshTarget(host=host, port=22, user="root", private_keys=keys))
    except ExternalServiceError as err:
        message = (
            f"{err} Your admin token must be from the Coolify team that owns the Coolify "
            "server (the main team), so its SSH key opens that server."
        )
        if str(err).startswith("Couldn't log in"):  # refused keys, not a network problem
            _ssh_refusals[attempt] = (time.monotonic(), message)
        raise CoolifyError(message, status.HTTP_502_BAD_GATEWAY) from None
    _ssh_refusals.pop(attempt, None)
    try:
        container = ssh.coolify_container(shell)
        teams = ssh.coolify_teams(shell, container)
        match = match_coolify_team(team, teams)
        if match is None:
            names = ", ".join(str(t.get("name")) for t in teams if t.get("id") != 0)
            raise CoolifyError(
                f"Couldn't tell which Coolify team is {team.name}'s. Coolify's teams: {names}. "
                "Rename one to match, or paste a token by hand.",
                status.HTTP_404_NOT_FOUND,
            )
        admins = match.get("admins") or []
        if not admins:
            raise CoolifyError(
                f"The Coolify team {match.get('name')} has no owner or admin to own the token.",
                status.HTTP_409_CONFLICT,
            )
        owner = next((a for a in admins if a.get("id") == 0), admins[0])
        token = ssh.create_team_token(
            shell,
            container,
            team_id=int(match["id"]),
            user_id=int(owner["id"]),
            name=WORKBENCH_TOKEN_NAME,
            abilities=TEAM_TOKEN_ABILITIES,
        )
    except ExternalServiceError as err:
        raise CoolifyError(str(err), status.HTTP_502_BAD_GATEWAY) from None
    finally:
        shell.close()
    save_team_credential(db, team_id=team.id, key=TOKEN_KEY, value=token, updated_by=user)
    name = str(match.get("name"))
    return AutoConnectResult(
        coolify_team=name,
        message=f"Connected {team.name} to its Coolify team, {name}.",
    )


def deployed_repos(db: Session, team: Team) -> dict[str, list[str]]:
    """GitHub repos the team's Coolify apps deploy from: {"owner/name": [branches]}.

    Empty if the team isn't connected to Coolify or Coolify can't be read.
    """
    dashboard = get_system_credential(db, "coolify_url")
    token = get_team_credential(db, team.id, TOKEN_KEY)
    if dashboard is None or token is None:
        return {}
    try:
        apps = CoolifyClient(dashboard, token).resources("applications")
    except ExternalServiceError:
        return {}
    repos: dict[str, list[str]] = {}
    for app in apps:
        repo = github_repo(app.get("git_repository"))
        if not repo:
            continue
        branches = repos.setdefault(repo, [])
        branch = str(app.get("git_branch") or "")
        if branch and branch not in branches:
            branches.append(branch)
    return repos


_GITHUB_REPO = re.compile(
    r"^(?:https?://github\.com/|git@github\.com:)?([\w.-]+/[\w.-]+?)(?:\.git)?/?$"
)


def github_repo(git_repository: Any) -> str | None:
    """owner/name from what Coolify stores ("org/x", "https://github.com/org/x.git", ...)."""
    m = _GITHUB_REPO.match(str(git_repository or "").strip())
    return m.group(1) if m else None


# --- the course summary -----------------------------------------------------------
#
# One cheap read of every connected team (apps with status and security, servers),
# for the dashboard's "Needs attention" list and the status line on each team card.
# Teams are read in parallel, and the result is kept for a minute.

SUMMARY_TTL_SECONDS = 60
_summary_cache: dict[str, tuple[float, CourseSummary]] = {}

TeamRead = tuple[
    dict[ResourceKind, list[dict[str, Any]]], list[dict[str, Any]], dict[str, SecurityInfo | None]
]


def _read_team(dashboard: str, token: str) -> TeamRead:
    """Everything the summary needs from one team's Coolify. Runs in a worker thread (no DB)."""
    client = CoolifyClient(dashboard, token)
    kinds: tuple[ResourceKind, ...] = ("applications", "databases", "services")
    raw = {kind: client.resources(kind) for kind in kinds}
    servers = client.servers()
    try:
        security = {
            str(v.get("uuid")): _security(v.get("security")) for v in client.vulnerabilities()
        }
    except ExternalServiceError:
        security = {}
    return raw, servers, security


def _server_summary(db: Session, raw: dict[str, Any], jobs: list[ServerJob]) -> ServerSummary:
    uuid = str(raw.get("uuid", ""))
    mine = [j for j in jobs if j.server_uuid == uuid]
    check = next((j for j in mine if j.kind in PATCH_KINDS and j.status == "succeeded"), None)
    try:
        result = json.loads(check.result) if check and check.result else {}
    except ValueError:
        result = {}
    raw_settings = raw.get("settings")
    settings: dict[str, Any] = raw_settings if isinstance(raw_settings, dict) else {}
    return ServerSummary(
        uuid=uuid,
        name=str(raw.get("name", "")),
        ip=str(raw.get("ip", "")),
        reachable=settings.get("is_reachable"),
        update_count=result.get("update_count"),
        security_count=result.get("security_count"),
        reboot_required=result.get("reboot_required"),
        checked_at=check.finished_at if check else None,
        job_running=any(job_read(db, j).status == "running" for j in mine),
    )


def course_summary(db: Session, teams: list[Team], *, refresh: bool = False) -> CourseSummary:
    dashboard = get_system_credential(db, "coolify_url")
    tokens = {t.id: get_team_credential(db, t.id, TOKEN_KEY) for t in teams}
    cache_key = json.dumps([[t.id, t.name, bool(tokens[t.id])] for t in teams] + [dashboard])
    cached = _summary_cache.get(cache_key)
    if cached and not refresh and time.monotonic() - cached[0] < SUMMARY_TTL_SECONDS:
        return cached[1]

    results: dict[int, TeamRead | ExternalServiceError] = {}
    if dashboard is not None:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                t.id: pool.submit(_read_team, dashboard, token)
                for t in teams
                if (token := tokens[t.id])
            }
            for team_id, future in futures.items():
                try:
                    results[team_id] = future.result()
                except ExternalServiceError as err:
                    results[team_id] = err

    jobs = list(db.scalars(select(ServerJob).order_by(ServerJob.id.desc())))
    summaries = []
    for team in teams:
        row = TeamSummary(team_id=team.id, team_name=team.name, connected=bool(tokens[team.id]))
        summaries.append(row)
        result = results.get(team.id)
        if result is None:
            continue
        if isinstance(result, ExternalServiceError):
            row.error = str(result)
            continue
        raw, raw_servers, security = result
        for kind, items in raw.items():
            for item in items:
                uuid = str(item.get("uuid", ""))
                row.apps.append(
                    AppSummary(
                        kind=kind,
                        uuid=uuid,
                        name=str(item.get("name") or uuid),
                        status=str(item.get("status") or ""),
                        security=security.get(uuid),
                    )
                )
                repo = github_repo(item.get("git_repository")) if kind == "applications" else None
                if repo and repo not in row.repos:
                    row.repos.append(repo)
        team_jobs = [j for j in jobs if j.team_id == team.id]
        row.servers = [_server_summary(db, s, team_jobs) for s in raw_servers]

    summary = CourseSummary(teams=summaries, generated_at=datetime.now(UTC))
    _summary_cache.clear()
    _summary_cache[cache_key] = (time.monotonic(), summary)
    return summary

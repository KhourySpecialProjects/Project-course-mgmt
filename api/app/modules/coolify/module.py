"""Coolify tool module.

The course runs one Coolify dashboard (an administrator sets its address in
System settings). Each student team is its own Team in Coolify, with its own
DigitalOcean droplet added as that team's server.

Two ways in:

- The team card's Coolify button. With your DigitalOcean token, the workbench
  finds the team's droplet (named or tagged after the team) and links Coolify,
  noting which server is theirs (``team_service`` below).
- The team's Coolify panel (``/teams/<id>/coolify`` in the web app), which works
  with the team's own Coolify API token (Coolify tokens only see their own team):
  servers, apps, deploy/restart/stop, logs, deployments, environment variables,
  security scan results, Docker cleanup, and, over SSH with Coolify's key for the
  server, patch checks, patching, and on-demand image scans. The course-wide
  Security page (``GET /security``) puts every team's results side by side.

Endpoints are under /api/tools/coolify; see service.py for what each does.
"""

from typing import Annotated, NoReturn
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.core.http import ExternalServiceError
from app.core.naming import best_match
from app.credentials.service import get_system_credential, get_user_credential
from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules.base import CreatedResource, TeamService, ToolModule, ToolStatus, status_for
from app.modules.coolify import digitalocean, service
from app.modules.coolify.schemas import (
    ActionResult,
    AutoConnectResult,
    Deployment,
    DeploymentDetail,
    EnvVar,
    EnvWrite,
    ImageScanningUpdate,
    JobRead,
    JobStart,
    Logs,
    PanelOverview,
    ResourceAction,
    ResourceFindings,
    ResourceKind,
    TeamSecurity,
)
from app.modules.coolify.service import CoolifyError
from app.teams.models import Team
from app.teams.service import TeamError, get_team, list_teams
from app.users.models import User

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/status", response_model=ToolStatus)
def status_(user: CurrentUser, db: DbSession) -> ToolStatus:
    """Report whether the Coolify integration is ready for the current user."""
    return status_for(module, db, user)


def dashboard_url(saved: str) -> str:
    """Tidy the saved dashboard address: "coolify.example.edu/" -> "https://coolify.example.edu"."""
    url = saved.strip().rstrip("/")
    if not urlsplit(url).scheme:
        url = f"https://{url}"
    return url


def find_team_server(db: Session, user: User, team_name: str) -> CreatedResource | None:
    """The team's droplet, linked to the Coolify dashboard; None if no droplet matches."""
    dashboard = get_system_credential(db, "coolify_url")
    token = get_user_credential(db, user, "digitalocean_token")
    if dashboard is None or token is None:
        raise ExternalServiceError("Coolify isn't set up yet.")
    droplets = digitalocean.list_droplets(token)
    droplet = best_match(team_name, droplets, names=lambda d: [d.name, *d.tags])
    if droplet is None:
        return None
    return CreatedResource(
        url=dashboard_url(dashboard),
        external_id=droplet.id,
        label=f"{droplet.name} · {droplet.ip or 'no IP address yet'}",
        already_existed=True,
    )


# --- the team panel ---------------------------------------------------------------


def _raise(err: CoolifyError | ExternalServiceError | TeamError) -> NoReturn:
    if isinstance(err, ExternalServiceError):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(err))
    raise HTTPException(err.status_code, detail=err.message)


def _team(db: Session, team_id: int) -> Team:
    try:
        return get_team(db, team_id)
    except TeamError as err:
        _raise(err)


Failure = (CoolifyError, ExternalServiceError)


@router.get("/security", response_model=list[TeamSecurity])
def course_security(user: CurrentUser, db: DbSession) -> list[TeamSecurity]:
    """Every team's image-scan results and server patch status."""
    return service.course_security(db, list_teams(db), user)


@router.get("/teams/{team_id}/overview", response_model=PanelOverview)
def overview(team_id: int, user: CurrentUser, db: DbSession) -> PanelOverview:
    return service.overview(db, _team(db, team_id), user)


@router.post("/teams/{team_id}/connect", response_model=AutoConnectResult)
def connect_team(team_id: int, user: CurrentUser, db: DbSession) -> AutoConnectResult:
    """Make and save the team's own Coolify token, using your Coolify admin token.

    Logs in to the Coolify server with Coolify's SSH key for it and runs Coolify's own
    token code for the team's Coolify team (matched by its server's IP, then by name).
    """
    try:
        return service.connect_team(db, _team(db, team_id), user)
    except CoolifyError as err:
        _raise(err)


@router.post("/teams/{team_id}/resources/{kind}/{uuid}/{action}", response_model=ActionResult)
def resource_action(
    team_id: int, kind: ResourceKind, uuid: str, action: ResourceAction, db: DbSession
) -> ActionResult:
    """start / stop / restart, or redeploy (rebuild from scratch, pulling newer images)."""
    try:
        return service.resource_action(db, _team(db, team_id), kind, uuid, action)
    except Failure as err:
        _raise(err)


@router.get("/teams/{team_id}/applications/{uuid}/logs", response_model=Logs)
def app_logs(
    team_id: int, uuid: str, db: DbSession, lines: Annotated[int, Query(ge=10, le=5000)] = 300
) -> Logs:
    try:
        return Logs(logs=service.logs(db, _team(db, team_id), uuid, lines))
    except Failure as err:
        _raise(err)


@router.get("/teams/{team_id}/applications/{uuid}/deployments", response_model=list[Deployment])
def app_deployments(team_id: int, uuid: str, db: DbSession) -> list[Deployment]:
    try:
        return service.deployments(db, _team(db, team_id), uuid)
    except Failure as err:
        _raise(err)


@router.get("/teams/{team_id}/deployments/{uuid}", response_model=DeploymentDetail)
def deployment(team_id: int, uuid: str, db: DbSession) -> DeploymentDetail:
    try:
        return service.deployment(db, _team(db, team_id), uuid)
    except Failure as err:
        _raise(err)


@router.post("/teams/{team_id}/deployments/{uuid}/cancel", response_model=ActionResult)
def cancel_deployment(team_id: int, uuid: str, db: DbSession) -> ActionResult:
    try:
        return service.cancel_deployment(db, _team(db, team_id), uuid)
    except Failure as err:
        _raise(err)


@router.get("/teams/{team_id}/applications/{uuid}/envs", response_model=list[EnvVar])
def list_envs(team_id: int, uuid: str, db: DbSession) -> list[EnvVar]:
    try:
        return service.envs(db, _team(db, team_id), uuid)
    except Failure as err:
        _raise(err)


@router.post(
    "/teams/{team_id}/applications/{uuid}/envs",
    response_model=list[EnvVar],
    status_code=status.HTTP_201_CREATED,
)
def create_env(team_id: int, uuid: str, body: EnvWrite, db: DbSession) -> list[EnvVar]:
    team = _team(db, team_id)
    try:
        service.save_env(db, team, uuid, body, create=True)
        return service.envs(db, team, uuid)
    except Failure as err:
        _raise(err)


@router.patch("/teams/{team_id}/applications/{uuid}/envs", response_model=list[EnvVar])
def update_env(team_id: int, uuid: str, body: EnvWrite, db: DbSession) -> list[EnvVar]:
    """Change a variable's value, found by its key (that's how Coolify updates them)."""
    team = _team(db, team_id)
    try:
        service.save_env(db, team, uuid, body, create=False)
        return service.envs(db, team, uuid)
    except Failure as err:
        _raise(err)


@router.delete("/teams/{team_id}/applications/{uuid}/envs/{env_uuid}", response_model=list[EnvVar])
def delete_env(team_id: int, uuid: str, env_uuid: str, db: DbSession) -> list[EnvVar]:
    team = _team(db, team_id)
    try:
        service.delete_env(db, team, uuid, env_uuid)
        return service.envs(db, team, uuid)
    except Failure as err:
        _raise(err)


@router.get(
    "/teams/{team_id}/resources/{kind}/{uuid}/vulnerabilities", response_model=ResourceFindings
)
def vulnerabilities(team_id: int, kind: ResourceKind, uuid: str, db: DbSession) -> ResourceFindings:
    try:
        return service.findings(db, _team(db, team_id), kind, uuid)
    except Failure as err:
        _raise(err)


@router.put("/teams/{team_id}/servers/{uuid}/image-scanning", status_code=204)
def set_image_scanning(team_id: int, uuid: str, body: ImageScanningUpdate, db: DbSession) -> None:
    """Turn Coolify's automatic image scanning (daily and after deploys) on or off."""
    try:
        service.set_image_scanning(db, _team(db, team_id), uuid, body.enabled)
    except Failure as err:
        _raise(err)


@router.post("/teams/{team_id}/servers/{uuid}/docker-cleanup", response_model=ActionResult)
def docker_cleanup(team_id: int, uuid: str, db: DbSession) -> ActionResult:
    try:
        return service.docker_cleanup(db, _team(db, team_id), uuid)
    except Failure as err:
        _raise(err)


@router.post(
    "/teams/{team_id}/servers/{uuid}/jobs",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_job(
    team_id: int,
    uuid: str,
    body: JobStart,
    background: BackgroundTasks,
    user: CurrentUser,
    db: DbSession,
) -> JobRead:
    """Start a patch check, patching, or an image scan on the server, over SSH.

    Returns right away; poll ``GET /teams/{team_id}/jobs/{id}`` for progress.
    """
    try:
        job = service.start_job(db, _team(db, team_id), uuid, body.kind, user)
    except Failure as err:
        _raise(err)
    background.add_task(service.run_job, job.id)
    return service.job_read(db, job)


@router.get("/teams/{team_id}/jobs/{job_id}", response_model=JobRead)
def get_job(team_id: int, job_id: int, db: DbSession) -> JobRead:
    try:
        return service.get_job(db, _team(db, team_id), job_id)
    except CoolifyError as err:
        _raise(err)


module = ToolModule(
    id="coolify",
    name="Coolify",
    description="Deploy each team's project, manage environment variables, and watch deployments.",
    router=router,
    credentials=[
        CredentialSpec(
            key="coolify_url",
            label="Coolify dashboard address",
            description=(
                "The address of the course's Coolify dashboard, the page you log in to, "
                "e.g. https://coolify.example.edu. Shared by everyone."
            ),
            scope=CredentialScope.SYSTEM,
            placeholder="https://coolify.example.edu",
        ),
        CredentialSpec(
            key="digitalocean_token",
            label="DigitalOcean API token",
            description=(
                "Finds each team's DigitalOcean droplet, the server its Coolify team deploys "
                "to. Only reads droplets; a token with just the droplet:read scope is enough."
            ),
            scope=CredentialScope.USER,
            help_url="https://cloud.digitalocean.com/account/api/tokens",
            placeholder="dop_v1_...",
        ),
        CredentialSpec(
            key=service.ADMIN_TOKEN_KEY,
            label="Coolify admin token",
            description=(
                "Optional, and lets the workbench connect every team to Coolify by itself. A "
                "token from your main Coolify team (the one that owns the Coolify server) with "
                "the root permission. It's used to log in to the Coolify server and create each "
                "team's own token. Coolify's API must be on (Settings → Advanced → API and MCP)."
            ),
            scope=CredentialScope.USER,
            help_url="https://coolify.io/docs/api-reference/authorization",
            placeholder="1|...",
            required=False,
        ),
        CredentialSpec(
            key=service.TOKEN_KEY,
            label="Coolify API token",
            description=(
                "This team's own token. In Coolify, switch to the team, then Keys & Tokens → "
                "API tokens. Give it read, read:sensitive, write, and deploy; you must be an "
                "admin of the Coolify team for logs, environment values, and server patching. "
                "Coolify's API must be on (Settings → Advanced → API and MCP)."
            ),
            scope=CredentialScope.TEAM,
            help_url="https://coolify.io/docs/api-reference/authorization",
            placeholder="1|...",
        ),
    ],
    team_service=TeamService(
        resource_name="server",
        summary=(
            "Finds the team's DigitalOcean droplet (named or tagged after the team, e.g. "
            "BeforeDawn) and links Coolify, noting which server is theirs. In Coolify, pick "
            "the team in the team menu. Droplets are never created or changed."
        ),
        find=find_team_server,
    ),
)

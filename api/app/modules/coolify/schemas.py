from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ResourceKind = Literal["applications", "databases", "services"]
ResourceAction = Literal["start", "stop", "restart", "redeploy"]
JobKind = Literal["patch_check", "patch_security", "patch_all", "image_scan"]


class SecurityInfo(BaseModel):
    """Coolify's image-scan verdict for a resource, as its Security tab shows it."""

    # update_now | update_available | no_fix | check_needed | ok | not_checked
    status: str = "not_checked"
    label: str = ""
    action: str = ""
    problem_count: int = 0
    exploited_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    eol: bool | None = None
    checked_at: str | None = None


class JobRead(BaseModel):
    id: int
    kind: str
    server_uuid: str
    server_name: str
    status: str
    log: str
    result: dict[str, Any] | None
    error: str
    started_by: str | None
    created_at: datetime
    finished_at: datetime | None


class ServerInfo(BaseModel):
    uuid: str
    name: str
    ip: str
    reachable: bool | None = None
    usable: bool | None = None
    image_scanning: bool | None = None
    last_patch_check: JobRead | None = None
    last_image_scan: JobRead | None = None
    running_job: JobRead | None = None


class ResourceInfo(BaseModel):
    kind: ResourceKind
    uuid: str
    name: str
    # e.g. "running:healthy", "exited:unhealthy"
    status: str
    project: str = ""
    environment: str = ""
    fqdn: str | None = None
    git_repository: str | None = None
    git_branch: str | None = None
    security: SecurityInfo | None = None


class PanelOverview(BaseModel):
    team_name: str
    token_set: bool
    # The workbench can make this team's token itself (you have a Coolify admin token).
    auto_connect: bool = False
    dashboard_url: str | None
    # Name of the Coolify team the token belongs to.
    coolify_team: str | None = None
    # Why Coolify couldn't be read (API off, bad token, ...).
    error: str | None = None
    # Why the security results couldn't be read, when the rest could.
    security_error: str | None = None
    servers: list[ServerInfo] = []
    resources: list[ResourceInfo] = []


class ActionResult(BaseModel):
    message: str
    deployment_uuid: str | None = None


class Deployment(BaseModel):
    uuid: str
    status: str
    commit: str | None = None
    commit_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class LogLine(BaseModel):
    output: str
    # stdout | stderr
    type: str = "stdout"


class DeploymentDetail(Deployment):
    log: list[LogLine] = []


class Logs(BaseModel):
    logs: str


class EnvVar(BaseModel):
    uuid: str
    key: str
    # None when Coolify won't show it (token without read:sensitive, or locked).
    value: str | None
    is_buildtime: bool = False
    is_preview: bool = False
    is_literal: bool = False
    is_multiline: bool = False
    # Locked in Coolify: its value is never shown again.
    is_shown_once: bool = False


class EnvWrite(BaseModel):
    key: str = Field(min_length=1, max_length=255)
    value: str = Field(max_length=65535)
    is_preview: bool = False
    is_literal: bool = False
    is_multiline: bool = False

    @field_validator("key")
    @classmethod
    def _clean_key(cls, v: str) -> str:
        v = v.strip()
        if not v or any(c.isspace() for c in v):
            raise ValueError("Use a name without spaces, e.g. DATABASE_URL")
        return v


class Finding(BaseModel):
    id: str
    title: str = ""
    severity: str
    package: str = ""
    version: str = ""
    fixed_in: str = ""
    state: str = ""
    # In CISA's list of known exploited vulnerabilities.
    kev: bool = False
    url: str = ""
    image: str = ""


class ResourceFindings(BaseModel):
    security: SecurityInfo | None
    images: list[str]
    findings: list[Finding]
    total: int


class ImageScanningUpdate(BaseModel):
    enabled: bool


class JobStart(BaseModel):
    kind: JobKind


class TeamSecurity(BaseModel):
    """One team's row on the course-wide Security page."""

    team_id: int
    team_name: str
    token_set: bool
    auto_connect: bool = False
    error: str | None = None
    resources: list[ResourceInfo] = []
    servers: list[ServerInfo] = []


class AutoConnectResult(BaseModel):
    coolify_team: str
    message: str


class ApiRequest(BaseModel):
    """A raw call to the team's Coolify API, for anything the panel has no screen for."""

    method: Literal["GET", "POST", "PATCH", "PUT", "DELETE"] = "GET"
    # Under /api/v1, e.g. "/applications" or "/databases/<uuid>/backups".
    path: str = Field(min_length=1, max_length=500)
    body: Any = None

    @field_validator("path")
    @classmethod
    def _safe_path(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("/"):
            v = f"/{v}"
        v = v.removeprefix("/api/v1")
        if ".." in v or "://" in v or "\\" in v or any(c.isspace() for c in v):
            raise ValueError("Use a path under /api/v1, like /applications")
        return v or "/"


class ApiResponse(BaseModel):
    status: int
    data: Any = None


# --- Course summary (the dashboard's "Needs attention" and team status lines) -------


class AppSummary(BaseModel):
    kind: ResourceKind
    uuid: str
    name: str
    # e.g. "running:healthy", "exited:unhealthy"
    status: str
    security: SecurityInfo | None = None


class ServerSummary(BaseModel):
    uuid: str
    name: str
    ip: str
    reachable: bool | None = None
    # From the last update check, if there's been one.
    update_count: int | None = None
    security_count: int | None = None
    reboot_required: bool | None = None
    checked_at: datetime | None = None
    job_running: bool = False


class TeamSummary(BaseModel):
    team_id: int
    team_name: str
    connected: bool
    error: str | None = None
    apps: list[AppSummary] = []
    servers: list[ServerSummary] = []
    # GitHub repositories ("owner/name") the team's apps deploy from.
    repos: list[str] = []


class CourseSummary(BaseModel):
    teams: list[TeamSummary]
    generated_at: datetime

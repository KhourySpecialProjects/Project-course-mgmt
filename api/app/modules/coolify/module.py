"""Coolify tool module.

The course runs one Coolify dashboard (an administrator sets its address in
System settings). Each student team is its own Team in Coolify, with its own
DigitalOcean droplet added as that team's server.

With your DigitalOcean API token, the workbench finds each team's droplet (named
or tagged after the team, e.g. ``BeforeDawn``) and links the team to Coolify,
noting which server is theirs (see ``team_service`` below).

Coolify can't open a particular team from a link: which team you're looking at
is chosen in Coolify's own team menu, and a link to a server page only works when
that server's team is already the current one. So the link goes to the dashboard.
Deploying team repos, environment variables, and deployment status will be added here.

Get the settings inside an endpoint with:

    from app.credentials.service import get_system_credential, get_user_credential
    dashboard = get_system_credential(db, "coolify_url")
    token = get_user_credential(db, user, "digitalocean_token")
"""

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.core.http import ExternalServiceError
from app.core.naming import best_match
from app.credentials.service import get_system_credential, get_user_credential
from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules.base import CreatedResource, TeamService, ToolModule, ToolStatus, status_for
from app.modules.coolify import digitalocean
from app.users.models import User

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/status", response_model=ToolStatus)
def status(user: CurrentUser, db: DbSession) -> ToolStatus:
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

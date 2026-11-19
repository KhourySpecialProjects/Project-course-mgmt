"""Coolify tool module.

This is a placeholder that shows the shape of a module. The real work
(projects per team, deploying team repos, environment variables, deployment
status) will be added here.

Coolify is self-hosted, so the module needs two things: the address of the
course's Coolify server (one per app, set by an administrator) and each
user's own API token. Get them inside an endpoint with:

    from app.credentials.service import get_system_credential, get_user_credential
    base_url = get_system_credential(db, "coolify_url")      # e.g. https://coolify.example.edu
    token = get_user_credential(db, user, "coolify_token")

API calls go to ``f"{base_url.rstrip('/')}/api/v1/..."`` with the header
``Authorization: Bearer <token>``.
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules.base import ToolModule, ToolStatus, status_for

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/status", response_model=ToolStatus)
def status(user: CurrentUser, db: DbSession) -> ToolStatus:
    """Report whether the Coolify integration is ready for the current user."""
    return status_for(module, db, user)


module = ToolModule(
    id="coolify",
    name="Coolify",
    description="Deploy each team's project, manage environment variables, and watch deployments.",
    router=router,
    credentials=[
        CredentialSpec(
            key="coolify_url",
            label="Coolify server URL",
            description=(
                "The address of the course's Coolify server, shared by everyone, e.g. "
                "https://coolify.example.edu. Use https://app.coolify.io for Coolify Cloud."
            ),
            scope=CredentialScope.SYSTEM,
            placeholder="https://coolify.example.edu",
        ),
        CredentialSpec(
            key="coolify_token",
            label="Coolify API token",
            description=(
                "Lets the workbench act in Coolify as you: creating projects and apps and "
                "deploying them for your team. Create one in Coolify under Keys & Tokens; "
                "API access must be enabled on the server."
            ),
            scope=CredentialScope.USER,
            help_url="https://coolify.io/docs/api-reference/authorization",
            placeholder="1|...",
        ),
    ],
)

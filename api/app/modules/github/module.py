"""GitHub tool module.

This is a placeholder that shows the shape of a module. The real work (bulk
repo creation, teams, permissions) will be added here.

Get the current user's token inside an endpoint with:

    from app.credentials.service import get_user_credential
    token = get_user_credential(db, user, "github_token")
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules.base import ToolModule, ToolStatus, status_for

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/status", response_model=ToolStatus)
def status(user: CurrentUser, db: DbSession) -> ToolStatus:
    """Report whether the GitHub integration is ready for the current user."""
    return status_for(module, db, user)


module = ToolModule(
    id="github",
    name="GitHub",
    description="Create repos and teams in bulk, manage access, and view the org.",
    router=router,
    credentials=[
        CredentialSpec(
            key="github_token",
            label="GitHub personal access token",
            description=(
                "Lets the workbench act in GitHub as you: creating repos and teams and "
                "managing access in your course organization. Needs admin rights on the org."
            ),
            scope=CredentialScope.USER,
            help_url="https://github.com/settings/tokens",
            placeholder="github_pat_...",
        ),
    ],
)

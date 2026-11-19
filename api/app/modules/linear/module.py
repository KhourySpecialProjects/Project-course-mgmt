"""Linear tool module.

This is a placeholder that shows the shape of a module. The real work
(inviting users, creating teams and projects, monitoring progress) will be
added here.

Get the current user's key inside an endpoint with:

    from app.credentials.service import get_user_credential
    api_key = get_user_credential(db, user, "linear_api_key")
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules.base import ToolModule, ToolStatus, status_for

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/status", response_model=ToolStatus)
def status(user: CurrentUser, db: DbSession) -> ToolStatus:
    """Report whether the Linear integration is ready for the current user."""
    return status_for(module, db, user)


module = ToolModule(
    id="linear",
    name="Linear",
    description="Invite users, create teams and projects, and monitor progress.",
    router=router,
    credentials=[
        CredentialSpec(
            key="linear_api_key",
            label="Linear personal API key",
            description=(
                "Lets the workbench act in Linear as you: inviting users and creating "
                "teams, projects, and issues. Create one in your Linear account settings."
            ),
            scope=CredentialScope.USER,
            placeholder="lin_api_...",
        ),
    ],
)

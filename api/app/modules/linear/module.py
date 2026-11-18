"""Linear tool module.

This is a placeholder that shows the shape of a module. The real work
(inviting users, creating teams and projects, monitoring progress) will be
added here.
"""

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_user
from app.modules.base import ToolModule

router = APIRouter(dependencies=[Depends(require_user)])


def is_configured() -> bool:
    return bool(os.environ.get("LINEAR_API_KEY"))


class LinearStatus(BaseModel):
    configured: bool
    message: str


@router.get("/status", response_model=LinearStatus)
def status() -> LinearStatus:
    """Report whether the Linear integration is ready to use."""
    if is_configured():
        return LinearStatus(configured=True, message="Linear API key found.")
    return LinearStatus(
        configured=False,
        message="Set LINEAR_API_KEY in .env to enable the Linear tools.",
    )


module = ToolModule(
    id="linear",
    name="Linear",
    description="Invite users, create teams and projects, and monitor progress.",
    router=router,
    is_configured=is_configured,
)

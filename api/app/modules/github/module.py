"""GitHub tool module.

This is a placeholder that shows the shape of a module. The real work (bulk
repo creation, teams, permissions) will be added here.
"""

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_user
from app.modules.base import ToolModule

router = APIRouter(dependencies=[Depends(require_user)])


def is_configured() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN"))


class GitHubStatus(BaseModel):
    configured: bool
    message: str


@router.get("/status", response_model=GitHubStatus)
def status() -> GitHubStatus:
    """Report whether the GitHub integration is ready to use."""
    if is_configured():
        return GitHubStatus(configured=True, message="GitHub token found.")
    return GitHubStatus(
        configured=False,
        message="Set GITHUB_TOKEN in .env to enable the GitHub tools.",
    )


module = ToolModule(
    id="github",
    name="GitHub",
    description="Create repos and teams in bulk, manage access, and view the org.",
    router=router,
    is_configured=is_configured,
)

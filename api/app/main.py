"""Entry point for the API. Uvicorn runs the ``app`` object defined here.

All routes live under ``/api`` so the web app can forward ``/api/*`` requests
to this service. Interactive API docs: http://localhost:8000/api/docs
"""

from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from app.auth.dependencies import CurrentUser
from app.auth.router import router as auth_router
from app.core.db import DbSession
from app.credentials.router import router as credentials_router
from app.invites.router import admin_router as invites_admin_router
from app.invites.router import public_router as invites_public_router
from app.modules import MODULES
from app.modules.base import ToolInfo
from app.users.router import router as users_router

app = FastAPI(
    title="Course Management Workbench API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

api = APIRouter(prefix="/api")


@api.get("/health", tags=["meta"])
def health(db: DbSession) -> dict[str, str]:
    """Liveness check. Also confirms the database is reachable."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@api.get("/tools", tags=["meta"], response_model=list[ToolInfo])
def list_tools(user: CurrentUser, db: DbSession) -> list[ToolInfo]:
    """List the installed tool modules and whether each is configured for the current user."""
    return [
        ToolInfo(
            id=m.id,
            name=m.name,
            description=m.description,
            configured=m.is_configured(db, user),
        )
        for m in MODULES
    ]


api.include_router(auth_router)
api.include_router(users_router)
api.include_router(invites_admin_router)
api.include_router(invites_public_router)
api.include_router(credentials_router)
for module in MODULES:
    api.include_router(module.router, prefix=f"/tools/{module.id}", tags=[module.id])

app.include_router(api)

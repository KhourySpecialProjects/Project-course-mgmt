"""Entry point for the API. Uvicorn runs the ``app`` object defined here.

All routes live under ``/api`` so the web app can forward ``/api/*`` requests
to this service. Interactive API docs: http://localhost:8000/api/docs
"""

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text

from app.auth.dependencies import require_user
from app.auth.router import router as auth_router
from app.core.db import DbSession
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


@api.get(
    "/tools", tags=["meta"], response_model=list[ToolInfo], dependencies=[Depends(require_user)]
)
def list_tools() -> list[ToolInfo]:
    """List the installed tool modules and whether each one is configured."""
    return [
        ToolInfo(id=m.id, name=m.name, description=m.description, configured=m.is_configured())
        for m in MODULES
    ]


api.include_router(auth_router)
api.include_router(users_router)
for module in MODULES:
    api.include_router(module.router, prefix=f"/tools/{module.id}", tags=[module.id])

app.include_router(api)

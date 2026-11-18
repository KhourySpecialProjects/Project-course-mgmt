"""The contract every tool module implements.

A *tool module* is a self-contained integration (GitHub, Linear, ...). The core
app knows nothing about any particular tool; it just loops over the registered
modules (see ``app/modules/__init__.py``) and mounts each one's router at
``/api/tools/<id>``.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter
from pydantic import BaseModel


@dataclass(frozen=True)
class ToolModule:
    # Short, URL-safe identifier, e.g. "github". Used in URLs and must match the
    # id of the matching module in the web app (web/src/modules).
    id: str
    name: str
    description: str
    router: APIRouter
    # Returns True when the module has what it needs to run (e.g. an API token).
    is_configured: Callable[[], bool]


class ToolInfo(BaseModel):
    """What ``GET /api/tools`` returns for each module."""

    id: str
    name: str
    description: str
    configured: bool

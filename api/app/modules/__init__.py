"""Registry of tool modules.

To add a module, create a package next to ``github/`` and ``linear/`` that
exposes a ``module`` object, then add it to ``MODULES`` below. See
docs/adding-a-tool-module.md for a walkthrough.
"""

from app.modules.base import ToolModule
from app.modules.github import module as github
from app.modules.linear import module as linear

MODULES: list[ToolModule] = [
    github.module,
    linear.module,
]

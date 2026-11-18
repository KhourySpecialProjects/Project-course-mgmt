"""Every credential the app knows about.

Core (app-wide) credentials are declared here. Tool modules declare their own
in their ``ToolModule(credentials=[...])``, and they're collected below, so a
new module's keys show up in the UI automatically.
"""

from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules import MODULES

CORE_CREDENTIALS: list[CredentialSpec] = [
    CredentialSpec(
        key="anthropic_api_key",
        label="Anthropic API key",
        description=(
            "Used for the app's AI-assisted features. Shared by everyone; "
            "create it in your organization's Anthropic account."
        ),
        scope=CredentialScope.SYSTEM,
        placeholder="sk-ant-...",
    ),
]


def all_specs() -> list[CredentialSpec]:
    return CORE_CREDENTIALS + [spec for m in MODULES for spec in m.credentials]


def specs_for(scope: CredentialScope) -> list[CredentialSpec]:
    return [s for s in all_specs() if s.scope == scope]


def get_spec(key: str, scope: CredentialScope) -> CredentialSpec | None:
    return next((s for s in specs_for(scope) if s.key == key), None)

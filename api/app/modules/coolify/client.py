"""Calls to the Coolify REST API (https://coolify.io/docs/api-reference).

Coolify API tokens belong to one Coolify team, so every call here is made with a
team's own token (saved on the team; see ``coolify_team_token`` in module.py)
against the course's Coolify dashboard address. Everything Coolify's MCP server
does goes through these same REST routes.

Token permissions (chosen when the token is created in Coolify):
    read            list and inspect
    read:sensitive  logs, environment values, SSH keys (for server patching)
    write           change settings, environment variables
    deploy          deploy, start, stop, restart, cancel, Docker cleanup
"""

from typing import Any, Literal
from urllib.parse import urlencode, urlsplit

from app.core import http
from app.core.http import ExternalServiceError

ResourceKind = Literal["applications", "databases", "services"]

API_OFF = (
    "Coolify's API is turned off. In Coolify, open Settings → Advanced → API and MCP and "
    "turn on API access."
)
TOKEN_PERMISSIONS = "read, read:sensitive, write, and deploy"


def dashboard_url(saved: str) -> str:
    """Tidy the saved dashboard address: "coolify.example.edu/" -> "https://coolify.example.edu"."""
    url = saved.strip().rstrip("/")
    if not urlsplit(url).scheme:
        url = f"https://{url}"
    return url


def _query(params: dict[str, Any]) -> str:
    clean = {
        k: ("true" if v is True else "false" if v is False else v)
        for k, v in params.items()
        if v is not None
    }
    return f"?{urlencode(clean)}" if clean else ""


class CoolifyClient:
    def __init__(self, dashboard: str, token: str) -> None:
        self.base = dashboard_url(dashboard)
        self._token = token

    # --- plumbing -----------------------------------------------------------

    def _call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: Any = None,
        timeout: float = 30,
    ) -> Any:
        url = f"{self.base}/api/v1{path}{_query(params or {})}"
        try:
            data = http.request_json(
                method,
                url,
                headers={"Authorization": f"Bearer {self._token}"},
                body=body,
                timeout=timeout,
            )
        except http.HttpError as err:
            raise self._error(err) from None
        if isinstance(data, str) and data.lstrip().startswith("<"):
            raise ExternalServiceError(
                f"{self.base} answered with a web page, not Coolify's API. Check the Coolify "
                "dashboard address in System settings."
            )
        return data

    def _error(self, err: http.HttpError) -> ExternalServiceError:
        detail = err.detail()
        if err.status == 0:
            return ExternalServiceError(f"Couldn't reach Coolify at {self.base}: {err.reason}")
        if isinstance(err.body, str) and err.body.lstrip().startswith("<"):
            return ExternalServiceError(
                f"{self.base} answered with a web page (HTTP {err.status}), not Coolify's API. "
                "Check the Coolify dashboard address in System settings."
            )
        if err.status == 401:
            return ExternalServiceError(
                "Coolify rejected this team's API token. Create a new one in Coolify (while "
                "switched to this team) and save it on this page."
            )
        if err.status == 403 and "api is disabled" in detail.lower():
            return ExternalServiceError(API_OFF)
        if err.status == 403 and "not allowed to access the api" in detail.lower():
            return ExternalServiceError(
                "Coolify refused this workbench's internet address. In Coolify, open Settings → "
                "Advanced → API and MCP and add the workbench server's public IP address to "
                "Allowed IPs (or clear the list to allow any address with a valid token)."
            )
        if err.status == 403:
            return ExternalServiceError(
                f"This team's Coolify token isn't allowed to do that ({detail}). Give the token "
                f"the {TOKEN_PERMISSIONS} permissions; reading logs, environment values, and "
                "SSH keys also needs the token's owner to be an admin of the Coolify team."
            )
        if err.status == 404:
            return ExternalServiceError(f"Not found in this team's Coolify: {detail}")
        return ExternalServiceError(f"Coolify error ({err.status}): {detail}")

    def raw(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        """Any API call, as-is: (status, response). Errors come back, not raised."""
        url = f"{self.base}/api/v1{path}"
        try:
            data = http.request_json(
                method,
                url,
                headers={"Authorization": f"Bearer {self._token}"},
                body=body,
                timeout=60,
            )
        except http.HttpError as err:
            if err.status == 0:
                raise self._error(err) from None
            return err.status, err.body
        return 200, data

    def _list(self, path: str, **params: Any) -> list[dict[str, Any]]:
        data = self._call("GET", path, params=params)
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []

    def _dict(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        data = self._call(method, path, **kwargs)
        return data if isinstance(data, dict) else {}

    # --- team, servers, projects ----------------------------------------------

    def team(self) -> dict[str, Any]:
        return self._dict("GET", "/team")

    def servers(self) -> list[dict[str, Any]]:
        return self._list("/servers")

    def server(self, uuid: str) -> dict[str, Any]:
        return self._dict("GET", f"/servers/{uuid}")

    def projects(self) -> list[dict[str, Any]]:
        return self._list("/projects")

    def environments(self, project_uuid: str) -> list[dict[str, Any]]:
        return self._list(f"/projects/{project_uuid}/environments")

    # --- applications, databases, services ------------------------------------

    def resources(self, kind: ResourceKind) -> list[dict[str, Any]]:
        return self._list(f"/{kind}")

    def control(
        self,
        kind: ResourceKind,
        uuid: str,
        action: str,
        *,
        force: bool = False,
        latest: bool = False,
    ) -> dict[str, Any]:
        """start / stop / restart.

        Starting an application deploys it (``force`` rebuilds without cache);
        restarting a service with ``latest`` pulls its newest images first.
        """
        params: dict[str, Any] = {}
        if action == "start" and kind == "applications" and force:
            params["force"] = True
        if action == "restart" and kind == "services" and latest:
            params["latest"] = True
        return self._dict("POST", f"/{kind}/{uuid}/{action}", params=params)

    def logs(self, uuid: str, *, lines: int = 200) -> str:
        data = self._dict("GET", f"/applications/{uuid}/logs", params={"lines": lines})
        return str(data.get("logs") or "")

    # --- deployments ----------------------------------------------------------

    def deployments(self, app_uuid: str, *, take: int = 10) -> list[dict[str, Any]]:
        data = self._dict("GET", f"/deployments/applications/{app_uuid}", params={"take": take})
        items = data.get("deployments") or []
        return [d for d in items if isinstance(d, dict)]

    def deployment(self, uuid: str) -> dict[str, Any]:
        return self._dict("GET", f"/deployments/{uuid}")

    def cancel_deployment(self, uuid: str) -> dict[str, Any]:
        return self._dict("POST", f"/deployments/{uuid}/cancel")

    # --- environment variables ------------------------------------------------

    def envs(self, app_uuid: str) -> list[dict[str, Any]]:
        return self._list(f"/applications/{app_uuid}/envs")

    def create_env(self, app_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._dict("POST", f"/applications/{app_uuid}/envs", body=data)

    def update_env(self, app_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Coolify updates environment variables by key."""
        return self._dict("PATCH", f"/applications/{app_uuid}/envs", body=data)

    def delete_env(self, app_uuid: str, env_uuid: str) -> dict[str, Any]:
        return self._dict("DELETE", f"/applications/{app_uuid}/envs/{env_uuid}")

    # --- security -------------------------------------------------------------

    def vulnerabilities(self) -> list[dict[str, Any]]:
        """Image scan results for every resource of the team."""
        data = self._call("GET", "/vulnerabilities")
        if isinstance(data, dict):
            data = data.get("resources") or []
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []

    def resource_vulnerabilities(
        self, kind: ResourceKind, uuid: str, *, page: int = 1, per_page: int = 100
    ) -> dict[str, Any]:
        return self._dict(
            "GET",
            f"/{kind}/{uuid}/vulnerabilities",
            params={"page": page, "per_page": per_page},
        )

    def image_scanning(self, server_uuid: str) -> dict[str, Any]:
        return self._dict("GET", f"/servers/{server_uuid}/image-scanning")

    def set_image_scanning(self, server_uuid: str, enabled: bool) -> dict[str, Any]:
        return self._dict(
            "PATCH",
            f"/servers/{server_uuid}/image-scanning",
            body={"is_image_scan_enabled": enabled},
        )

    def docker_cleanup(self, server_uuid: str) -> dict[str, Any]:
        return self._dict("POST", f"/servers/{server_uuid}/docker-cleanup/run", timeout=120)

    # --- SSH keys (for server patching and scans) -----------------------------

    def private_keys(self) -> list[str]:
        """The team's SSH private keys. Needs read:sensitive, else Coolify hides them."""
        keys = []
        for item in self._list("/security/keys"):
            text = item.get("private_key")
            if not text and item.get("uuid"):
                text = self._dict("GET", f"/security/keys/{item['uuid']}").get("private_key")
            if isinstance(text, str) and "PRIVATE KEY" in text:
                keys.append(text)
        return keys

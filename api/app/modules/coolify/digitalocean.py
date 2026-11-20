"""Calls to the DigitalOcean API (https://docs.digitalocean.com/reference/api/).

Each team's Coolify runs on its own DigitalOcean droplet. This finds the droplets
so the workbench can work out each team's server address. Read-only: it never
creates, changes, or deletes droplets.
"""

from dataclasses import dataclass
from typing import Any

from app.core import http
from app.core.http import ExternalServiceError

API_URL = "https://api.digitalocean.com/v2"
MAX_PAGES = 10  # 200 droplets per page


@dataclass(frozen=True)
class Droplet:
    id: str
    name: str
    tags: list[str]
    # Public IPv4 address, or None while the droplet is still being set up.
    ip: str | None


def _droplet(raw: dict[str, Any]) -> Droplet:
    v4 = (raw.get("networks") or {}).get("v4") or []
    public = next((n["ip_address"] for n in v4 if n.get("type") == "public"), None)
    return Droplet(
        id=str(raw["id"]),
        name=str(raw.get("name", "")),
        tags=[str(t) for t in raw.get("tags") or []],
        ip=str(public) if public else None,
    )


def list_droplets(token: str) -> list[Droplet]:
    """Every droplet the token can see."""
    droplets: list[Droplet] = []
    url: str | None = f"{API_URL}/droplets?per_page=200"
    for _ in range(MAX_PAGES):
        if url is None:
            break
        try:
            data = http.request_json("GET", url, headers={"Authorization": f"Bearer {token}"})
        except http.HttpError as err:
            if err.status == 0:
                raise ExternalServiceError(f"Couldn't reach DigitalOcean: {err.reason}") from None
            if err.status == 401:
                raise ExternalServiceError(
                    "DigitalOcean rejected your API token. Replace it with a valid one."
                ) from None
            if err.status == 403:
                raise ExternalServiceError(
                    "Your DigitalOcean token can't list droplets. Give it read access to "
                    "droplets (the droplet:read scope)."
                ) from None
            raise ExternalServiceError(
                f"DigitalOcean error ({err.status}): {err.detail()}"
            ) from None
        if not isinstance(data, dict):
            raise ExternalServiceError("DigitalOcean sent an unexpected response.")
        droplets += [_droplet(d) for d in data.get("droplets") or []]
        url = ((data.get("links") or {}).get("pages") or {}).get("next")
    return droplets

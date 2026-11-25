"""A small helper for calling outside services' JSON APIs (GitHub, Linear, Coolify, ...).

    from app.core import http

    repo = http.request_json("GET", "https://api.github.com/repos/org/name", headers={...})

It uses only the standard library. Tests swap ``request_json`` for a fake with
pytest's ``monkeypatch`` so they never touch the network (see tests/test_teams.py).

Error handling:

- ``HttpError`` means the request failed: the service answered with an error
  status, or couldn't be reached at all (``status == 0``). Integration code
  catches it and turns it into a helpful ``ExternalServiceError``.
- ``ExternalServiceError`` carries a message that is safe to show to the user.
  Never put a token or key in it.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "course-workbench"
DEFAULT_TIMEOUT_SECONDS = 20.0


class ExternalServiceError(Exception):
    """An outside service refused or failed. ``str(err)`` is shown to the user as-is."""


class HttpError(Exception):
    def __init__(self, status: int, body: Any = None, reason: str = "") -> None:
        # HTTP status code, or 0 if the service couldn't be reached.
        self.status = status
        # Parsed JSON body of the error response (or its text, or None).
        self.body = body
        self.reason = reason
        super().__init__(f"HTTP {status} {reason}".strip())

    def detail(self) -> str:
        """The most useful human-readable bit of the error response."""
        body = self.body
        if isinstance(body, dict):
            parts = [str(body["message"])] if body.get("message") else []
            for e in body.get("errors") or []:
                if isinstance(e, dict) and e.get("message"):
                    parts.append(str(e["message"]))
            if parts:
                return ": ".join(parts)
        if isinstance(body, str) and body.strip():
            return body.strip()[:300]
        return self.reason or f"HTTP {self.status}"


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: Any = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Send a request (with ``body`` as JSON, if given) and return the parsed JSON response."""
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise HttpError(0, reason=f"Not an http(s) address: {url}")

    all_headers = {"Accept": "application/json", "User-Agent": USER_AGENT, **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        all_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=all_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw: bytes = resp.read()
    except urllib.error.HTTPError as err:
        raise HttpError(err.code, _parse(err.read()), str(err.reason)) from None
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        reason = getattr(err, "reason", None) or err
        raise HttpError(0, reason=str(reason)) from None
    return _parse(raw)


def _parse(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode(errors="replace")[:1000]

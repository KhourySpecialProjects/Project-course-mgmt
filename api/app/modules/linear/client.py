"""Calls to Linear's GraphQL API (https://linear.app/developers/graphql).

The only file in this module that talks to Linear. Every function takes the
API key to use; read it with ``get_user_credential(db, user, "linear_api_key")``.
"""

from dataclasses import dataclass
from typing import Any

from app.core import http
from app.core.http import ExternalServiceError
from app.core.naming import best_match

API_URL = "https://api.linear.app/graphql"
APP_URL = "https://linear.app"


@dataclass(frozen=True)
class LinearTeam:
    id: str
    key: str
    name: str
    url: str


def _first_error(errors: Any) -> str:
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        first = errors[0]
        extensions = first.get("extensions") or {}
        return str(extensions.get("userPresentableMessage") or first.get("message") or first)
    return str(errors)


def _graphql(api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    # Personal API keys go in the Authorization header as-is (no "Bearer").
    try:
        data = http.request_json(
            "POST",
            API_URL,
            headers={"Authorization": api_key},
            body={"query": query, "variables": variables or {}},
        )
    except http.HttpError as err:
        if err.status == 0:
            raise ExternalServiceError(f"Couldn't reach Linear: {err.reason}") from None
        if err.status == 401:
            raise ExternalServiceError(
                "Linear rejected your API key. Replace it with a valid one."
            ) from None
        body = err.body if isinstance(err.body, dict) else {}
        message = _first_error(body["errors"]) if body.get("errors") else err.detail()
        raise ExternalServiceError(f"Linear error: {message}") from None
    if not isinstance(data, dict):
        raise ExternalServiceError("Linear sent an unexpected response.")
    if data.get("errors"):
        raise ExternalServiceError(f"Linear error: {_first_error(data['errors'])}")
    result: dict[str, Any] = data.get("data") or {}
    return result


_FIND_TEAMS = """
query WorkbenchTeams {
  organization { urlKey }
  teams(first: 250) { nodes { id key name } }
}
"""

_CREATE_TEAM = """
mutation WorkbenchCreateTeam($input: TeamCreateInput!) {
  teamCreate(input: $input) { success team { id key name } }
}
"""


def _to_team(node: dict[str, Any], url_key: str) -> LinearTeam:
    return LinearTeam(
        id=str(node["id"]),
        key=str(node["key"]),
        name=str(node["name"]),
        url=f"{APP_URL}/{url_key}/team/{node['key']}",
    )


def find_team(api_key: str, name: str) -> tuple[LinearTeam | None, str]:
    """The workspace's team matching ``name`` (see ``best_match``), or None.

    Also returns the workspace's URL key (the ``acme`` in linear.app/acme/...),
    which ``create_team`` needs.
    """
    found = _graphql(api_key, _FIND_TEAMS)
    url_key = str((found.get("organization") or {}).get("urlKey") or "")
    nodes = (found.get("teams") or {}).get("nodes") or []
    node = best_match(name, nodes, names=lambda n: [str(n.get("name", ""))])
    return (_to_team(node, url_key) if node else None), url_key


def create_team(api_key: str, name: str, url_key: str) -> LinearTeam:
    # Linear picks the team's short key (used in issue ids, e.g. TEA-12) from the name.
    created = _graphql(api_key, _CREATE_TEAM, {"input": {"name": name}})
    payload = created.get("teamCreate") or {}
    if not payload.get("success") or not payload.get("team"):
        raise ExternalServiceError("Linear didn't create the team.")
    return _to_team(payload["team"], url_key)

"""Calls to the GitHub REST API (https://docs.github.com/en/rest).

The only file in this module that talks to GitHub. Every function takes the
token to use; read it with ``get_user_credential(db, user, "github_token")``.
"""

from typing import Any
from urllib.parse import quote

from app.core import http
from app.core.http import ExternalServiceError

API_URL = "https://api.github.com"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _error(err: http.HttpError) -> ExternalServiceError:
    if err.status == 0:
        return ExternalServiceError(f"Couldn't reach GitHub: {err.reason}")
    if err.status == 401:
        return ExternalServiceError(
            "GitHub rejected your personal access token. Replace it with a valid one."
        )
    return ExternalServiceError(f"GitHub error ({err.status}): {err.detail()}")


def get_repo(token: str, owner: str, name: str) -> dict[str, Any] | None:
    """The repository ``owner/name``, or None if it doesn't exist (or the token can't see it)."""
    url = f"{API_URL}/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    try:
        repo: dict[str, Any] = http.request_json("GET", url, headers=_headers(token))
    except http.HttpError as err:
        if err.status == 404:
            return None
        raise _error(err) from None
    return repo


def list_org_repos(token: str, org: str, *, max_pages: int = 10) -> list[dict[str, Any]]:
    """The organization's repositories that the token can see (up to 100 per page)."""
    repos: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        url = f"{API_URL}/orgs/{quote(org, safe='')}/repos?per_page=100&page={page}"
        try:
            batch = http.request_json("GET", url, headers=_headers(token))
        except http.HttpError as err:
            if err.status == 404:
                raise ExternalServiceError(
                    f"GitHub organization '{org}' wasn't found, or your token can't see it. "
                    "Check the GitHub organization in System settings."
                ) from None
            raise _error(err) from None
        if not isinstance(batch, list):
            break
        repos += batch
        if len(batch) < 100:
            break
    return repos


def create_org_repo(token: str, org: str, name: str, *, description: str) -> dict[str, Any]:
    """Create a private repository in ``org``, with a README so it isn't empty."""
    url = f"{API_URL}/orgs/{quote(org, safe='')}/repos"
    body = {"name": name, "description": description, "private": True, "auto_init": True}
    try:
        repo: dict[str, Any] = http.request_json("POST", url, headers=_headers(token), body=body)
    except http.HttpError as err:
        if err.status == 404:
            raise ExternalServiceError(
                f"GitHub organization '{org}' wasn't found, or your token can't see it. "
                "Check the GitHub organization in System settings."
            ) from None
        if err.status == 403:
            raise ExternalServiceError(
                f"Your GitHub token isn't allowed to create repositories in '{org}'. "
                "It needs admin rights on the organization (for a fine-grained token: "
                "the organization as resource owner, with Administration: read and write)."
            ) from None
        raise _error(err) from None
    return repo

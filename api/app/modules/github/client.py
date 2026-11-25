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


def _get(token: str, path: str) -> Any:
    try:
        return http.request_json("GET", f"{API_URL}{path}", headers=_headers(token))
    except http.HttpError as err:
        if err.status == 404:
            raise ExternalServiceError(
                "GitHub says this repository doesn't exist, which is what it says when your "
                "token can't see a private repository. Give your token access to the "
                "organization's private repositories (Contents, Pull requests, Issues: read)."
            ) from None
        raise _error(err) from None


def _commit(raw: dict[str, Any]) -> dict[str, Any]:
    commit = raw.get("commit") or {}
    author = (raw.get("author") or {}).get("login") or (commit.get("author") or {}).get("name")
    return {
        "sha": str(raw.get("sha", ""))[:7],
        "message": str(commit.get("message", "")).split("\n", 1)[0],
        "author": author or "",
        "date": (commit.get("committer") or {}).get("date") or "",
        "url": raw.get("html_url") or "",
    }


def _pull(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": raw.get("number"),
        "title": raw.get("title") or "",
        "author": (raw.get("user") or {}).get("login") or "",
        "state": "merged" if raw.get("merged_at") else str(raw.get("state") or ""),
        "draft": bool(raw.get("draft")),
        "updated_at": raw.get("updated_at") or "",
        "url": raw.get("html_url") or "",
    }


def repo_activity(token: str, full_name: str, *, branch: str | None = None) -> dict[str, Any]:
    """Recent commits and pull requests of ``owner/name`` (on ``branch``, else the default)."""
    path = "/".join(quote(p, safe="") for p in full_name.split("/", 1))
    repo = _get(token, f"/repos/{path}")
    ref = branch or repo.get("default_branch") or "main"
    commits = _get(token, f"/repos/{path}/commits?per_page=30&sha={quote(ref, safe='')}")
    open_prs = _get(token, f"/repos/{path}/pulls?state=open&per_page=20&sort=updated")
    closed = _get(
        token, f"/repos/{path}/pulls?state=closed&per_page=10&sort=updated&direction=desc"
    )
    return {
        "full_name": repo.get("full_name") or full_name,
        "url": repo.get("html_url") or f"https://github.com/{full_name}",
        "private": bool(repo.get("private")),
        "branch": ref,
        "pushed_at": repo.get("pushed_at"),
        "open_issues": max(int(repo.get("open_issues_count") or 0) - len(open_prs), 0),
        "commits": [_commit(c) for c in commits if isinstance(c, dict)],
        "open_pulls": [_pull(p) for p in open_prs if isinstance(p, dict)],
        "recent_merged": [_pull(p) for p in closed if isinstance(p, dict) and p.get("merged_at")],
    }

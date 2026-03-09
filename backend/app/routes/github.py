"""
Routes for GitHub API proxying.

Fetches issues from GitHub's REST API and filters out pull requests
(which GitHub includes in the /issues endpoint).
"""

import logging
import os
import re

from fastapi import APIRouter, HTTPException, Query
import httpx

logger = logging.getLogger("backlog_pilot.routes.github")

router = APIRouter()

GITHUB_API_BASE = "https://api.github.com"

_REPO_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?/[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$")


def _validate_repo(repo: str) -> None:
    """Ensure repo matches owner/repo format to prevent path traversal."""
    if not _REPO_RE.match(repo):
        raise HTTPException(status_code=400, detail="Invalid repo format. Expected 'owner/repo'.")


def _github_headers() -> dict[str, str]:
    # TODO: Set GITHUB_TOKEN in backend/.env for higher rate limits.
    #       Without a token, GitHub allows only 60 requests/hour.
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@router.get("/issues")
async def list_issues(
    repo: str = Query(..., description="GitHub repo in owner/repo format"),
    state: str = Query("open", description="Issue state: open, closed, all"),
    sort: str = Query("updated", description="Sort by: created, updated, comments"),
    direction: str = Query("desc", description="Sort direction: asc, desc"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    labels: str = Query("", description="Comma-separated list of label names"),
):
    """Fetch issues from a GitHub repository."""
    _validate_repo(repo)
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
    params: dict[str, str | int] = {
        "state": state,
        "sort": sort,
        "direction": direction,
        "per_page": per_page,
        "page": page,
    }
    if labels:
        params["labels"] = labels

    logger.info("Fetching issues from %s (state=%s, sort=%s, direction=%s)", repo, state, sort, direction)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=_github_headers(), params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("GitHub API error %d for %s: %s", e.response.status_code, repo, e.response.text[:200])
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error("Failed to reach GitHub API: %s", e)
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach GitHub API: {str(e)}",
            )

    # Filter out pull requests (GitHub returns PRs in the issues endpoint)
    raw_items = resp.json()
    issues = [issue for issue in raw_items if "pull_request" not in issue]

    logger.info("GitHub returned %d items, %d after filtering PRs", len(raw_items), len(issues))

    return issues


@router.get("/issues/{issue_number}")
async def get_issue(
    repo: str = Query(..., description="GitHub repo in owner/repo format"),
    issue_number: int = 0,
):
    """Fetch a single issue from a GitHub repository."""
    _validate_repo(repo)
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}"

    logger.info("Fetching issue #%d from %s", issue_number, repo)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=_github_headers())
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("GitHub API error %d for %s#%d", e.response.status_code, repo, issue_number)
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error("Failed to reach GitHub API: %s", e)
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach GitHub API: {str(e)}",
            )

    return resp.json()

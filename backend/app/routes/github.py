import os
from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter()

GITHUB_API_BASE = "https://api.github.com"


def _github_headers() -> dict[str, str]:
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
    direction: str = Query("asc", description="Sort direction: asc, desc"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    labels: str = Query("", description="Comma-separated list of label names"),
):
    """Fetch issues from a GitHub repository."""
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

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=_github_headers(), params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach GitHub API: {str(e)}",
            )

    # Filter out pull requests (GitHub returns PRs in the issues endpoint)
    issues = [
        issue for issue in resp.json() if "pull_request" not in issue
    ]
    return issues


@router.get("/issues/{issue_number}")
async def get_issue(
    repo: str = Query(..., description="GitHub repo in owner/repo format"),
    issue_number: int = 0,
):
    """Fetch a single issue from a GitHub repository."""
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=_github_headers())
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach GitHub API: {str(e)}",
            )

    return resp.json()

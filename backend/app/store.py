"""In-memory store for tracked issues. Simple dict-based storage for MVP."""

from app.models import TrackedIssue

# Key: "{repo}#{issue_number}"
_tracked_issues: dict[str, TrackedIssue] = {}


def _key(repo: str, issue_number: int) -> str:
    return f"{repo}#{issue_number}"


def get_tracked_issue(repo: str, issue_number: int) -> TrackedIssue | None:
    return _tracked_issues.get(_key(repo, issue_number))


def upsert_tracked_issue(issue: TrackedIssue) -> TrackedIssue:
    _tracked_issues[_key(issue.repo, issue.issue_number)] = issue
    return issue


def get_all_tracked_issues() -> list[TrackedIssue]:
    return list(_tracked_issues.values())

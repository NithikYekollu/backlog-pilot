"""
Routes for Devin API integration.

All raw HTTP calls live in app.services.devin_api — this module handles
request validation, state tracking, and response shaping for the frontend.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models import (
    TriageRequest,
    FixRequest,
    MessageRequest,
    TrackedIssue,
    TriageResult,
)
from app.services.devin_api import (
    DevinAPIError,
    DevinSessionResponse,
    create_session,
    get_session,
    send_message,
    parse_triage_json,
    get_last_assistant_text,
    extract_pr_url,
)
from app.store import get_tracked_issue, upsert_tracked_issue, get_all_tracked_issues

logger = logging.getLogger("backlog_pilot.routes.devin")

router = APIRouter()


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

# TODO: Tune these prompts based on real Devin output quality.
#       The JSON-only instruction works well but Devin sometimes wraps in
#       markdown code fences — the parser handles that case.

TRIAGE_PROMPT_TEMPLATE = """You are triaging GitHub issue #{issue_number} from the repo {repo}.

**Issue Title:** {title}

**Issue Body:**
{body}

---

Please analyze this issue and provide a structured triage assessment. Respond with ONLY a JSON object (no markdown, no code fences) in exactly this format:

{{
  "severity": "<critical|high|medium|low>",
  "category": "<bug|feature|refactor|docs|infra>",
  "estimated_effort": "<small|medium|large>",
  "summary": "<one-sentence summary of the issue>",
  "suggested_approach": "<brief description of how to fix/implement this>",
  "can_auto_fix": <true|false>
}}

Be concise but specific in your summary and approach.
"""

FIX_PROMPT_TEMPLATE = """Fix GitHub issue #{issue_number} from the repo {repo}.

**Issue Title:** {title}

**Issue Body:**
{body}

{triage_context}

Please:
1. Clone the repository if needed
2. Analyze the issue and codebase
3. Implement the fix
4. Create a pull request with your changes
5. Make sure tests pass
"""


# ---------------------------------------------------------------------------
# Helper to convert DevinAPIError -> HTTPException
# ---------------------------------------------------------------------------

def _handle_devin_error(exc: DevinAPIError) -> HTTPException:
    logger.error("Devin API error: %s", exc)
    return HTTPException(status_code=exc.status_code, detail=str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/triage")
async def create_triage_session(request: TriageRequest):
    """Create a Devin session to triage a GitHub issue."""
    prompt = TRIAGE_PROMPT_TEMPLATE.format(
        issue_number=request.issue_number,
        repo=request.repo,
        title=request.title,
        body=request.body or "(no description provided)",
    )

    try:
        session = await create_session(prompt)
    except DevinAPIError as exc:
        raise _handle_devin_error(exc)

    logger.info(
        "Triage session created: id=%s repo=%s issue=#%d",
        session.session_id, request.repo, request.issue_number,
    )

    # Track the issue
    tracked = get_tracked_issue(request.repo, request.issue_number) or TrackedIssue(
        issue_number=request.issue_number,
        repo=request.repo,
        title=request.title,
    )
    tracked.triage_session_id = session.session_id
    tracked.triage_status = "running"
    tracked.devin_url = session.url
    upsert_tracked_issue(tracked)

    return {
        "session_id": session.session_id,
        "url": session.url,
        "status": "running",
    }


@router.get("/sessions/{session_id}")
async def get_session_status(session_id: str):
    """Poll the status of a Devin session.

    Returns the raw Devin API response so the frontend can inspect any field.
    """
    try:
        session = await get_session(session_id)
    except DevinAPIError as exc:
        raise _handle_devin_error(exc)

    return session.raw


@router.post("/sessions/{session_id}/message")
async def send_session_message(session_id: str, request: MessageRequest):
    """Send a follow-up message to a Devin session."""
    try:
        session = await send_message(session_id, request.message)
    except DevinAPIError as exc:
        raise _handle_devin_error(exc)

    return session.raw


@router.post("/fix")
async def create_fix_session(request: FixRequest):
    """Create a Devin session to fix a GitHub issue."""
    triage_context = ""
    if request.triage_result:
        triage_context = (
            f"**Triage Summary:** {request.triage_result.summary}\n"
            f"**Suggested Approach:** {request.triage_result.suggested_approach}\n"
            f"**Severity:** {request.triage_result.severity}\n"
            f"**Category:** {request.triage_result.category}\n"
            f"**Estimated Effort:** {request.triage_result.estimated_effort}\n"
        )

    prompt = FIX_PROMPT_TEMPLATE.format(
        issue_number=request.issue_number,
        repo=request.repo,
        title=request.title,
        body=request.body or "(no description provided)",
        triage_context=triage_context,
    )

    try:
        session = await create_session(prompt)
    except DevinAPIError as exc:
        raise _handle_devin_error(exc)

    logger.info(
        "Fix session created: id=%s repo=%s issue=#%d",
        session.session_id, request.repo, request.issue_number,
    )

    # Track the issue
    tracked = get_tracked_issue(request.repo, request.issue_number) or TrackedIssue(
        issue_number=request.issue_number,
        repo=request.repo,
        title=request.title,
    )
    tracked.fix_session_id = session.session_id
    tracked.fix_status = "running"
    tracked.devin_url = session.url
    upsert_tracked_issue(tracked)

    return {
        "session_id": session.session_id,
        "url": session.url,
        "status": "running",
    }


@router.post("/sessions/{session_id}/sync")
async def sync_session(session_id: str):
    """Sync session status and extract triage results or PR URL.

    This is the main polling endpoint the frontend uses.  It fetches the
    latest session state from Devin, tries to parse structured results,
    and updates the in-memory tracked issue.
    """
    try:
        session = await get_session(session_id)
    except DevinAPIError as exc:
        raise _handle_devin_error(exc)

    status = session.status

    # Find the tracked issue for this session
    all_issues = get_all_tracked_issues()
    tracked = None
    is_triage = False
    for issue in all_issues:
        if issue.triage_session_id == session_id:
            tracked = issue
            is_triage = True
            break
        if issue.fix_session_id == session_id:
            tracked = issue
            is_triage = False
            break

    if not tracked:
        logger.warning("sync_session called for unknown session %s", session_id)
        return {"status": status, "session_data": session.raw}

    if is_triage:
        tracked.triage_status = status
        _try_extract_triage_result(tracked, session)
    else:
        tracked.fix_status = status
        _try_extract_pr_url(tracked, session)

    upsert_tracked_issue(tracked)

    logger.info(
        "Synced session %s: status=%s triage_result=%s pr_url=%s",
        session_id, status,
        "yes" if tracked.triage_result else "no",
        tracked.pr_url or "none",
    )

    return {
        "status": status,
        "tracked_issue": tracked.model_dump(),
        "session_data": session.raw,
    }


@router.get("/tracked")
async def list_tracked_issues():
    """List all tracked issues."""
    return [issue.model_dump() for issue in get_all_tracked_issues()]


# ---------------------------------------------------------------------------
# Internal helpers for result extraction
# ---------------------------------------------------------------------------

def _try_extract_triage_result(tracked: TrackedIssue, session: DevinSessionResponse) -> None:
    """Try to pull a TriageResult from the session's output."""
    if tracked.triage_result:
        return  # already have it
    if session.status != "finished":
        return

    import json

    # 1) Check structured_output first
    # TODO: Verify that "structured_output" is the correct field name.
    structured = session.structured_output
    if structured:
        raw_str = json.dumps(structured) if isinstance(structured, dict) else str(structured)
        parsed = parse_triage_json(raw_str)
        if parsed:
            try:
                tracked.triage_result = TriageResult(**parsed)
                logger.info("Extracted triage result from structured_output")
                return
            except Exception as exc:
                logger.warning("structured_output parsed but failed validation: %s", exc)

    # 2) Fall back to last assistant message
    last_text = get_last_assistant_text(session)
    if last_text:
        parsed = parse_triage_json(last_text)
        if parsed:
            try:
                tracked.triage_result = TriageResult(**parsed)
                logger.info("Extracted triage result from conversation")
            except Exception as exc:
                logger.warning("Conversation text parsed but failed validation: %s", exc)


def _try_extract_pr_url(tracked: TrackedIssue, session: DevinSessionResponse) -> None:
    """Try to pull a PR URL from the session's output."""
    if tracked.pr_url:
        return
    if session.status != "finished":
        return

    # 1) structured_output
    structured = session.structured_output
    if structured and isinstance(structured, dict):
        # TODO: Confirm the actual field name(s) Devin uses for PR URLs.
        pr_url = structured.get("pr_url") or structured.get("pull_request_url")
        if pr_url:
            tracked.pr_url = pr_url
            return

    # 2) Last assistant message
    last_text = get_last_assistant_text(session)
    if last_text:
        pr_url = extract_pr_url(last_text)
        if pr_url:
            tracked.pr_url = pr_url

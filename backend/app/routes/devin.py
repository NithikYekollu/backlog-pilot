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

TRIAGE_PROMPT_TEMPLATE = """You are triaging GitHub issue #{issue_number} from the repository {repo}.

**Issue title:** {title}

**Issue body:**
{body}

---

### Instructions

1. **Restate the issue** — Write a clear one-sentence summary of what the reporter is describing. Do not copy the title verbatim; distill the core problem.

2. **Inspect relevant code** — Clone the repository if needed. Navigate the codebase to identify the components, modules, and files most likely involved. Read the actual source code rather than guessing from file names alone.

3. **Identify likely area and files** — Name the architectural area (e.g. "authentication middleware", "database migration layer", "React component tree") and list specific file paths you inspected.

4. **Estimate difficulty** — Rate as `easy` (isolated change, clear fix), `medium` (touches multiple files or requires careful reasoning), or `hard` (cross-cutting, risky, or poorly understood area).

5. **Assess autonomous fix safety** — Determine whether this issue can be safely fixed without human intervention. Set `safe_to_autofix` to `true` only if: the fix is well-scoped, unlikely to introduce regressions, and you are confident in the approach. When in doubt, set it to `false`.

6. **Flag ambiguity** — If the issue description is vague, missing reproduction steps, or could be interpreted multiple ways, set `needs_human_clarification` to `true`.

7. **Propose acceptance criteria** — List the concrete conditions that must hold for this issue to be considered resolved (e.g. "Login form no longer throws 500 on empty email", "Unit test added for edge case").

8. **Recommend next step** — State the single most useful next action (e.g. "Patch the validation logic in `src/auth/login.ts:45`", "Add a migration to backfill the missing column").

### Structured output

Update your `structured_output` immediately and keep refining it as you analyze. Return **only** these fields:

{{
  "issue_summary": "<one-sentence distillation of the issue>",
  "likely_area": "<architectural area of the codebase>",
  "suspected_files": ["<file paths you inspected and believe are involved>"],
  "difficulty": "<easy|medium|hard>",
  "safe_to_autofix": <true|false>,
  "needs_human_clarification": <true|false>,
  "acceptance_criteria": ["<condition that must hold when resolved>"],
  "recommended_next_step": "<concrete next action>"
}}

Do not include any fields outside this schema. Be concise but specific.
"""

FIX_PROMPT_TEMPLATE = """You are fixing GitHub issue #{issue_number} from the repository {repo}.

**Issue title:** {title}

**Issue body:**
{body}

{triage_context}

---

### Instructions

1. **Understand before changing** — Read the issue carefully. If triage context is provided above, use it as a starting point but verify the analysis yourself. Do not blindly trust triage output.

2. **Inspect the code** — Navigate to the suspected files and surrounding code. Understand the existing patterns, conventions, and test coverage before making changes.

3. **Reproduce or reason** — If the issue describes a bug, try to reproduce it or reason through the code path to confirm the root cause. If you cannot reproduce or confirm, surface this as a blocker instead of guessing.

4. **Make the smallest safe fix** — Change only what is necessary. Prefer targeted edits over refactors. Follow existing code style and conventions. Do not introduce new dependencies unless absolutely required.

5. **Run checks** — Run the project's test suite, linter, and type checker if available. Fix any failures your changes introduce. If the project has no tests, note this in your PR description.

6. **Surface blockers** — If you encounter ambiguity that is too high to resolve confidently, stop and say so rather than shipping a guess. Explain what you are unsure about and what information would unblock you.

7. **Open a pull request** — Create a PR with a clear title referencing the issue (e.g. "Fix #42: Prevent 500 on empty email login"), a description summarizing what you changed and why, and a list of files modified.

8. **Update structured output** — Keep your `structured_output` updated as you work:

{{
  "status": "<in_progress|blocked|completed>",
  "current_task": "<what you are doing right now>",
  "files_changed": ["<files you have modified>"],
  "pr_url": "<URL of the pull request once created>"
}}

### Guardrails

- Do NOT force-push, rebase, or amend commits.
- Do NOT modify unrelated files or clean up code outside the scope of the issue.
- Do NOT skip tests to make CI pass.
- If the fix requires a database migration, flag it for human review instead of running it.
- If you are less than 80% confident in your fix, set status to "blocked" and explain why.
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
        tr = request.triage_result
        parts: list[str] = []
        if tr.display_summary:
            parts.append(f"**Triage Summary:** {tr.display_summary}")
        if tr.display_approach:
            parts.append(f"**Recommended Next Step:** {tr.display_approach}")
        if tr.likely_area:
            parts.append(f"**Likely Area:** {tr.likely_area}")
        if tr.suspected_files:
            parts.append(f"**Suspected Files:** {', '.join(tr.suspected_files)}")
        if tr.difficulty:
            parts.append(f"**Difficulty:** {tr.difficulty.value}")
        if tr.acceptance_criteria:
            criteria = "\n".join(f"  - {c}" for c in tr.acceptance_criteria)
            parts.append(f"**Acceptance Criteria:**\n{criteria}")
        triage_context = "\n".join(parts)

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
        # Backend lost in-memory state (e.g. dev-mode reload).
        # Reconstruct a minimal TrackedIssue from the Devin API response
        # so the frontend still gets useful data (PR URL, triage result).
        logger.warning(
            "sync_session called for unknown session %s — reconstructing from API",
            session_id,
        )
        tracked = TrackedIssue(
            issue_number=0,
            repo="unknown",
            title="(recovered session)",
            fix_session_id=session_id,
            triage_session_id=session_id,
        )
        # When we don't know the session type, try both extractions
        is_triage = False  # doesn't matter — we'll try both below

    if is_triage:
        tracked.triage_status = status
        _try_extract_triage_result(tracked, session)
    else:
        tracked.fix_status = status
        _try_extract_pr_url(tracked, session)

    # Always try PR URL extraction regardless of session type
    # (in case of recovered sessions or sessions that produce PRs unexpectedly)
    if not tracked.pr_url:
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
    """Try to pull a TriageResult from the session's output.

    Devin updates structured_output progressively, so we attempt extraction
    even while the session is still running.  However, we only overwrite an
    existing result if the new one has more fields populated.
    """
    import json

    def _try_build(parsed: dict) -> TriageResult | None:
        """Defensively build a TriageResult, ignoring unknown keys."""
        try:
            # Filter to only keys TriageResult knows about so extra fields
            # from Devin don't cause validation errors.
            known_keys = set(TriageResult.model_fields.keys())
            filtered = {k: v for k, v in parsed.items() if k in known_keys}
            return TriageResult(**filtered)
        except Exception as exc:
            logger.warning("Failed to build TriageResult: %s", exc)
            return None

    def _field_count(tr: TriageResult) -> int:
        """Count how many meaningful fields are populated."""
        count = 0
        if tr.issue_summary:
            count += 1
        if tr.likely_area:
            count += 1
        if tr.suspected_files:
            count += 1
        if tr.acceptance_criteria:
            count += 1
        if tr.recommended_next_step:
            count += 1
        return count

    best: TriageResult | None = tracked.triage_result

    # 1) Check structured_output first (the preferred source)
    structured = session.structured_output
    if structured:
        raw_str = json.dumps(structured) if isinstance(structured, dict) else str(structured)
        parsed = parse_triage_json(raw_str)
        if parsed:
            candidate = _try_build(parsed)
            if candidate and (not best or _field_count(candidate) > _field_count(best)):
                best = candidate
                logger.info("Extracted triage result from structured_output")

    # 2) Fall back to last assistant message.
    #    Devin often puts the triage JSON in conversation text rather than
    #    structured_output, and the session may be "blocked" (needs_input)
    #    rather than "finished" when the analysis is complete.
    last_text = get_last_assistant_text(session)
    if last_text:
        parsed = parse_triage_json(last_text)
        if parsed:
            candidate = _try_build(parsed)
            if candidate and (not best or _field_count(candidate) > _field_count(best)):
                best = candidate
                logger.info("Extracted triage result from conversation (status=%s)", session.status)

    if best and best is not tracked.triage_result:
        tracked.triage_result = best


def _try_extract_pr_url(tracked: TrackedIssue, session: DevinSessionResponse) -> None:
    """Try to pull a PR URL from the session's output.

    Devin may update structured_output with a pr_url while the session is
    still running, so we attempt extraction regardless of status.
    """
    if tracked.pr_url:
        return

    # 1) structured_output (available while running)
    structured = session.structured_output
    if structured and isinstance(structured, dict):
        pr_url = structured.get("pr_url") or structured.get("pull_request_url")
        if pr_url:
            tracked.pr_url = pr_url
            logger.info("Extracted PR URL from structured_output: %s", pr_url)
            return

    # 2) Last assistant message (check anytime, most useful when finished)
    last_text = get_last_assistant_text(session)
    if last_text:
        pr_url = extract_pr_url(last_text)
        if pr_url:
            tracked.pr_url = pr_url
            logger.info("Extracted PR URL from conversation: %s", pr_url)

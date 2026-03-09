import os
import json
import re
from fastapi import APIRouter, HTTPException
import httpx

from app.models import (
    TriageRequest,
    FixRequest,
    MessageRequest,
    TrackedIssue,
    TriageResult,
)
from app.store import get_tracked_issue, upsert_tracked_issue, get_all_tracked_issues

router = APIRouter()

DEVIN_API_BASE = "https://api.devin.ai/v1"


def _devin_headers() -> dict[str, str]:
    token = os.environ.get("DEVIN_API_KEY", "")
    if not token:
        raise HTTPException(
            status_code=503,
            detail="DEVIN_API_KEY is not configured. Please set it in the backend .env file.",
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


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


@router.post("/triage")
async def create_triage_session(request: TriageRequest):
    """Create a Devin session to triage a GitHub issue."""
    headers = _devin_headers()

    prompt = TRIAGE_PROMPT_TEMPLATE.format(
        issue_number=request.issue_number,
        repo=request.repo,
        title=request.title,
        body=request.body or "(no description provided)",
    )

    payload = {
        "prompt": prompt,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{DEVIN_API_BASE}/sessions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Devin API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach Devin API: {str(e)}",
            )

    data = resp.json()
    session_id = data.get("session_id", "")
    devin_url = data.get("url", "")

    # Track the issue
    tracked = get_tracked_issue(request.repo, request.issue_number)
    if tracked:
        tracked.triage_session_id = session_id
        tracked.triage_status = "running"
        tracked.devin_url = devin_url
    else:
        tracked = TrackedIssue(
            issue_number=request.issue_number,
            repo=request.repo,
            title=request.title,
            triage_session_id=session_id,
            triage_status="running",
            devin_url=devin_url,
        )
    upsert_tracked_issue(tracked)

    return {
        "session_id": session_id,
        "url": devin_url,
        "status": "running",
    }


@router.get("/sessions/{session_id}")
async def get_session_status(session_id: str):
    """Poll the status of a Devin session."""
    headers = _devin_headers()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{DEVIN_API_BASE}/session/{session_id}",
                headers=headers,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Devin API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach Devin API: {str(e)}",
            )

    return resp.json()


@router.post("/sessions/{session_id}/message")
async def send_session_message(session_id: str, request: MessageRequest):
    """Send a follow-up message to a Devin session."""
    headers = _devin_headers()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{DEVIN_API_BASE}/session/{session_id}/message",
                headers=headers,
                json={"message": request.message},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Devin API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach Devin API: {str(e)}",
            )

    return resp.json()


@router.post("/fix")
async def create_fix_session(request: FixRequest):
    """Create a Devin session to fix a GitHub issue."""
    headers = _devin_headers()

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

    payload = {
        "prompt": prompt,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{DEVIN_API_BASE}/sessions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Devin API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach Devin API: {str(e)}",
            )

    data = resp.json()
    session_id = data.get("session_id", "")
    devin_url = data.get("url", "")

    # Track the issue
    tracked = get_tracked_issue(request.repo, request.issue_number)
    if tracked:
        tracked.fix_session_id = session_id
        tracked.fix_status = "running"
        tracked.devin_url = devin_url
    else:
        tracked = TrackedIssue(
            issue_number=request.issue_number,
            repo=request.repo,
            title=request.title,
            fix_session_id=session_id,
            fix_status="running",
            devin_url=devin_url,
        )
    upsert_tracked_issue(tracked)

    return {
        "session_id": session_id,
        "url": devin_url,
        "status": "running",
    }


def _parse_triage_json(text: str) -> dict | None:
    """Try to extract a JSON object from Devin's response text."""
    # Try direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    if not text:
        return None

    # Try to find JSON in code fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any JSON object
    brace_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


@router.post("/sessions/{session_id}/sync")
async def sync_session(session_id: str):
    """Sync session status and extract triage results or PR URL."""
    headers = _devin_headers()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{DEVIN_API_BASE}/session/{session_id}",
                headers=headers,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Devin API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach Devin API: {str(e)}",
            )

    session_data = resp.json()
    status = session_data.get("status_enum", "running")

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
        return {"status": status, "session_data": session_data}

    if is_triage:
        tracked.triage_status = status

        # Try to parse triage result from structured output or conversation
        if status == "finished":
            structured = session_data.get("structured_output")
            if structured:
                parsed = _parse_triage_json(
                    json.dumps(structured) if isinstance(structured, dict) else str(structured)
                )
                if parsed:
                    try:
                        tracked.triage_result = TriageResult(**parsed)
                    except Exception:
                        pass

            # If no structured output, check last message
            if not tracked.triage_result:
                last_text = _get_last_assistant_text(session_data)
                if last_text:
                    parsed = _parse_triage_json(last_text)
                    if parsed:
                        try:
                            tracked.triage_result = TriageResult(**parsed)
                        except Exception:
                            pass
    else:
        tracked.fix_status = status

        # Try to extract PR URL from structured output or conversation
        if status == "finished":
            structured = session_data.get("structured_output")
            if structured and isinstance(structured, dict):
                pr_url = structured.get("pr_url") or structured.get("pull_request_url")
                if pr_url:
                    tracked.pr_url = pr_url

            if not tracked.pr_url:
                last_text = _get_last_assistant_text(session_data)
                if last_text:
                    pr_match = re.search(
                        r"https://github\.com/[^\s]+/pull/\d+", last_text
                    )
                    if pr_match:
                        tracked.pr_url = pr_match.group(0)

    upsert_tracked_issue(tracked)

    return {
        "status": status,
        "tracked_issue": tracked.model_dump(),
        "session_data": session_data,
    }


def _get_last_assistant_text(session_data: dict) -> str | None:
    """Extract the last assistant/Devin message text from session data."""
    conversation = session_data.get("conversation", [])
    if not conversation:
        return None

    for msg in reversed(conversation):
        role = msg.get("role", "")
        if role in ("assistant", "devin"):
            return msg.get("content", "") or msg.get("text", "")
    return None


@router.get("/tracked")
async def list_tracked_issues():
    """List all tracked issues."""
    return [issue.model_dump() for issue in get_all_tracked_issues()]

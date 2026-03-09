"""
Dedicated service module for Devin API calls.

Keeps all HTTP interaction with the Devin API in one place so the rest of
the app never touches raw requests/responses directly.  Every call logs
the outgoing request and incoming response for easy debugging.

TODO: Replace DEVIN_API_BASE if Devin ever ships a v2 endpoint.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("backlog_pilot.devin_api")

# TODO: Update this if the Devin API base URL changes.
DEVIN_API_BASE = "https://api.devin.ai/v1"

# TODO: Set DEVIN_API_KEY in backend/.env before using triage or fix features.
_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    """Return the configured API key or raise with a clear message."""
    key = os.environ.get("DEVIN_API_KEY", "").strip()
    if not key:
        raise DevinAPIError(
            "DEVIN_API_KEY is not configured. Please set it in the backend .env file.",
            status_code=503,
        )
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class DevinAPIError(Exception):
    """Raised when the Devin API returns an error or is unreachable."""

    def __init__(self, message: str, status_code: int = 502, raw_response: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.raw_response = raw_response


# ---------------------------------------------------------------------------
# Response wrapper  (keeps raw data available for inspection)
# ---------------------------------------------------------------------------

@dataclass
class DevinSessionResponse:
    """Thin wrapper around the JSON returned by the Devin sessions API.

    We store the full raw dict so callers can inspect any field, even ones
    we haven't explicitly modelled yet.
    """

    raw: dict[str, Any]

    # Convenience accessors ------------------------------------------------
    # TODO: Verify these field names against the latest Devin API docs.
    #       If the API changes its schema these are the only places to update.

    @property
    def session_id(self) -> str:
        return self.raw.get("session_id", "")

    @property
    def url(self) -> str:
        """The Devin web UI link for this session."""
        return self.raw.get("url", "")

    @property
    def status(self) -> str:
        """Session status.  Known values: running, finished, failed, stopped, blocked."""
        # TODO: The field name may be "status" or "status_enum" depending on
        #       the endpoint.  We check both and prefer status_enum.
        return self.raw.get("status_enum", self.raw.get("status", "unknown"))

    @property
    def structured_output(self) -> Any | None:
        """Structured output attached to the session, if any."""
        return self.raw.get("structured_output")

    @property
    def conversation(self) -> list[dict[str, Any]]:
        """Full conversation history between user and Devin.

        The Devin API returns this as 'messages' in the session response.
        Each message has 'type' (e.g. 'devin_message', 'initial_user_message')
        and 'message' (the text content).
        """
        return self.raw.get("messages", self.raw.get("conversation", []))


# ---------------------------------------------------------------------------
# Core API calls
# ---------------------------------------------------------------------------

async def create_session(prompt: str) -> DevinSessionResponse:
    """POST /sessions  -- create a new Devin session.

    Returns a DevinSessionResponse wrapping the raw API response.
    """
    payload = {"prompt": prompt}

    logger.info("Creating Devin session (prompt length=%d chars)", len(prompt))
    logger.debug("Session payload: %s", json.dumps(payload, indent=2)[:500])

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{DEVIN_API_BASE}/sessions",
                headers=_headers(),
                json=payload,
            )
        except httpx.RequestError as exc:
            logger.error("Failed to reach Devin API: %s", exc)
            raise DevinAPIError(f"Failed to reach Devin API: {exc}") from exc

        logger.info("Devin create-session responded %d", resp.status_code)
        logger.debug("Response body: %s", resp.text[:1000])

        if not resp.is_success:
            raise DevinAPIError(
                f"Devin API error ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                raw_response=resp.text,
            )

    return DevinSessionResponse(raw=resp.json())


async def get_session(session_id: str) -> DevinSessionResponse:
    """GET /session/{session_id}  -- poll session status.

    Returns a DevinSessionResponse wrapping the raw API response.
    """
    logger.info("Polling Devin session %s", session_id)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(
                f"{DEVIN_API_BASE}/session/{session_id}",
                headers=_headers(),
            )
        except httpx.RequestError as exc:
            logger.error("Failed to reach Devin API: %s", exc)
            raise DevinAPIError(f"Failed to reach Devin API: {exc}") from exc

        logger.info("Devin get-session responded %d (session=%s)", resp.status_code, session_id)
        logger.debug("Response body: %s", resp.text[:2000])

        if not resp.is_success:
            raise DevinAPIError(
                f"Devin API error ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                raw_response=resp.text,
            )

    return DevinSessionResponse(raw=resp.json())


async def send_message(session_id: str, message: str) -> DevinSessionResponse:
    """POST /session/{session_id}/message  -- send follow-up to Devin."""
    logger.info("Sending message to session %s (length=%d)", session_id, len(message))

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{DEVIN_API_BASE}/session/{session_id}/message",
                headers=_headers(),
                json={"message": message},
            )
        except httpx.RequestError as exc:
            logger.error("Failed to reach Devin API: %s", exc)
            raise DevinAPIError(f"Failed to reach Devin API: {exc}") from exc

        logger.info("Devin send-message responded %d", resp.status_code)

        if not resp.is_success:
            raise DevinAPIError(
                f"Devin API error ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                raw_response=resp.text,
            )

    return DevinSessionResponse(raw=resp.json())


# ---------------------------------------------------------------------------
# Result extraction helpers
# ---------------------------------------------------------------------------

def parse_triage_json(text: str) -> dict[str, Any] | None:
    """Try to extract a triage-result JSON object from Devin's response text.

    Attempts, in order:
      1. Direct JSON parse of the whole string.
      2. JSON inside a fenced code block (```json ... ```).
      3. First top-level {...} substring.
    """
    if not text:
        return None

    # 1) Direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            logger.debug("Parsed triage JSON directly")
            return obj
    except (json.JSONDecodeError, TypeError):
        pass

    # 2) Fenced code block
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            obj = json.loads(fenced.group(1))
            logger.debug("Parsed triage JSON from fenced block")
            return obj
        except json.JSONDecodeError:
            pass

    # 3) First bare JSON object (brace-counting to handle nested braces)
    start = text.find("{")
    if start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        logger.debug("Parsed triage JSON from bare braces")
                        return obj
                    except json.JSONDecodeError:
                        break

    logger.warning("Could not extract triage JSON from response text (length=%d)", len(text))
    return None


def get_last_assistant_text(session: DevinSessionResponse) -> str | None:
    """Return the text content of the last assistant/devin message.

    The Devin API uses 'type' (not 'role') and 'message' (not 'content').
    Known types: 'devin_message', 'initial_user_message', 'user_message'.
    """
    for msg in reversed(session.conversation):
        msg_type = msg.get("type", "")
        role = msg.get("role", "")
        # Match Devin messages by type (preferred) or role (legacy fallback)
        if msg_type == "devin_message" or role in ("assistant", "devin"):
            text = msg.get("message", "") or msg.get("content", "") or msg.get("text", "")
            if text:
                return text
    return None


def extract_pr_url(text: str) -> str | None:
    """Pull the first GitHub PR URL out of a text blob."""
    match = re.search(r"https://github\.com/[^\s)\"']+/pull/\d+", text)
    if match:
        logger.debug("Extracted PR URL: %s", match.group(0))
        return match.group(0)
    return None

from pydantic import BaseModel, field_validator
from typing import Optional
from enum import Enum


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TriageResult(BaseModel):
    """Structured triage output returned by Devin via structured_output.

    All fields are optional with sensible defaults so that a partial response
    from Devin still creates a valid object.
    """

    issue_summary: str = ""
    likely_area: str = ""
    suspected_files: list[str] = []
    difficulty: Difficulty = Difficulty.MEDIUM
    safe_to_autofix: bool = False
    needs_human_clarification: bool = False
    acceptance_criteria: list[str] = []
    recommended_next_step: str = ""

    # ------------------------------------------------------------------
    # Backward-compat with old schema fields so in-flight sessions
    # created before this change still parse.
    # ------------------------------------------------------------------
    severity: Optional[str] = None
    category: Optional[str] = None
    estimated_effort: Optional[str] = None
    summary: Optional[str] = None
    suggested_approach: Optional[str] = None
    can_auto_fix: Optional[bool] = None

    @field_validator("difficulty", mode="before")
    @classmethod
    def _coerce_difficulty(cls, v: object) -> str:
        """Accept common synonyms so Devin doesn't have to be exact."""
        if isinstance(v, str):
            mapping = {
                "easy": "easy",
                "simple": "easy",
                "low": "easy",
                "medium": "medium",
                "moderate": "medium",
                "hard": "hard",
                "difficult": "hard",
                "complex": "hard",
                "high": "hard",
            }
            return mapping.get(v.lower().strip(), v)
        return v  # type: ignore[return-value]

    @property
    def display_summary(self) -> str:
        """Best-effort summary, falling back to old schema field."""
        return self.issue_summary or self.summary or ""

    @property
    def display_approach(self) -> str:
        """Best-effort approach, falling back to old schema field."""
        return self.recommended_next_step or self.suggested_approach or ""

    @property
    def display_autofix(self) -> bool:
        """Whether Devin thinks it can auto-fix this issue."""
        if self.safe_to_autofix:
            return True
        if self.can_auto_fix is not None:
            return self.can_auto_fix
        return False


class TrackedIssue(BaseModel):
    issue_number: int
    repo: str
    title: str
    triage_session_id: Optional[str] = None
    triage_status: Optional[str] = None
    triage_result: Optional[TriageResult] = None
    fix_session_id: Optional[str] = None
    fix_status: Optional[str] = None
    pr_url: Optional[str] = None
    devin_url: Optional[str] = None


class TriageRequest(BaseModel):
    repo: str
    issue_number: int
    title: str
    body: str


class FixRequest(BaseModel):
    repo: str
    issue_number: int
    title: str
    body: str
    triage_result: Optional[TriageResult] = None


class MessageRequest(BaseModel):
    message: str

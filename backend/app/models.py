from pydantic import BaseModel
from typing import Optional
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    REFACTOR = "refactor"
    DOCS = "docs"
    INFRA = "infra"


class Effort(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class TriageResult(BaseModel):
    severity: Severity
    category: Category
    estimated_effort: Effort
    summary: str
    suggested_approach: str
    can_auto_fix: bool


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

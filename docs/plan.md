# Backlog Pilot - Implementation Plan

## Product Overview

Backlog Pilot automates GitHub issue triage and resolution using the Devin API. It ingests stale issues from a GitHub repo, lets users trigger AI-powered triage, displays structured results, and allows users to approve issues for autonomous fixing via Devin sessions.

## User Flow

1. **Configure** - User enters GitHub repo (owner/repo)
2. **Browse Issues** - See a list of open GitHub issues from the configured repo
3. **Triage** - Click "Run Triage" on an issue to start a Devin triage session
4. **Review Triage** - See structured triage output (8 fields: summary, difficulty, suspected files, acceptance criteria, etc.)
5. **Approve Fix** - Click "Approve for Fix" to start a Devin session that works on the issue
6. **Track Progress** - Auto-polling updates status every 15 seconds (running, blocked, completed, failed)
7. **View PR** - See the PR link when Devin completes the fix

## Architecture

```
┌─────────────────┐       ┌──────────────────────┐
│   Next.js 14    │       │   FastAPI Backend     │
│   Frontend      │──────>│   (Python)            │
│   (React +      │ REST  │                       │
│    Tailwind)    │<──────│   /api/github/*       │
│   :3000         │       │   /api/devin/*        │
└─────────────────┘       │   :8000               │
                          └──────────┬────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
              ┌─────v────┐    ┌─────v─────┐   ┌─────v─────┐
              │ GitHub   │    │ Devin     │   │ In-Memory │
              │ REST API │    │ API v1    │   │ Store     │
              └──────────┘    └───────────┘   └───────────┘
```

### Stack

| Layer     | Technology                        | Rationale                          |
|-----------|-----------------------------------|------------------------------------|
| Frontend  | Next.js 14 (App Router) + React   | Fast to build, SSR-capable         |
| Styling   | Tailwind CSS                      | Rapid UI development               |
| Backend   | FastAPI (Python 3.12 + Poetry)    | Async, type-safe, easy to deploy   |
| State     | In-memory dict (server-side)      | Simple MVP, no DB required         |
| APIs      | GitHub REST API + Devin REST API  | Real integrations                  |
| Language  | TypeScript (FE) + Python (BE)     | Type safety on both sides          |

### API Endpoints

| Route                                  | Method | Description                          |
|----------------------------------------|--------|--------------------------------------|
| `GET /api/github/issues?repo=o/r`     | GET    | Fetch issues from configured repo    |
| `POST /api/devin/triage`              | POST   | Create a Devin triage session        |
| `POST /api/devin/fix`                 | POST   | Create a Devin fix session           |
| `GET /api/devin/sessions/{id}`        | GET    | Get raw session status               |
| `POST /api/devin/sessions/{id}/sync`  | POST   | Sync status & extract results        |
| `POST /api/devin/sessions/{id}/message` | POST | Send follow-up message to session  |
| `GET /api/devin/tracked`              | GET    | List all tracked issues              |

### Key Data Models

```python
# Structured triage schema (8 fields)
class TriageResult(BaseModel):
    issue_summary: str = ""
    likely_area: str = ""
    suspected_files: list[str] = []
    difficulty: Difficulty = Difficulty.MEDIUM  # easy | medium | hard
    safe_to_autofix: bool = False
    needs_human_clarification: bool = False
    acceptance_criteria: list[str] = []
    recommended_next_step: str = ""

# Issue with triage/fix state
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
```

## File Structure

```
backlog-pilot/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point + CORS
│   │   ├── models.py           # Pydantic data models
│   │   ├── store.py            # In-memory state store
│   │   ├── routes/
│   │   │   ├── github.py       # GitHub API proxy routes
│   │   │   └── devin.py        # Devin API integration + prompt templates
│   │   └── services/
│   │       └── devin_api.py    # Devin HTTP client, response wrapper, helpers
│   ├── .env.example
│   └── pyproject.toml
├── frontend/                   # Next.js frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx        # Main dashboard + auto-polling logic
│   │   │   ├── layout.tsx      # Root layout
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── header.tsx      # Header + demo mode banner
│   │   │   ├── config-banner.tsx
│   │   │   ├── repo-input.tsx
│   │   │   ├── issue-card.tsx  # Issue card with triage/fix controls
│   │   │   └── issue-list.tsx
│   │   └── lib/
│   │       ├── api.ts          # Backend API client
│   │       └── types.ts        # TypeScript types + accessor helpers
│   ├── .env.example
│   └── package.json
└── docs/
    ├── plan.md                 # Architecture & implementation plan
    ├── prompts.md              # Triage & fix prompt templates
    └── triage-schema.md        # Structured triage schema reference
```

## Key Features

### Auto-polling
When a triage or fix session is running, the dashboard auto-refreshes every 15 seconds. Polling stops automatically when the session reaches a terminal state (finished, failed, stopped) or when the expected result (triage_result or pr_url) is extracted.

### Structured Triage Schema
Triage sessions use Devin's structured_output field with an 8-field JSON schema. The backend extracts results from both structured_output and conversation text, with progressive extraction (partial results update as Devin works).

### Session State Recovery
When the backend restarts (e.g., dev-mode file watcher), in-memory state is lost. The sync endpoint reconstructs a minimal TrackedIssue from the Devin API response, allowing the frontend to recover PR URLs and triage results.

### Defensive Extraction
- Difficulty enum accepts synonyms ("simple" -> "easy", "complex" -> "hard") and defaults unrecognized values to "medium"
- JSON parser handles fenced code blocks, bare JSON, and nested braces
- User-controlled fields (issue body/title) are escaped before str.format() to prevent crashes on curly braces

## Devin API Integration

### 1. Create Triage Session
```
POST https://api.devin.ai/v1/sessions
Body: { prompt: "<triage prompt with 8-field schema>" }
Headers: { Authorization: "Bearer {DEVIN_API_KEY}" }
Response: { session_id, url, status }
```

### 2. Create Fix Session
```
POST https://api.devin.ai/v1/sessions
Body: { prompt: "<fix prompt with triage context + guardrails>" }
Headers: { Authorization: "Bearer {DEVIN_API_KEY}" }
Response: { session_id, url, status }
```

### 3. Poll Session Status
```
GET https://api.devin.ai/v1/session/{session_id}
Headers: { Authorization: "Bearer {DEVIN_API_KEY}" }
Response: { status_enum, structured_output, messages, ... }
```

### 4. Send Follow-up Message
```
POST https://api.devin.ai/v1/session/{session_id}/message
Body: { message: "..." }
Headers: { Authorization: "Bearer {DEVIN_API_KEY}" }
```

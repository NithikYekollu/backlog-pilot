# Backlog Pilot - Implementation Plan

## Product Overview

Backlog Pilot automates GitHub issue triage and resolution using the Devin API. It ingests stale issues from a GitHub repo, lets users trigger AI-powered triage, displays structured results, and allows users to approve issues for autonomous fixing via Devin sessions.

## User Flow

1. **Configure** - User enters GitHub repo (owner/repo) and API keys
2. **Browse Issues** - See a list of open GitHub issues from the configured repo
3. **Triage** - Click "Run Triage" on an issue to start a Devin triage session
4. **Review Triage** - See structured triage output (severity, category, estimated effort, suggested approach)
5. **Approve Fix** - Click "Approve for Fix" to start a Devin session that works on the issue
6. **Track Progress** - See Devin session status (running, completed, failed)
7. **View PR** - See the PR link when Devin completes the fix

## Architecture

```
┌─────────────────────────────────────┐
│           Next.js App               │
│  ┌───────────┐  ┌────────────────┐  │
│  │  Frontend  │  │  API Routes    │  │
│  │  (React +  │──│  /api/github/* │  │
│  │  Tailwind) │  │  /api/devin/*  │  │
│  └───────────┘  └────────┬───────┘  │
│                          │          │
└──────────────────────────┼──────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼────┐ ┌────▼─────┐ ┌────▼─────┐
        │ GitHub   │ │ Devin    │ │ In-Memory│
        │ API      │ │ API      │ │ Store    │
        └──────────┘ └──────────┘ └──────────┘
```

### Stack

| Layer     | Technology                        | Rationale                          |
|-----------|-----------------------------------|------------------------------------|
| Frontend  | Next.js 14 (App Router) + React   | Fast to build, SSR, API routes     |
| Styling   | Tailwind CSS + shadcn/ui          | Rapid UI development               |
| Backend   | Next.js API Routes                | No separate server needed          |
| State     | In-memory Map (server-side)       | Simple MVP, no DB required         |
| APIs      | GitHub REST API + Devin REST API  | Real integrations                  |
| Language  | TypeScript                        | Type safety, better DX             |

### API Routes

| Route                          | Method | Description                          |
|--------------------------------|--------|--------------------------------------|
| `/api/github/issues`           | GET    | Fetch issues from configured repo    |
| `/api/devin/triage`            | POST   | Create a Devin triage session        |
| `/api/devin/fix`               | POST   | Create a Devin fix session           |
| `/api/devin/sessions/[id]`     | GET    | Get session status                   |
| `/api/devin/sessions/[id]/message` | POST | Send follow-up message to session |

### Key Data Models

```typescript
// Triage result structure
interface TriageResult {
  severity: 'critical' | 'high' | 'medium' | 'low';
  category: 'bug' | 'feature' | 'refactor' | 'docs' | 'infra';
  estimatedEffort: 'small' | 'medium' | 'large';
  summary: string;
  suggestedApproach: string;
  canAutoFix: boolean;
}

// Issue with triage/fix state
interface TrackedIssue {
  issueNumber: number;
  repo: string;
  triageSessionId?: string;
  triageResult?: TriageResult;
  fixSessionId?: string;
  fixStatus?: 'pending' | 'running' | 'completed' | 'failed';
  prUrl?: string;
}
```

## Implementation Phases

### Phase 1: Scaffold & Config (Current)
- [x] Create Next.js project with TypeScript + Tailwind
- [x] Set up project structure
- [x] Create docs/plan.md and README
- [x] Stub API integration points

### Phase 2: GitHub Integration
- [ ] Implement `/api/github/issues` route
- [ ] Build issue list view with filtering
- [ ] Show issue metadata (labels, age, assignees)

### Phase 3: Devin Triage
- [ ] Implement `/api/devin/triage` route (create session with triage prompt)
- [ ] Build triage UI with loading states
- [ ] Parse and display structured triage results
- [ ] Poll session status until complete

### Phase 4: Devin Fix
- [ ] Implement `/api/devin/fix` route
- [ ] Build "Approve for Fix" flow
- [ ] Session status tracking with polling
- [ ] Display PR URL when available

### Phase 5: Polish
- [ ] Error handling and edge cases
- [ ] Empty states and loading skeletons
- [ ] Configuration UI for API keys
- [ ] Demo-ready styling

## File Structure

```
backlog-pilot/
├── docs/
│   └── plan.md
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── globals.css
│   │   └── api/
│   │       ├── github/
│   │       │   └── issues/route.ts
│   │       └── devin/
│   │           ├── triage/route.ts
│   │           ├── fix/route.ts
│   │           └── sessions/
│   │               └── [id]/
│   │                   ├── route.ts
│   │                   └── message/route.ts
│   ├── components/
│   │   ├── ui/              (shadcn components)
│   │   ├── issue-list.tsx
│   │   ├── issue-card.tsx
│   │   ├── triage-panel.tsx
│   │   ├── session-status.tsx
│   │   ├── config-banner.tsx
│   │   └── header.tsx
│   ├── lib/
│   │   ├── github.ts        (GitHub API client)
│   │   ├── devin.ts          (Devin API client)
│   │   ├── store.ts          (in-memory state)
│   │   └── types.ts          (shared types)
│   └── hooks/
│       └── use-polling.ts
├── .env.example
├── .gitignore
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── README.md
```

## Devin API Integration Points

### 1. Create Triage Session
```
POST https://api.devin.ai/v1/sessions
Body: { prompt: "Triage GitHub issue #{number}: {title}\n\n{body}\n\nProvide structured triage..." }
Headers: { Authorization: "Bearer {DEVIN_API_KEY}" }
```

### 2. Poll Session Status
```
GET https://api.devin.ai/v1/session/{session_id}
Headers: { Authorization: "Bearer {DEVIN_API_KEY}" }
Response: { status, structured_output, ... }
```

### 3. Send Follow-up Message
```
POST https://api.devin.ai/v1/session/{session_id}/message
Body: { message: "..." }
Headers: { Authorization: "Bearer {DEVIN_API_KEY}" }
```

### 4. Create Fix Session
```
POST https://api.devin.ai/v1/sessions
Body: { prompt: "Fix GitHub issue #{number}...", playbook_id?: "..." }
Headers: { Authorization: "Bearer {DEVIN_API_KEY}" }
```

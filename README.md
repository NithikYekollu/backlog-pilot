# Backlog Pilot

AI-powered GitHub issue triage and resolution using the [Devin API](https://docs.devin.ai).

Backlog Pilot ingests open issues from any GitHub repository, lets you trigger AI-powered triage via Devin, displays structured triage results (severity, category, effort, approach), and lets you approve issues for autonomous fixing — all from a single dashboard.

![Architecture](docs/plan.md)

## Stack

| Layer    | Technology              |
|----------|-------------------------|
| Frontend | Next.js 14 (App Router) |
| Styling  | Tailwind CSS            |
| Backend  | FastAPI (Python)        |
| APIs     | GitHub REST + Devin API |
| State    | In-memory (MVP)         |

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)

### 1. Clone the repo

```bash
git clone https://github.com/NithikYekollu/backlog-pilot.git
cd backlog-pilot
```

### 2. Set up the backend

```bash
cd backend

# Install dependencies
poetry install

# Create .env from template
cp .env.example .env

# Edit .env and add your API keys:
# - DEVIN_API_KEY (required for triage/fix)
# - GITHUB_TOKEN (optional, for private repos or higher rate limits)

# Start the backend server
poetry run fastapi dev app/main.py
```

The backend runs at **http://localhost:8000**.

### 3. Set up the frontend

In a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The frontend runs at **http://localhost:3000**.

### 4. Use the app

1. Open http://localhost:3000
2. Enter a GitHub repo (e.g. `facebook/react`)
3. Click **Load Issues** to see open issues
4. Click **Run Triage** on any issue to start a Devin triage session
5. Once triage completes, click **Refresh Status** to see results
6. If Devin says it can auto-fix, click **Approve Fix** to start a fix session
7. Monitor fix progress and see the PR link when complete

## API Keys

| Key | Required | Purpose |
|-----|----------|---------|
| `DEVIN_API_KEY` | Yes (for triage/fix) | Authenticates with the Devin API |
| `GITHUB_TOKEN` | No (public repos work without it) | Higher rate limits, access to private repos |

Without API keys configured, you can still browse issues from public repos. Triage and fix actions will show a clear configuration warning.

## Project Structure

```
backlog-pilot/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── main.py        # FastAPI app entry point
│   │   ├── models.py      # Pydantic data models
│   │   ├── store.py       # In-memory state store
│   │   └── routes/
│   │       ├── github.py   # GitHub API proxy routes
│   │       └── devin.py    # Devin API integration routes
│   ├── .env.example
│   └── pyproject.toml
├── frontend/              # Next.js frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx    # Main dashboard page
│   │   │   ├── layout.tsx  # Root layout
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── header.tsx
│   │   │   ├── config-banner.tsx
│   │   │   ├── repo-input.tsx
│   │   │   ├── issue-card.tsx
│   │   │   └── issue-list.tsx
│   │   └── lib/
│   │       ├── api.ts      # Backend API client
│   │       └── types.ts    # TypeScript types
│   ├── .env.example
│   └── package.json
└── docs/
    └── plan.md            # Architecture & implementation plan
```

## Development

### Backend

```bash
cd backend
poetry run fastapi dev app/main.py  # auto-reload on changes
```

### Frontend

```bash
cd frontend
npm run dev  # auto-reload on changes
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/github/issues?repo=owner/repo` | GET | List issues from a GitHub repo |
| `POST /api/devin/triage` | POST | Start a Devin triage session |
| `POST /api/devin/fix` | POST | Start a Devin fix session |
| `GET /api/devin/sessions/{id}` | GET | Get session status |
| `POST /api/devin/sessions/{id}/message` | POST | Send message to session |
| `POST /api/devin/sessions/{id}/sync` | POST | Sync status & extract results |
| `GET /api/devin/tracked` | GET | List all tracked issues |

## License

MIT

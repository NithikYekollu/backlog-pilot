"""
Backlog Pilot API — FastAPI entry point.

TODO: For production, replace in-memory store with a real database
      and tighten CORS origins.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.routes import github, devin  # noqa: E402

# ---------------------------------------------------------------------------
# Logging — surface useful debug info during development.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet down noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("backlog_pilot")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Backlog Pilot API", version="0.1.0")

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


app.include_router(github.router, prefix="/api/github", tags=["github"])
app.include_router(devin.router, prefix="/api/devin", tags=["devin"])

logger.info("Backlog Pilot API ready")

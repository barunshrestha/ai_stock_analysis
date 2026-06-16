"""FastAPI application entry point.

Run from the repo root (so yahoo_session/scanner/database import correctly):

    ./venv/bin/python -m uvicorn backend.main:app --reload --port 8000

Interactive API docs: http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS
from backend.routers import admin, ai, automation, dca, news, portfolio, search, stocks

app = FastAPI(
    title="AI Stock Analysis API",
    description="Backend for the professional redesign (see PRD.md). "
    "Wraps Yahoo Finance (curl_cffi impersonation), PostgreSQL cache, "
    "the technical scanner, and local Ollama AI.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(news.router)
app.include_router(search.router)
app.include_router(stocks.router)
app.include_router(portfolio.router)
app.include_router(dca.router)
app.include_router(ai.router)
app.include_router(automation.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    from backend.deps import _db_or_none

    return {
        "status": "ok",
        "database": "connected" if _db_or_none() is not None else "unavailable",
    }

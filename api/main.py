"""
Research Intelligence Platform — v1 API entry point.

All routes are mounted under /api/v1/ with CORS enabled for the
Next.js frontend at localhost:3000.

Run:
    cd /path/to/research-intelligence-platfrom
    source .venv/bin/activate
    export DATABASE_URL=sqlite:///research_platform.db
    uvicorn api.main:app --reload --port 8000

Interactive docs: http://127.0.0.1:8000/docs
Existing API:     http://127.0.0.1:8001  (run api.search on a different port)
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import chat, graph, papers, search, stats, techniques

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "Research Intelligence Platform API v1",
    description = (
        "Powers the Research Intelligence Platform UI. "
        "Serves papers, graph data, search, and corpus statistics "
        "extracted from NeurIPS, ICLR, ICML, and other ML conferences."
    ),
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Next.js dev server and any production origin configured via env.
# In production, set CORS_ORIGIN to your deployed frontend URL.

_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_extra = os.getenv("CORS_ORIGIN", "").strip()
if _extra:
    _cors_origins.append(_extra)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = _cors_origins,
    allow_credentials = True,
    allow_methods     = ["GET", "POST", "OPTIONS"],
    allow_headers     = ["*"],
    expose_headers    = ["X-Total-Count"],   # lets the frontend read pagination total
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(stats.router)
app.include_router(papers.router)
app.include_router(search.router)
app.include_router(graph.router)
app.include_router(techniques.router)
app.include_router(chat.router)


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "Research Intelligence Platform API v1",
        "docs":    "/docs",
        "endpoints": [
            "GET  /api/v1/stats",
            "GET  /api/v1/papers",
            "GET  /api/v1/papers/{id}",
            "GET  /api/v1/papers/{id}/related",
            "GET  /api/v1/papers/{id}/graph",
            "POST /api/v1/search",
            "GET  /api/v1/graph",
            "GET  /api/v1/graph/clusters",
            "GET  /api/v1/graph/techniques",
            "GET  /api/v1/techniques",
            "POST /api/v1/chat",
        ],
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
def health():
    from db.session import ping
    db_ok = ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "db":     "connected" if db_ok else "unreachable",
    }

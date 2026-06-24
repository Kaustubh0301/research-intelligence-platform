"""
Research Intelligence Platform — v1 API entry point.

Run locally:
    source .venv/bin/activate
    uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 2

Interactive docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
load_dotenv(override=True)

from search.embeddings import get_index as _get_embedding_index
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import chat, feature_map, graph, papers, search, stats, techniques

# ── App ───────────────────────────────────────────────────────────────────────

_dev_mode = os.getenv("API_DEV_MODE", "").lower() in ("1", "true", "yes")

app = FastAPI(
    title       = "Research Intelligence Platform API v1",
    description = (
        "Powers the Research Intelligence Platform UI. "
        "Serves papers, graph data, search, and corpus statistics "
        "extracted from NeurIPS, ICLR, ICML, and other ML conferences."
    ),
    version     = "1.0.0",
    # Docs only available in dev mode (set API_DEV_MODE=1 locally)
    docs_url    = "/docs"   if _dev_mode else None,
    redoc_url   = "/redoc"  if _dev_mode else None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# CORS_ORIGIN must be set to the exact deployed frontend origin (no trailing slash).
# Example: https://your-project.vercel.app
# When unset, falls back to localhost-only (dev mode).

_cors_origin = os.getenv("CORS_ORIGIN", "").strip()

if _cors_origin:
    _allowed_origins = [_cors_origin]
    _origin_regex    = None
else:
    # Dev: allow any localhost / 127.0.0.1 port
    _allowed_origins = []
    _origin_regex    = r"http://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins      = _allowed_origins,
    allow_origin_regex = _origin_regex,
    allow_credentials  = True,
    allow_methods      = ["GET", "POST", "OPTIONS"],
    allow_headers      = ["*"],
    expose_headers     = ["X-Total-Count"],
)

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def _load_embedding_index() -> None:
    _get_embedding_index().load()


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(stats.router)
app.include_router(papers.router)
app.include_router(search.router)
app.include_router(graph.router)
app.include_router(techniques.router)
app.include_router(chat.router)
app.include_router(feature_map.router)


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

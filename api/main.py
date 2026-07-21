"""Healthcare Revenue Cycle Command Center — FastAPI backend.

Run:
    uvicorn api.main:app --reload            (from the repository root)

Data source: CSV mode by default (data/processed/). Set DATABASE_URL to a
reachable PostgreSQL instance to serve from the star schema instead.

Swagger UI: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import get_store
from api.models.schemas import HealthResponse
from api.routes import claims, decision, kpis, operations, payers

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api.main")

# Origins always allowed so local development works out of the box (Vite dev
# server on :5173, Vite preview on :4173).
DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://127.0.0.1:4173",
]


def _normalize_origin(origin: str) -> str:
    """Strip whitespace and any trailing slash so an origin set via env matches
    the browser's Origin header (which never has a trailing slash)."""
    return origin.strip().rstrip("/")


def build_allowed_origins() -> list[str]:
    """Allowed CORS origins: the local dev defaults plus any deployed frontend
    URL(s) from the FRONTEND_URL environment variable (comma-separated allowed).
    Never returns "*", so credentials stay valid and access is scoped.
    """
    origins = list(DEFAULT_DEV_ORIGINS)
    for part in os.getenv("FRONTEND_URL", "").split(","):
        norm = _normalize_origin(part)
        if norm:
            origins.append(norm)
    # De-duplicate while preserving order
    seen: set[str] = set()
    unique = [o for o in origins if not (o in seen or seen.add(o))]
    return unique

app = FastAPI(
    title="Healthcare Revenue Cycle Command Center API",
    description=(
        "Analytics and work-queue API over a synthetic healthcare revenue "
        "cycle dataset (claims, denials, payments, A/R aging, follow-up "
        "tasks). **All data is synthetic — no PHI.**"
    ),
    version="1.0.0",
)

# CORS: local dev origins + the deployed frontend from FRONTEND_URL (env-based,
# never a wildcard). See build_allowed_origins().
ALLOWED_ORIGINS = build_allowed_origins()
log.info("CORS allowed origins: %s", ALLOWED_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kpis.router)
app.include_router(claims.router)
app.include_router(payers.router)
app.include_router(operations.router)
app.include_router(decision.router)


@app.on_event("startup")
def warm_store() -> None:
    """Load all tables once at startup so first requests are fast."""
    get_store()


@app.get("/", tags=["System"], summary="API landing page")
def root() -> dict:
    """Public landing response so hitting the bare API origin returns a
    professional payload instead of 404. No secrets, no PHI, no paths."""
    return {
        "name": "Healthcare Revenue Cycle Command Center API",
        "status": "ok",
        "data_mode": "synthetic",
        "health": "/health",
        "documentation": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health", response_model=HealthResponse, tags=["System"],
         summary="Liveness check + data source mode")
def health() -> HealthResponse:
    store = get_store()
    return HealthResponse(status="ok", mode=store.mode,
                          tables_loaded=len(store.tables))

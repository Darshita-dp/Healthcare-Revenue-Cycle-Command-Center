"""Healthcare Revenue Cycle Command Center — FastAPI backend.

Run:
    uvicorn api.main:app --reload            (from the repository root)

Data source: CSV mode by default (data/processed/). Set DATABASE_URL to a
reachable PostgreSQL instance to serve from the star schema instead.

Swagger UI: http://localhost:8000/docs
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import get_store
from api.models.schemas import HealthResponse
from api.routes import claims, decision, kpis, operations, payers

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Healthcare Revenue Cycle Command Center API",
    description=(
        "Analytics and work-queue API over a synthetic healthcare revenue "
        "cycle dataset (claims, denials, payments, A/R aging, follow-up "
        "tasks). **All data is synthetic — no PHI.**"
    ),
    version="1.0.0",
)

# CORS for local frontend development (Vite default ports)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
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


@app.get("/health", response_model=HealthResponse, tags=["System"],
         summary="Liveness check + data source mode")
def health() -> HealthResponse:
    store = get_store()
    return HealthResponse(status="ok", mode=store.mode,
                          tables_loaded=len(store.tables))

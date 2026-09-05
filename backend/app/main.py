"""FastAPI application entry point for Reconex."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.analytics import router as analytics_router
from backend.app.api.investigations import router as investigations_router
from backend.app.api.payments import router as payments_router
from backend.app.api.runs import router as runs_router
from backend.app.reconciliation.loader import CSVLoadError
from backend.app.workspace.store import WorkspaceStore

logger = logging.getLogger(__name__)


def create_app(workspace: Optional[WorkspaceStore] = None) -> FastAPI:
    store = workspace or WorkspaceStore.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.workspace = store
        try:
            store.load_data()
        except CSVLoadError as exc:
            logger.warning("CSV data was not loaded at startup: %s", exc)
        store.restore_persisted_runs()
        yield

    app = FastAPI(
        title="Reconex",
        description="AI-assisted Finance Controller for merchant settlement reconciliation",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(runs_router)
    app.include_router(payments_router)
    app.include_router(investigations_router)
    app.include_router(analytics_router)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "Reconex",
            "version": "0.1.0",
            "phase": "Phase 3B - AI Exception Investigation",
            "timestamp": datetime.now().isoformat(),
        }

    return app


app = create_app()

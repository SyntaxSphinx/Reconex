"""FastAPI application entry point for LedgerPilot.

Phase 1: Minimal health-check endpoint only.
"""

from fastapi import FastAPI
from datetime import datetime

app = FastAPI(
    title="LedgerPilot",
    description="AI-assisted Finance Controller for merchant settlement reconciliation",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "LedgerPilot",
        "version": "0.1.0",
        "phase": "Phase 1 - Data Generation",
        "timestamp": datetime.now().isoformat(),
    }

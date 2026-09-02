"""FastAPI application entry point for Reconex.

Minimal health-check endpoint only.
"""

from fastapi import FastAPI
from datetime import datetime

app = FastAPI(
    title="Reconex",
    description="AI-assisted Finance Controller for merchant settlement reconciliation",
    version="0.1.0",
)


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

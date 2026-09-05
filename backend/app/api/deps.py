"""Shared FastAPI dependencies for the API layer."""

from __future__ import annotations

from fastapi import Request

from backend.app.workspace.store import WorkspaceStore


def get_workspace(request: Request) -> WorkspaceStore:
    return request.app.state.workspace

"""Resolve dataset and run-persistence directories for the API workspace."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

# backend/app/workspace/paths.py → project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def project_root() -> Path:
    return _PROJECT_ROOT


def resolve_data_dir(
    env: Optional[Mapping[str, str]] = None,
    root: Optional[Path] = None,
) -> Path:
    """Prefer RECONEX_DATA_DIR, then data/generated if present, else data/sample."""
    source = os.environ if env is None else env
    configured = source.get("RECONEX_DATA_DIR")
    if configured:
        return Path(configured)

    base = root or project_root()
    generated = base / "data" / "generated"
    if (generated / "payments.csv").is_file():
        return generated
    return base / "data" / "sample"


def resolve_runs_dir(
    env: Optional[Mapping[str, str]] = None,
    root: Optional[Path] = None,
) -> Path:
    """Directory for optional persisted run JSON files."""
    source = os.environ if env is None else env
    configured = source.get("RECONEX_RUNS_DIR")
    if configured:
        return Path(configured)
    return (root or project_root()) / "data" / "runs"

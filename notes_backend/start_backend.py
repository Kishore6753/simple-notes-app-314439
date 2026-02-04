#!/usr/bin/env python3
"""
Backend startup bootstrapper.

This project vendors a local virtualenv under ./venv where requirements are installed.
Some container runners may invoke system Python without activating the venv, which
causes import errors (e.g., fastapi not found) and the server never becomes ready.

This script prefers the venv interpreter when present and starts uvicorn with the
correct module path.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _venv_python() -> Path:
    """Return path to venv python if it exists, else an empty Path."""
    base = Path(__file__).resolve().parent
    candidate = base / "venv" / "bin" / "python"
    return candidate if candidate.exists() else Path()


def main() -> int:
    """Start uvicorn with the correct interpreter."""
    base = Path(__file__).resolve().parent

    python = _venv_python()
    if python:
        python_exe = str(python)
    else:
        python_exe = sys.executable

    host = os.getenv("UVICORN_HOST", os.getenv("HOST", "0.0.0.0"))
    port = os.getenv("PORT", "3001")

    # Uvicorn app import path:
    # - we add `src` to PYTHONPATH so `api.main:app` is importable.
    env = dict(os.environ)
    env["PYTHONPATH"] = str(base / "src") + (
        (os.pathsep + env["PYTHONPATH"]) if env.get("PYTHONPATH") else ""
    )

    cmd = [
        python_exe,
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    # If a runner sets UVICORN_WORKERS, respect it.
    workers = env.get("UVICORN_WORKERS")
    if workers and workers.isdigit() and int(workers) > 1:
        cmd += ["--workers", workers]

    # If a runner sets LOG_LEVEL, respect it.
    log_level = env.get("LOG_LEVEL")
    if log_level:
        cmd += ["--log-level", log_level]

    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())

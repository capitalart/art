from __future__ import annotations

"""Utility for structured audit logging.

This module provides the :func:`log_action` helper used by routes to
record user actions in hour-based log files under ``config.LOGS_DIR``.
"""

import contextlib
import fcntl
from pathlib import Path
from datetime import datetime
import os
from typing import Any

import config


_ACTION_DIRS = {
    "upload": "upload",
    "analyse-openai": "analyse-openai",
    "analyse-google": "analyse-google",
    "edits": "edits",
    "finalise": "finalise",
    "lock": "lock",
    "sellbrite-exports": "sellbrite-exports",
}


def strip_binary(obj: Any) -> Any:
    """Recursively remove bytes objects from ``obj`` for safe logging."""
    if isinstance(obj, dict):
        return {
            k: strip_binary(v)
            for k, v in obj.items()
            if not isinstance(v, (bytes, bytearray))
        }
    if isinstance(obj, list):
        return [strip_binary(v) for v in obj if not isinstance(v, (bytes, bytearray))]
    if isinstance(obj, (bytes, bytearray)):
        return f"<{len(obj)} bytes>"
    return obj


def sanitize_blob_data(obj: Any) -> Any:
    """Return ``obj`` with any obvious binary or base64 blobs summarised."""

    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            if k in {"image", "image_url", "image_data", "content"}:
                clean[k] = "<image data>"
            else:
                clean[k] = sanitize_blob_data(v)
        return clean
    if isinstance(obj, list):
        return [sanitize_blob_data(v) for v in obj]
    if isinstance(obj, (bytes, bytearray)):
        return f"<{len(obj)} bytes>"
    if isinstance(obj, str) and len(obj) > 300 and "base64" in obj:
        return "<base64 data>"
    return obj


def _log_path(action: str) -> Path:
    """Return folder path for the given action."""
    folder = _ACTION_DIRS.get(action, action)
    path = config.LOGS_DIR / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_action(
    action: str,
    filename: str,
    user: str | None,
    details: str,
    *,
    status: str = "success",
    error: str | None = None,
) -> None:
    """Append a formatted line to the audit log for ``action``."""

    log_dir = _log_path(action)
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H")
    log_file = log_dir / f"{stamp}.log"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    user_id = user or "unknown"

    parts = [
        timestamp,
        f"user: {user_id}",
        f"action: {action}",
        f"file: {filename}",
        f"status: {status}",
    ]
    if details:
        parts.append(f"detail: {details}")
    if error:
        parts.append(f"error: {error}")
    line = " | ".join(parts)

    with open(log_file, "a", encoding="utf-8") as f:
        with contextlib.suppress(OSError):
            fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line + "\n")

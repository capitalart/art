"""Utilities for tracking and limiting active user sessions."""

from __future__ import annotations

import json
import threading
import datetime
from pathlib import Path
import contextlib
import fcntl

from config import LOGS_DIR

REGISTRY_FILE = LOGS_DIR / "session_registry.json"
_LOCK = threading.Lock()


def _load_registry() -> dict:
    """Load the session registry JSON file."""
    if not REGISTRY_FILE.exists():
        return {}
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            with contextlib.suppress(OSError):
                fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
    except Exception:
        REGISTRY_FILE.unlink(missing_ok=True)
        return {}
    return data


def _save_registry(data: dict) -> None:
    """Safely write the session registry back to disk."""
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(REGISTRY_FILE)


def register_session(username: str, session_id: str) -> bool:
    """Register a session ID for the given user. Return False if limit reached."""
    with _LOCK:
        data = _load_registry()
        sessions = data.get(username, [])
        if len(sessions) >= 5:
            return False
        sessions.append({
            "session_id": session_id,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        data[username] = sessions
        _save_registry(data)
    return True


def remove_session(username: str, session_id: str) -> None:
    """Remove a session entry for ``username``."""
    with _LOCK:
        data = _load_registry()
        if username in data:
            data[username] = [s for s in data[username] if s.get("session_id") != session_id]
            if not data[username]:
                data.pop(username, None)
            _save_registry(data)


def all_sessions() -> dict:
    """Return the entire session registry."""
    with _LOCK:
        return _load_registry()


def is_active(username: str, session_id: str) -> bool:
    """Check if the given session ID is active for ``username``."""
    data = all_sessions()
    return any(s.get("session_id") == session_id for s in data.get(username, []))

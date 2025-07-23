"""Utilities for tracking active user sessions with a device limit."""
from __future__ import annotations

import json
import threading
import datetime
from pathlib import Path
import contextlib
import fcntl

import config

REGISTRY_FILE = config.LOGS_DIR / "session_registry.json"
_LOCK = threading.Lock()
MAX_SESSIONS = 5
TIMEOUT_SECONDS = 7200  # 2 hours


def _load_registry() -> dict:
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_FILE.write_text("{}")
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
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_FILE.with_suffix(".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(REGISTRY_FILE)


def _cleanup_expired(data: dict) -> dict:
    now = datetime.datetime.utcnow()
    changed = False
    for user in list(data.keys()):
        sessions = [
            s
            for s in data[user]
            if now - datetime.datetime.fromisoformat(s["timestamp"]) < datetime.timedelta(seconds=TIMEOUT_SECONDS)
        ]
        if len(sessions) != len(data[user]):
            changed = True
        if sessions:
            data[user] = sessions
        else:
            data.pop(user)
            changed = True
    if changed:
        _save_registry(data)
    return data


def register_session(username: str, session_id: str) -> bool:
    with _LOCK:
        data = _load_registry()
        data = _cleanup_expired(data)
        sessions = data.get(username, [])
        if len(sessions) >= MAX_SESSIONS:
            return False
        sessions.append({"session_id": session_id, "timestamp": datetime.datetime.utcnow().isoformat()})
        data[username] = sessions
        _save_registry(data)
    return True


def remove_session(username: str, session_id: str) -> None:
    with _LOCK:
        data = _load_registry()
        data = _cleanup_expired(data)
        if username in data:
            data[username] = [s for s in data[username] if s.get("session_id") != session_id]
            if not data[username]:
                data.pop(username, None)
        _save_registry(data)


def touch_session(username: str, session_id: str) -> bool:
    with _LOCK:
        data = _load_registry()
        data = _cleanup_expired(data)
        for s in data.get(username, []):
            if s.get("session_id") == session_id:
                s["timestamp"] = datetime.datetime.utcnow().isoformat()
                _save_registry(data)
                return True
    return False


def active_sessions(username: str) -> list[dict]:
    data = _load_registry()
    data = _cleanup_expired(data)
    return data.get(username, [])


def all_sessions() -> dict:
    data = _load_registry()
    data = _cleanup_expired(data)
    return data

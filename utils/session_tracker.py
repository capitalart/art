# utils/session_tracker.py
"""
Utilities for tracking active user sessions with a device limit.

This module provides a thread-safe mechanism for managing a JSON-based
session registry file, enforcing a maximum number of concurrent sessions
per user and handling session timeouts.

INDEX
-----
1.  Imports
2.  Configuration & Constants
3.  Public Session Management Functions
4.  Internal Helper Functions
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import json
import threading
import datetime
import contextlib
import fcntl
import logging

import config

# ===========================================================================
# 2. Configuration & Constants
# ===========================================================================
REGISTRY_FILE = config.SESSION_REGISTRY_FILE
MAX_SESSIONS = config.MAX_SESSIONS
TIMEOUT_SECONDS = config.SESSION_TIMEOUT_SECONDS

_LOCK = threading.Lock()
logger = logging.getLogger(__name__)


# ===========================================================================
# 3. Public Session Management Functions
# ===========================================================================

def register_session(username: str, session_id: str) -> bool:
    """
    Registers a new session for a user, respecting the MAX_SESSIONS limit.

    Args:
        username: The user for whom to register the session.
        session_id: The unique identifier for the new session.

    Returns:
        True if the session was registered successfully, False if the limit was reached.
    """
    with _LOCK:
        data = _load_registry()
        data = _cleanup_expired(data)
        sessions = data.get(username, [])
        if len(sessions) >= MAX_SESSIONS:
            logger.warning(f"Session registration denied for '{username}': limit of {MAX_SESSIONS} reached.")
            return False
        
        sessions.append({
            "session_id": session_id,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        data[username] = sessions
        _save_registry(data)
        logger.info(f"Registered new session {session_id} for user '{username}'.")
    return True


def remove_session(username: str, session_id: str) -> None:
    """Removes a specific session for a user."""
    with _LOCK:
        data = _load_registry()
        if username in data:
            original_count = len(data[username])
            data[username] = [s for s in data[username] if s.get("session_id") != session_id]
            if not data[username]:
                del data[username]
            
            if len(data.get(username, [])) < original_count:
                logger.info(f"Removed session {session_id} for user '{username}'.")
                _save_registry(data)


def touch_session(username: str, session_id: str) -> bool:
    """
    Updates the timestamp of an active session to keep it alive.

    Returns:
        True if the session was found and touched, False if it was expired or not found.
    """
    with _LOCK:
        data = _load_registry()
        data = _cleanup_expired(data)
        for s in data.get(username, []):
            if s.get("session_id") == session_id:
                s["timestamp"] = datetime.datetime.utcnow().isoformat()
                _save_registry(data)
                return True
    logger.warning(f"Attempted to touch an invalid or expired session '{session_id}' for user '{username}'.")
    return False


def active_sessions(username: str) -> list[dict]:
    """Returns a list of all active sessions for a given user."""
    data = _load_registry()
    return _cleanup_expired(data).get(username, [])


def all_sessions() -> dict:
    """Returns a dictionary of all active sessions for all users."""
    data = _load_registry()
    return _cleanup_expired(data)


# ===========================================================================
# 4. Internal Helper Functions
# ===========================================================================

def _load_registry() -> dict:
    """Loads the session registry JSON file safely."""
    if not REGISTRY_FILE.exists():
        return {}
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            with contextlib.suppress(OSError): # fcntl may fail on some systems
                fcntl.flock(f, fcntl.LOCK_SH)
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Could not read session registry file at {REGISTRY_FILE}: {e}")
        return {}


def _save_registry(data: dict) -> None:
    """Saves the session registry data to its JSON file atomically."""
    tmp_path = REGISTRY_FILE.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_path.replace(REGISTRY_FILE)
    except IOError as e:
        logger.error(f"Could not write to session registry file at {REGISTRY_FILE}: {e}")


def _cleanup_expired(data: dict) -> dict:
    """Removes sessions that have exceeded the timeout duration."""
    now = datetime.datetime.utcnow()
    changed = False
    for user in list(data.keys()):
        active_user_sessions = [
            s for s in data[user]
            if now - datetime.datetime.fromisoformat(s["timestamp"]) < datetime.timedelta(seconds=TIMEOUT_SECONDS)
        ]
        if len(active_user_sessions) != len(data[user]):
            changed = True
        
        if active_user_sessions:
            data[user] = active_user_sessions
        else:
            del data[user]
            changed = True
            
    if changed:
        logger.info("Cleaned up expired sessions from registry.")
        _save_registry(data)
    return data
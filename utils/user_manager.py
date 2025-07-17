"""Simple user management helpers for the admin interface."""

from __future__ import annotations

import json
from pathlib import Path

import config

USERS_FILE = Path("settings/users.json")
DEFAULT_USERS = [{"username": config.ADMIN_USERNAME, "role": "admin"}]


def load_users() -> list[dict]:
    """Return the list of users from the settings file."""
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except Exception:
            pass
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(DEFAULT_USERS, indent=2))
    return DEFAULT_USERS.copy()


def save_users(users: list[dict]) -> None:
    """Persist a list of user dictionaries."""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))


def add_user(username: str, role: str = "user") -> None:
    """Add a new user if it doesn't already exist."""
    users = load_users()
    if any(u["username"] == username for u in users):
        return
    users.append({"username": username, "role": role})
    save_users(users)


def delete_user(username: str) -> None:
    """Remove a user entry by username."""
    users = [u for u in load_users() if u["username"] != username]
    save_users(users)


def set_role(username: str, role: str) -> None:
    """Update the role for an existing user."""
    users = load_users()
    for u in users:
        if u["username"] == username:
            u["role"] = role
            break
    save_users(users)

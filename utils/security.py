"""Utility helpers for login requirement toggle."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta

SETTINGS_FILE = Path("settings/security_settings.json")

DEFAULTS = {"login_required": True, "expires": None}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    SETTINGS_FILE.write_text(json.dumps(DEFAULTS))
    return DEFAULTS.copy()


def save_settings(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data))


def login_required_enabled() -> bool:
    data = load_settings()
    if not data.get("login_required"):
        exp = data.get("expires")
        if exp and datetime.fromisoformat(exp) <= datetime.utcnow():
            data["login_required"] = True
            data["expires"] = None
            save_settings(data)
    return data.get("login_required", True)


def disable_login_for(minutes: int) -> None:
    data = load_settings()
    data["login_required"] = False
    data["expires"] = (datetime.utcnow() + timedelta(minutes=minutes)).isoformat()
    save_settings(data)


def enable_login() -> None:
    data = load_settings()
    data["login_required"] = True
    data["expires"] = None
    save_settings(data)


def remaining_minutes() -> int | None:
    data = load_settings()
    exp = data.get("expires")
    if exp:
        delta = datetime.fromisoformat(exp) - datetime.utcnow()
        return max(int(delta.total_seconds() // 60), 0)
    return None

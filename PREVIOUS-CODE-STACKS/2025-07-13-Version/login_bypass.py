from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

import config

STATE_FILE = config.LOGS_DIR / "login_bypass_state.json"
HISTORY_LOG = config.LOGS_DIR / "login_bypass_history.log"


def enable(seconds: int) -> None:
    """Enable login bypass for the given number of seconds."""
    expires = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"expires": expires.isoformat()}))
    with open(HISTORY_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.utcnow().isoformat()}\tENABLE\t{seconds}\n")


def disable() -> None:
    """Disable login bypass."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    with open(HISTORY_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.utcnow().isoformat()}\tDISABLE\n")


def _load_expiry() -> datetime.datetime | None:
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text())
        return datetime.datetime.fromisoformat(data["expires"])
    except Exception:
        STATE_FILE.unlink()
        return None


def get_remaining() -> int:
    """Return remaining seconds of bypass, or 0 if inactive."""
    expiry = _load_expiry()
    if not expiry:
        return 0
    remaining = (expiry - datetime.datetime.utcnow()).total_seconds()
    if remaining <= 0:
        STATE_FILE.unlink()
        return 0
    return int(math.ceil(remaining))


def is_active() -> bool:
    return get_remaining() > 0


def remaining_str() -> str:
    secs = get_remaining()
    if secs <= 0:
        return ""
    td = datetime.timedelta(seconds=secs)
    return str(td).split(".")[0]

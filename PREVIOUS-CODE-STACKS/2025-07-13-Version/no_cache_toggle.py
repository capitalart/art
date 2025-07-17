from __future__ import annotations

import datetime
import json

import config

STATE_FILE = config.LOGS_DIR / "forced_no_cache_state.json"
HISTORY_LOG = config.LOGS_DIR / "forced_no_cache_history.log"


def enable() -> None:
    """Enable forced no-cache globally for 2 hours."""
    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"expires": expires.isoformat()}))
    with open(HISTORY_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.utcnow().isoformat()}\tENABLED\n")


def disable() -> None:
    """Disable forced no-cache."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    with open(HISTORY_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.utcnow().isoformat()}\tDISABLED\n")


def _load_expiry() -> datetime.datetime | None:
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text())
        return datetime.datetime.fromisoformat(data.get("expires", ""))
    except Exception:
        STATE_FILE.unlink()
        return None


def is_enabled() -> bool:
    expiry = _load_expiry()
    if not expiry:
        return False
    if datetime.datetime.utcnow() >= expiry:
        STATE_FILE.unlink()
        with open(HISTORY_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.utcnow().isoformat()}\tAUTO-OFF\n")
        return False
    return True


def remaining_str() -> str:
    expiry = _load_expiry()
    if not expiry:
        return ""
    remaining = (expiry - datetime.datetime.utcnow()).total_seconds()
    if remaining <= 0:
        return ""
    return str(datetime.timedelta(seconds=int(remaining))).split(".")[0]

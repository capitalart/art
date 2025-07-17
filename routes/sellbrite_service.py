"""Sellbrite API integration utilities."""

from __future__ import annotations

import base64
import logging
import os
from typing import Dict

import requests
from flask import Blueprint, jsonify
from dotenv import load_dotenv

load_dotenv()

SELLBRITE_TOKEN = os.getenv("SELLBRITE_TOKEN")
SELLBRITE_SECRET = os.getenv("SELLBRITE_SECRET")
API_BASE = "https://api.sellbrite.com/v1"

logger = logging.getLogger(__name__)

bp = Blueprint("sellbrite", __name__)


def _auth_header() -> Dict[str, str]:
    """Return the HTTP Authorization header for Sellbrite."""
    if not SELLBRITE_TOKEN or not SELLBRITE_SECRET:
        logger.error("Sellbrite credentials not configured")
        return {}
    creds = f"{SELLBRITE_TOKEN}:{SELLBRITE_SECRET}".encode("utf-8")
    encoded = base64.b64encode(creds).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}


def test_sellbrite_connection() -> bool:
    """Attempt a simple authenticated request to verify credentials."""
    url = f"{API_BASE}/products"
    try:
        resp = requests.get(url, headers=_auth_header(), timeout=10)
    except requests.RequestException as exc:
        logger.error("Sellbrite connection error: %s", exc)
        return False
    if resp.status_code == 200:
        logger.info("Sellbrite authentication succeeded")
        return True
    logger.error(
        "Sellbrite authentication failed: %s %s", resp.status_code, resp.text
    )
    return False


@bp.route("/sellbrite/test")
def sellbrite_test():
    """Flask route demonstrating a simple API connectivity check."""
    success = test_sellbrite_connection()
    status = 200 if success else 500
    return jsonify({"success": success}), status


if __name__ == "__main__":
    ok = test_sellbrite_connection()
    print("Connection successful" if ok else "Connection failed")

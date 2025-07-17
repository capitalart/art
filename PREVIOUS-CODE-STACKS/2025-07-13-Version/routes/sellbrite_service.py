"""Sellbrite API integration utilities."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from utils.sellbrite_api import SellbriteAPI

bp = Blueprint("sellbrite", __name__)
logger = logging.getLogger(__name__)
try:
    sb_api = SellbriteAPI()
except RuntimeError:
    sb_api = None


@bp.route("/sellbrite/test")
def sellbrite_test():
    """Flask route demonstrating a simple API connectivity check."""
    if sb_api is None:
        return jsonify({"success": False, "error": "credentials not configured"}), 500
    success = sb_api.test_connection()
    status = 200 if success else 500
    return jsonify({"success": success}), status


if __name__ == "__main__":
    if sb_api is None:
        print("Sellbrite credentials not configured")
    else:
        ok = sb_api.test_connection()
        print("Connection successful" if ok else "Connection failed")

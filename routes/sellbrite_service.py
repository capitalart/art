"""Sellbrite API integration utilities."""

from __future__ import annotations

import base64
import logging
import os
from typing import Dict, Any, List, Tuple

import requests
from flask import Blueprint, jsonify
from dotenv import load_dotenv

import config
from routes.sellbrite_export import generate_sellbrite_json

load_dotenv()

SELLBRITE_TOKEN = config.SELLBRITE_ACCOUNT_TOKEN
SELLBRITE_SECRET = config.SELLBRITE_SECRET_KEY
API_BASE = config.SELLBRITE_API_BASE_URL

logger = logging.getLogger(__name__)

bp = Blueprint("sellbrite", __name__, url_prefix="/sellbrite")


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
    url = f"{API_BASE}/products?limit=1"
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


def get_products() -> List[Dict[str, Any]]:
    """Fetch all product listings from Sellbrite."""
    url = f"{API_BASE}/products"
    try:
        resp = requests.get(url, headers=_auth_header(), timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("Failed to fetch products from Sellbrite: %s", exc)
        return []


def create_product(listing_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Create a new product in Sellbrite using the API."""
    url = f"{API_BASE}/products"
    payload = generate_sellbrite_json(listing_data)
    sku = payload.get("sku", "N/A")

    try:
        resp = requests.post(url, headers=_auth_header(), json=payload, timeout=20)
        if 200 <= resp.status_code < 300:
            logger.info(f"Successfully created product {sku} in Sellbrite.")
            return True, f"Successfully created {sku}"
        else:
            error_message = resp.text
            logger.error(
                f"Failed to create product {sku} in Sellbrite. Status: {resp.status_code}, Response: {error_message}"
            )
            return False, f"Failed for {sku}: {error_message}"
    except requests.RequestException as exc:
        logger.error(f"Request failed for product {sku}: %s", exc)
        return False, f"Request failed for {sku}: {exc}"


@bp.route("/test-connection")
def sellbrite_test_route():
    """Flask route demonstrating a simple API connectivity check."""
    success = test_sellbrite_connection()
    status = 200 if success else 500
    return jsonify({"success": success}), status
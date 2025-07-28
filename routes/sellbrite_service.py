# routes/sellbrite_service.py
"""
Sellbrite API integration utilities.

This module handles all direct communication with the Sellbrite API,
including authentication, connection testing, and product creation/updating.

INDEX
-----
1.  Imports & Initialisation
2.  Authentication & Connection
3.  API Product Management Functions
4.  Flask Routes
"""

# ===========================================================================
# 1. Imports & Initialisation
# ===========================================================================
from __future__ import annotations
import base64
import logging
from typing import Dict, Any, List, Tuple, Optional
import requests
from flask import Blueprint, jsonify
import config
from routes.sellbrite_export import generate_sellbrite_json

SELLBRITE_TOKEN = config.SELLBRITE_ACCOUNT_TOKEN
SELLBRITE_SECRET = config.SELLBRITE_SECRET_KEY
API_BASE = config.SELLBRITE_API_BASE_URL
logger = logging.getLogger(__name__)
bp = Blueprint("sellbrite", __name__, url_prefix="/sellbrite")

# ===========================================================================
# 2. Authentication & Connection
# ===========================================================================
# (_auth_header and test_sellbrite_connection functions remain the same)

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

# ===========================================================================
# 3. API Product Management Functions
# ===========================================================================

def get_product_by_sku(sku: str) -> Optional[Dict[str, Any]]:
    """Fetches a single product from Sellbrite by its SKU."""
    if not sku:
        return None
    url = f"{API_BASE}/products/{sku}"
    try:
        resp = requests.get(url, headers=_auth_header(), timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.RequestException as exc:
        logger.error(f"Failed to fetch product {sku} from Sellbrite: {exc}")
        return None

def get_products() -> List[Dict[str, Any]]:
    # ... (function remains the same)
    url = f"{API_BASE}/products"
    try:
        resp = requests.get(url, headers=_auth_header(), timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("Failed to fetch products from Sellbrite: %s", exc)
        return []


def create_product(listing_data: Dict[str, Any]) -> Tuple[bool, str]:
    # ... (function remains the same)
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


def update_product(sku: str, listing_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Update an existing product, preserving its live inventory quantity."""
    if not sku:
        return False, "SKU is required for an update."

    # --- MODIFIED LOGIC ---
    # 1. Fetch the current product data from Sellbrite
    live_product = get_product_by_sku(sku)
    
    # 2. Generate the base payload with our local data
    payload = generate_sellbrite_json(listing_data)

    # 3. If the product exists, preserve its quantity
    if live_product:
        try:
            # Inventory is a list; we get the first warehouse's available count
            live_quantity = live_product.get("inventory", [{}])[0].get("available")
            if isinstance(live_quantity, int):
                payload["quantity"] = live_quantity
                logger.info(f"Preserving live quantity of {live_quantity} for SKU {sku}.")
        except (IndexError, TypeError):
            logger.warning(f"Could not parse live quantity for SKU {sku}. Using default.")
    # --- END OF MODIFIED LOGIC ---

    url = f"{API_BASE}/products/{sku}"
    try:
        resp = requests.put(url, headers=_auth_header(), json=payload, timeout=20)
        if 200 <= resp.status_code < 300:
            logger.info(f"Successfully updated product {sku} in Sellbrite.")
            return True, f"Successfully updated {sku}"
        
        error_message = resp.text
        logger.error(f"Failed to update product {sku}. Status: {resp.status_code}, Response: {error_message}")
        return False, f"Update failed for {sku}: {error_message}"
    except requests.RequestException as exc:
        logger.error(f"Request failed for product update {sku}: %s", exc)
        return False, f"Update request failed for {sku}: {exc}"

# ===========================================================================
# 4. Flask Routes
# ===========================================================================
@bp.route("/test-connection")
def sellbrite_test_route():
    # ... (function remains the same)
    success = test_sellbrite_connection()
    status = 200 if success else 500
    return jsonify({"success": success}), status
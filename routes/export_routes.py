# routes/export_routes.py
"""
Flask routes for exporting listing data to external services like Sellbrite.

This module contains routes for both the modern, API-driven Sellbrite sync export system.

INDEX
-----
1.  Imports & Initialisation
2.  Data Collection Helpers
3.  Sellbrite API Management Routes
"""

# ===========================================================================
# 1. Imports & Initialisation
# ===========================================================================

from __future__ import annotations
import datetime
import json
from pathlib import Path
from typing import List, Dict

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, send_from_directory, abort, session, Response,
)

import config
from . import utils
from routes import sellbrite_service
from routes.sellbrite_export import generate_sellbrite_json
from utils.logger_utils import log_action

bp = Blueprint("exports", __name__, url_prefix="/exports")


# ===========================================================================
# 2. Data Collection Helpers
# ===========================================================================

def _collect_listings(locked_only: bool) -> List[Dict]:
    """Gathers finalised and/or locked listing data from the filesystem."""
    listings = []
    search_dirs = [config.FINALISED_ROOT]
    if locked_only:
        search_dirs.append(config.ARTWORK_VAULT_ROOT)

    for base in search_dirs:
        if not base.exists():
            continue
        for listing_path in base.rglob("*-listing.json"):
            try:
                utils.assign_or_get_sku(listing_path, config.SKU_TRACKER)
                with open(listing_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if not locked_only or data.get("locked"):
                    listings.append(data)
            except Exception as e:
                log_action("sellbrite-exports", listing_path.name, "system", "failed to collect listing", status="fail", error=str(e))
    return listings


def _collect_locked_listings() -> List[Dict]:
    """Gathers only locked artwork listings, specifically for the API sync."""
    return _collect_listings(locked_only=True)


# ===========================================================================
# 3. Sellbrite API Management Routes
# ===========================================================================

@bp.route("/sellbrite/manage")
def sellbrite_management():
    """Displays the Sellbrite API management dashboard."""
    is_connected = sellbrite_service.test_sellbrite_connection()
    products = sellbrite_service.get_products() if is_connected else []
    return render_template("sellbrite_management.html", is_connected=is_connected, products=products)


@bp.post("/sellbrite/sync")
def sync_to_sellbrite():
    """Pushes locked products to Sellbrite (live) or shows a preview (dry run)."""
    run_type = request.form.get("run_type")
    user = session.get("username", "system")
    log_action("sellbrite-sync", "all_locked", user, f"Starting {run_type} sync.")
    
    listings_to_sync = _collect_locked_listings()

    if not listings_to_sync:
        flash("No locked artworks found to sync.", "warning")
        return redirect(url_for('exports.sellbrite_management'))

    if run_type == "dry_run":
        product_payloads = [generate_sellbrite_json(listing) for listing in listings_to_sync]
        return render_template("sellbrite_sync_preview.html", products=product_payloads)

    elif run_type == "live":
        success_count, fail_count = 0, 0
        for listing in listings_to_sync:
            sku = listing.get("sku", "UNKNOWN_SKU")
            success, message = sellbrite_service.create_product(listing)
            if success:
                success_count += 1
                log_action("sellbrite-sync", sku, user, "Live sync successful.", status="success")
            else:
                fail_count += 1
                flash(f"SKU {sku}: {message}", 'danger')
                log_action("sellbrite-sync", sku, user, "Live sync failed.", status="fail", error=message)
        
        flash(f"Live sync complete: {success_count} successful, {fail_count} failed.", 'success' if fail_count == 0 else 'warning')
        return redirect(url_for('exports.sellbrite_management'))
    
    flash("Invalid action specified.", "danger")
    return redirect(url_for('exports.sellbrite_management'))


@bp.route("/sellbrite/log/<path:log_filename>")
def view_sellbrite_log(log_filename: str):
    path = config.SELLBRITE_DIR / log_filename
    if not path.exists(): abort(404)
    return Response(path.read_text(encoding="utf-8"), mimetype="text/plain")
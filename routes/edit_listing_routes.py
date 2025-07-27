# routes/edit_listing_routes.py

# === [ 1. IMPORTS ] ===
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request, url_for
from . import utils
import config

# === [ 2. BLUEPRINT SETUP ] ===
bp = Blueprint("edit_listing", __name__, url_prefix="/edit")
logger = logging.getLogger(__name__)

# === [ 3. API ROUTES ] ===
# --- [ 3a. Swap Mockup API Endpoint | edit-listing-routes-py-3a ] ---
@bp.post("/swap-mockup-api")
def swap_mockup_api():
    """
    Handles an asynchronous request to swap a single mockup.
    Accepts JSON payload and returns JSON with new image URLs.
    """
    data = request.json
    seo_folder = data.get("seo_folder")
    slot_idx = data.get("slot_index")
    new_category = data.get("new_category")
    aspect = data.get("aspect")

    if not all([seo_folder, isinstance(slot_idx, int), new_category, aspect]):
        return jsonify({"success": False, "error": "Missing required data."}), 400

    try:
        success, new_mockup_name, new_thumb_name = utils.swap_one_mockup(
            seo_folder, slot_idx, new_category
        )

        if not success:
            raise RuntimeError("The swap_one_mockup utility failed.")

        # Construct the full URLs for the new images
        new_mockup_url = url_for(
            'artwork.processed_image', seo_folder=seo_folder, filename=new_mockup_name
        )
        new_thumb_url = url_for(
            'artwork.serve_mockup_thumb', seo_folder=seo_folder, filename=new_thumb_name
        )

        return jsonify({
            "success": True,
            "message": "Mockup swapped successfully.",
            "new_mockup_url": new_mockup_url,
            "new_thumb_url": new_thumb_url
        })

    except Exception as e:
        logger.error(f"Failed to swap mockup for {seo_folder}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
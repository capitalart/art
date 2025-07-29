# routes/edit_listing_routes.py
"""
Flask routes dedicated to asynchronous actions on the 'Edit Listing' page.

This module provides API-style endpoints that are called via JavaScript
to perform specific actions without a full page reload, such as swapping
a mockup image.

INDEX
-----
1.  Imports
2.  Blueprint Setup
3.  API Routes
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request, url_for
from . import utils
import config

# ===========================================================================
# 2. Blueprint Setup
# ===========================================================================
bp = Blueprint("edit_listing", __name__, url_prefix="/edit")
logger = logging.getLogger(__name__)

# ===========================================================================
# 3. API Routes
# ===========================================================================

@bp.post("/swap-mockup-api")
def swap_mockup_api():
    """
    Handles an asynchronous request to swap a single mockup.
    Accepts a JSON payload and returns JSON with new image URLs.
    """
    data = request.json
    seo_folder = data.get("seo_folder")
    slot_idx = data.get("slot_index")
    new_category = data.get("new_category")
    current_mockup_src = data.get("current_mockup_src")

    if not all([seo_folder, isinstance(slot_idx, int), new_category]):
        logger.warning("Swap mockup API called with missing data.")
        return jsonify({"success": False, "error": "Missing required data."}), 400

    try:
        logger.info(f"Attempting to swap mockup for '{seo_folder}', slot {slot_idx}, to category '{new_category}'.")
        success, new_mockup_name, new_thumb_name = utils.swap_one_mockup(
            seo_folder, slot_idx, new_category, current_mockup_src
        )

        if not success:
            raise RuntimeError("The swap_one_mockup utility failed to generate new images.")

        # --- CORRECTED URL GENERATION ---
        # The routes expect a single 'filename' or 'filepath' argument that includes the subdirectories.
        mockup_filepath = f"{seo_folder}/{new_mockup_name}"
        thumb_filepath = f"{seo_folder}/{config.THUMB_SUBDIR}/{new_thumb_name}"

        new_mockup_url = url_for('artwork.processed_image', filename=mockup_filepath)
        new_thumb_url = url_for('artwork.serve_mockup_thumb', filepath=thumb_filepath)

        logger.info(f"Successfully swapped mockup for '{seo_folder}'. New image: {new_mockup_name}")
        return jsonify({
            "success": True,
            "message": "Mockup swapped successfully.",
            "new_mockup_url": new_mockup_url,
            "new_thumb_url": new_thumb_url
        })

    except Exception as e:
        logger.error(f"Failed to swap mockup for '{seo_folder}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
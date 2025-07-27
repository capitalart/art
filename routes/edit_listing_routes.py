"""Routes for interactive edit-listing actions."""

from __future__ import annotations

from flask import Blueprint, request, jsonify, url_for

from routes import utils

bp = Blueprint("edit_listing", __name__)


@bp.route("/swap-mockup", methods=["POST"])
def swap_mockup():
    """Swap a mockup via AJAX and return new file paths."""
    data = request.get_json(silent=True) or {}
    seo = data.get("seo_filename", "").strip()
    aspect = data.get("aspect_ratio", "").strip()
    slot = int(data.get("slot_index", 0))
    category = data.get("category", "").strip()

    if not seo or not aspect or not category:
        return jsonify(success=False, error="Invalid parameters"), 400

    success, new_mockup, new_thumb = utils.swap_one_mockup(seo, slot, category)
    if not success:
        return jsonify(success=False, error="Swap failed"), 500

    thumb_path = f"art-processing/processed-artwork/{seo}/THUMBS/{new_thumb}"
    full_path = f"art-processing/processed-artwork/{seo}/{new_mockup}"

    return jsonify(
        success=True,
        new_full=url_for("static", filename=full_path),
        new_thumb=url_for("static", filename=thumb_path),
    )

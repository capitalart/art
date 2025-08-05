# routes/edit_listing_routes.py
# -*- coding: utf-8 -*-
"""
Flask routes for the ArtNarrator "Edit Listing" page.

This module contains all logic for viewing, editing, saving, and managing
a single artwork listing after it has been analysed by the AI.
"""
from __future__ import annotations
import json, logging, shutil
from pathlib import Path

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify, abort
)

import config
from . import utils as routes_utils
from helpers.listing_utils import (
    load_json_file_safe, resolve_listing_paths,
    generate_public_image_urls, update_artwork_registry
)
from utils.sku_assigner import assign_or_get_sku, reset_sku as reset_sku_file
from utils.logger_utils import log_action

# FIX: All routes on this page now belong to the 'edit_listing' blueprint.
bp = Blueprint("edit_listing", __name__, url_prefix="/edit-listing")


# === [ 1. Core Page Rendering | edit-routes-py-1 ] ===
@bp.route("/<aspect>/<filename>")
def edit_listing(aspect: str, filename: str):
    """Renders the main edit page for a single artwork."""
    try:
        seo_folder, folder, listing_file, main_img_path = resolve_listing_paths(aspect, filename, allow_locked=True)
    except FileNotFoundError:
        flash(f"Could not find artwork files for {filename}. It may have been moved or deleted.", "danger")
        return redirect(url_for("artwork.artworks"))

    listing_data = load_json_file_safe(listing_file, {})
    artwork_data = routes_utils.populate_artwork_data_from_json(listing_data, seo_folder)
    mockup_data = listing_data.get("mockups", [])
    mockups_details = routes_utils.get_mockup_details_for_template(mockup_data, folder, seo_folder, aspect)
    categories = routes_utils.get_categories_for_aspect(aspect)

    return render_template(
        "edit_listing.html",
        menu=routes_utils.get_menu(),
        artwork=artwork_data,
        mockups=mockups_details,
        main_image_path=main_img_path,
        aspect=aspect,
        filename=filename,
        seo_folder=seo_folder,
        categories=categories,
        allowed_colours=routes_utils.get_allowed_colours(),
        is_locked=routes_utils.is_finalised_image(main_img_path)
    )


# === [ 2. Listing Data Management (Save/Update) | edit-routes-py-2 ] ===
@bp.route("/save/<aspect>/<filename>", methods=["POST"])
def save_listing(aspect: str, filename: str):
    """Handles AJAX requests to save changes to the listing's text data."""
    try:
        seo_folder, _, listing_file, _ = resolve_listing_paths(aspect, filename, allow_locked=True)
    except FileNotFoundError:
        return jsonify({"success": False, "message": "Listing file not found."}), 404

    data = load_json_file_safe(listing_file)
    form_data = request.form.to_dict(flat=True)

    data['title'] = form_data.get('title', data.get('title'))
    data['description'] = form_data.get('description', data.get('description'))
    data['primary_colour'] = form_data.get('primary_colour', data.get('primary_colour'))
    data['secondary_colour'] = form_data.get('secondary_colour', data.get('secondary_colour'))

    tags, tags_changed = routes_utils.clean_terms(form_data.get('tags', '').split(','))
    materials, materials_changed = routes_utils.clean_terms(form_data.get('materials', '').split(','))
    data['tags'] = tags
    data['materials'] = materials

    with open(listing_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    log_action("save_listing", seo_folder, session.get("username", "unknown"), "Listing data saved.")
    message = "Listing saved successfully."
    if tags_changed or materials_changed:
        message += " Some tags/materials were cleaned for consistency."

    return jsonify({"success": True, "message": message})


# === [ 3. Mockup Management | edit-routes-py-3 ] ===
@bp.route("/swap-mockup/<aspect>/<filename>/<int:slot_idx>", methods=["POST"])
def swap_mockup(aspect: str, filename: str, slot_idx: int):
    """Handles AJAX requests to swap a single mockup image."""
    new_category = request.form.get("category")
    if not new_category:
        return jsonify({"success": False, "error": "No category specified"}), 400

    try:
        seo_folder, folder, _, _ = resolve_listing_paths(aspect, filename, allow_locked=True)
        success, new_composite, new_thumb = routes_utils.swap_one_mockup(seo_folder, slot_idx, new_category)

        if success:
            log_action("swap_mockup", seo_folder, session.get("username", "unknown"), f"Swapped slot {slot_idx} to {new_category}.")
            # The URL needs to point to the correct serving endpoint based on status
            status_folder = 'processed'
            if routes_utils.is_finalised_image(folder):
                status_folder = 'finalised' # This is a simplification; a more robust check might be needed
            
            return jsonify({
                "success": True,
                "message": "Mockup swapped!",
                "new_image_url": url_for(f'artwork.{status_folder}_image', filename=f"{seo_folder}/{new_composite}"),
                "new_thumb_url": url_for('artwork.serve_mockup_thumb', filepath=f"{seo_folder}/{config.THUMB_SUBDIR}/{new_thumb}")
            })
        else:
            return jsonify({"success": False, "error": "Failed to swap mockup. Check application logs."}), 500

    except Exception as e:
        logging.error(f"Error swapping mockup for {filename}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected server error occurred."}), 500

@bp.route("/regenerate-all-mockups/<aspect>/<filename>", methods=["POST"])
def regenerate_all_mockups(aspect: str, filename: str):
    """Placeholder for regenerating all mockups."""
    log_action("regenerate_all_mockups", filename, session.get("username", "unknown"), "Triggered.")
    flash("Full mockup regeneration is not yet implemented.", "info")
    return redirect(url_for("edit_listing.edit_listing", aspect=aspect, filename=filename))


# === [ 4. SKU Management | edit-routes-py-4 ] ===
@bp.route("/assign-sku/<aspect>/<filename>", methods=["POST"])
def assign_sku(aspect: str, filename: str):
    """Handles AJAX request to assign the next available SKU."""
    try:
        seo_folder, _, listing_file, _ = resolve_listing_paths(aspect, filename)
        sku = assign_or_get_sku(listing_file, config.SKU_TRACKER)
        log_action("assign_sku", sku, session.get("username", "unknown"), f"Assigned to {seo_folder}.")
        return jsonify({"success": True, "sku": sku, "message": f"SKU {sku} assigned."})
    except FileNotFoundError:
        return jsonify({"success": False, "message": "Listing file not found."}), 404
    except Exception as e:
        logging.error(f"Error assigning SKU for {filename}: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred while assigning SKU."}), 500

@bp.route("/reset-sku/<aspect>/<filename>", methods=["POST"])
def reset_sku(aspect: str, filename: str):
    """Handles AJAX request to reset an SKU, making it available again."""
    try:
        seo_folder, _, listing_file, _ = resolve_listing_paths(aspect, filename)
        data = load_json_file_safe(listing_file)
        old_sku = data.get("sku")

        if not old_sku:
             return jsonify({"success": False, "message": "No SKU exists on this listing to reset."})

        reset_sku_file(config.SKU_TRACKER, old_sku)
        data["sku"] = ""
        with open(listing_file, "w") as f:
            json.dump(data, f, indent=2)

        log_action("reset_sku", old_sku, session.get("username", "unknown"), f"Reset SKU for {seo_folder}.")
        return jsonify({"success": True, "message": f"SKU {old_sku} was reset and is now available."})

    except FileNotFoundError:
        return jsonify({"success": False, "message": "Listing file not found."}), 404
    except Exception as e:
        logging.error(f"Error resetting SKU for {filename}: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred while resetting SKU."}), 500


# === [ 5. Finalisation and Locking | edit-routes-py-5 ] ===
@bp.route("/finalise/<seo_folder>", methods=["POST"])
def finalise_artwork(seo_folder: str):
    """Moves an artwork from 'processed' to 'finalised'."""
    src = config.PROCESSED_ROOT / seo_folder
    dst = config.FINALISED_ROOT / seo_folder
    try:
        if not src.exists(): raise FileNotFoundError(f"Source artwork folder '{seo_folder}' not found in processed.")
        shutil.move(str(src), str(dst))
        listing_file = dst / f"{seo_folder}-listing.json"
        routes_utils.update_listing_paths(listing_file, config.PROCESSED_ROOT, config.FINALISED_ROOT)
        data = load_json_file_safe(listing_file)
        data["locked"] = False
        data["images"] = generate_public_image_urls(seo_folder, "finalised")
        with open(listing_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        update_artwork_registry(seo_folder, dst, "finalised")
        flash("Artwork finalised and moved for review.", "success")
        log_action("finalise", seo_folder, session.get("username", "unknown"), "Artwork finalised.")
    except Exception as exc:
        flash(f"Error during finalisation: {exc}", "danger")
        log_action("finalise", seo_folder, session.get("username", "unknown"), f"Finalisation failed: {exc}", status="fail")
    return redirect(url_for("artwork.finalised_gallery"))

@bp.route("/lock/<seo_folder>", methods=["POST"])
def lock_listing(seo_folder: str):
    """Moves an artwork from 'finalised' to the 'locked' vault."""
    src = config.FINALISED_ROOT / seo_folder
    dst = config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}"
    try:
        if not src.exists(): raise FileNotFoundError(f"Finalised artwork '{seo_folder}' not found.")
        shutil.move(str(src), str(dst))
        listing_file = dst / f"{seo_folder}-listing.json"
        routes_utils.update_listing_paths(listing_file, config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT)
        data = load_json_file_safe(listing_file)
        data["locked"] = True
        data["images"] = generate_public_image_urls(f"LOCKED-{seo_folder}", "locked")
        with open(listing_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        update_artwork_registry(f"LOCKED-{seo_folder}", dst, "locked")
        flash("Artwork locked in for export.", "success")
        log_action("lock", seo_folder, session.get("username", "unknown"), "Artwork locked.")
    except Exception as e:
        flash(f"Error locking artwork: {e}", "danger")
        log_action("lock", seo_folder, session.get("username", "unknown"), f"Locking failed: {e}", status="fail")
    return redirect(url_for("artwork.locked_gallery"))

@bp.route("/unlock/<seo_folder>", methods=["POST"])
def unlock_listing(seo_folder: str):
    """Moves a locked artwork back to 'finalised'."""
    clean_name = seo_folder.replace("LOCKED-", "")
    src = config.ARTWORK_VAULT_ROOT / seo_folder
    dst = config.FINALISED_ROOT / clean_name
    try:
        shutil.move(str(src), str(dst))
        listing_file = dst / f"{clean_name}-listing.json"
        routes_utils.update_listing_paths(listing_file, config.ARTWORK_VAULT_ROOT, config.FINALISED_ROOT)
        data = load_json_file_safe(listing_file)
        data["locked"] = False
        data["images"] = generate_public_image_urls(clean_name, "finalised")
        with open(listing_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        update_artwork_registry(clean_name, dst, "finalised")
        flash("Artwork unlocked and moved back to finalised.", "success")
        log_action("unlock", seo_folder, session.get("username", "unknown"), "Artwork unlocked.")
    except Exception as exc:
        flash(f"Error during unlocking: {exc}", "danger")
        log_action("unlock", seo_folder, session.get("username", "unknown"), f"Unlocking failed: {exc}", status="fail")
    return redirect(url_for("artwork.finalised_gallery"))
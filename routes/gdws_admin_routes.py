# routes/gdws_admin_routes.py
"""
Admin interface for the Guided Description Writing System (GDWS).

This module provides the backend for the GDWS editor, allowing admins to
load, edit, reorder, and regenerate paragraph blocks for different artwork
aspect ratios.

INDEX
-----
1.  Imports
2.  Blueprint Setup
3.  Helper Functions
4.  Main Editor Routes
5.  Asynchronous API Routes
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import json
import re
import logging
from pathlib import Path
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify

import config
from routes.utils import get_menu
from utils.ai_services import call_ai_to_rewrite, call_ai_to_generate_title

logger = logging.getLogger(__name__)

# ===========================================================================
# 2. Blueprint Setup
# ===========================================================================
bp = Blueprint("gdws_admin", __name__, url_prefix="/admin/gdws")


# ===========================================================================
# 3. Helper Functions
# ===========================================================================

def slugify(text: str) -> str:
    """
    Creates a filesystem-safe name from a heading.
    Note: This version is specific to GDWS and contains hardcoded remappings.
    """
    s = text.lower()
    s = re.sub(r'[^\w\s-]', '', s).strip()
    s = re.sub(r'[-\s]+', '_', s)
    if "about_the_artist" in s: return "about_the_artist"
    if "did_you_know" in s: return "about_art_style"
    if "what_youll_receive" in s: return "file_details"
    return s


def get_aspect_ratios() -> list[str]:
    """Return a list of available aspect ratio folders in the GDWS directory."""
    if not config.GDWS_CONTENT_DIR.exists():
        return []
    return sorted([p.name for p in config.GDWS_CONTENT_DIR.iterdir() if p.is_dir()])


# ===========================================================================
# 4. Main Editor Routes
# ===========================================================================

@bp.route("/")
def editor():
    """Renders the main GDWS editor page."""
    # Pass pinned titles from config to the template
    pinned_start = config.GDWS_CONFIG["PINNED_START_TITLES"]
    pinned_end = config.GDWS_CONFIG["PINNED_END_TITLES"]
    return render_template(
        "dws_editor.html",
        menu=get_menu(),
        aspect_ratios=get_aspect_ratios(),
        PINNED_START_TITLES=pinned_start,
        PINNED_END_TITLES=pinned_end,
    )


@bp.route("/template/<aspect_ratio>")
def get_template_data(aspect_ratio: str):
    """Fetches and sorts paragraphs based on saved order and pinned status."""
    aspect_path = config.GDWS_CONTENT_DIR / aspect_ratio
    if not aspect_path.exists():
        return jsonify({"error": "Aspect ratio not found"}), 404

    all_blocks = {}
    for folder_path in [p for p in aspect_path.iterdir() if p.is_dir()]:
        base_file = folder_path / "base.json"
        if base_file.exists():
            try:
                data = json.loads(base_file.read_text(encoding='utf-8'))
                all_blocks[data['title']] = data
            except Exception as e:
                logger.error(f"Error loading GDWS base file {base_file}: {e}")

    # Use pinned titles from config
    pinned_start = config.GDWS_CONFIG["PINNED_START_TITLES"]
    pinned_end = config.GDWS_CONFIG["PINNED_END_TITLES"]

    start_blocks = [all_blocks.pop(title) for title in pinned_start if title in all_blocks]
    end_blocks = [all_blocks.pop(title) for title in pinned_end if title in all_blocks]
    
    # Sort remaining (middle) blocks based on the order.json file
    order_file = aspect_path / "order.json"
    sorted_middle_blocks = []
    if order_file.exists():
        try:
            order = json.loads(order_file.read_text(encoding='utf-8'))
            for title in order:
                if title in all_blocks:
                    sorted_middle_blocks.append(all_blocks.pop(title))
        except Exception as e:
            logger.error(f"Error reading GDWS order file {order_file}: {e}")
    
    # Add any remaining blocks that weren't in the order file
    sorted_middle_blocks.extend(all_blocks.values())

    return jsonify({"blocks": start_blocks + sorted_middle_blocks + end_blocks})


# ===========================================================================
# 5. Asynchronous API Routes
# ===========================================================================

@bp.post("/save-order")
def save_order():
    """Saves the new display order of the middle paragraphs."""
    data = request.json
    aspect_ratio = data.get('aspect_ratio')
    order = data.get('order')

    if not aspect_ratio or order is None:
        return jsonify({"status": "error", "message": "Missing aspect_ratio or order data."}), 400

    try:
        order_file = config.GDWS_CONTENT_DIR / aspect_ratio / "order.json"
        order_file.write_text(json.dumps(order, indent=2), encoding='utf-8')
        logger.info(f"GDWS paragraph order saved for aspect ratio: {aspect_ratio}")
        return jsonify({"status": "success", "message": "Order saved."})
    except Exception as e:
        logger.error(f"Failed to save GDWS order for {aspect_ratio}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to write order file to disk."}), 500


@bp.post("/regenerate-title")
def regenerate_title():
    """Handles AI regeneration for a paragraph title."""
    content = request.json.get('content', '')
    try:
        new_title = call_ai_to_generate_title(content)
        return jsonify({"new_title": new_title})
    except Exception as e:
        logger.error(f"AI title regeneration failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "AI title generation failed."}), 500


@bp.post("/regenerate-paragraph")
def regenerate_paragraph():
    """Handles AI regeneration for a single paragraph's content."""
    data = request.json
    prompt = (
        f"Instruction: \"{data.get('instructions', '')}\"\n\n"
        f"Rewrite the following text based on the instruction. Respond only with the rewritten text.\n\n"
        f"TEXT TO REWRITE:\n\"{data.get('current_text', '')}\""
    )
    try:
        new_text = call_ai_to_rewrite(prompt)
        return jsonify({"new_content": new_text})
    except Exception as e:
        logger.error(f"AI paragraph regeneration failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "AI content regeneration failed."}), 500


@bp.post("/save-base-paragraph")
def save_base_paragraph():
    """Saves edits to a base.json file, handling potential renames."""
    data = request.json
    aspect_ratio = data.get('aspect_ratio')
    original_title = data.get('original_title')
    new_title = data.get('new_title')
    
    if not all([aspect_ratio, original_title, new_title]):
        return jsonify({"status": "error", "message": "Missing required data."}), 400

    try:
        original_slug = slugify(original_title)
        new_slug = slugify(new_title)
        
        original_folder = config.GDWS_CONTENT_DIR / aspect_ratio / original_slug
        target_folder = config.GDWS_CONTENT_DIR / aspect_ratio / new_slug
        
        # Handle renaming of the folder if the title/slug changed
        if original_slug != new_slug:
            if target_folder.exists():
                return jsonify({"status": "error", "message": "A paragraph with that name already exists."}), 400
            if not original_folder.exists():
                return jsonify({"status": "error", "message": "Original paragraph folder not found."}), 404
            original_folder.rename(target_folder)
            logger.info(f"Renamed GDWS folder from '{original_slug}' to '{new_slug}'")

        file_path = target_folder / "base.json"
        existing_data = json.loads(file_path.read_text(encoding='utf-8')) if file_path.exists() else {"id": "base"}

        existing_data.update({
            'title': new_title,
            'content': data.get('content', existing_data.get('content', '')),
            'instructions': data.get('instructions', existing_data.get('instructions', '')),
            'last_updated': datetime.now().isoformat()
        })
        
        file_path.write_text(json.dumps(existing_data, indent=4), encoding='utf-8')
        logger.info(f"Updated GDWS base file: {file_path}")
        return jsonify({"status": "success", "message": f"Updated {file_path}", "new_slug": new_slug})
    except Exception as e:
        logger.error(f"Failed to save base paragraph '{new_title}': {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An unexpected error occurred while saving."}), 500
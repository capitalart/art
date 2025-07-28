# routes/mockup_admin_routes.py
"""
Admin dashboard for managing and categorising mockups.

Provides functionality for uploading, viewing, categorizing, and deleting
mockup images used in the artwork composite generation process.

INDEX
-----
1.  Imports & Initialisation
2.  Blueprint Setup
3.  Helper Functions
4.  Main Dashboard Route
5.  Image Serving Routes
6.  Mockup Management API Routes
"""

# ===========================================================================
# 1. Imports & Initialisation
# ===========================================================================
from __future__ import annotations
import logging
import shutil
import subprocess
from pathlib import Path

# Third-party imports
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, url_for,
    send_from_directory
)
from PIL import Image
import imagehash

# Local application imports
import config
from routes.utils import get_menu

logger = logging.getLogger(__name__)

# ===========================================================================
# 2. Blueprint Setup
# ===========================================================================
bp = Blueprint("mockup_admin", __name__, url_prefix="/admin/mockups")


# ===========================================================================
# 3. Helper Functions
# ===========================================================================

def get_available_aspects() -> list[str]:
    """Finds available aspect ratio staging folders."""
    if not config.MOCKUPS_STAGING_DIR.exists():
        return []
    return sorted([d.name for d in config.MOCKUPS_STAGING_DIR.iterdir() if d.is_dir()])


def generate_thumbnail(source_path: Path, aspect: str):
    """Creates a thumbnail for a mockup image if it doesn't exist."""
    thumb_dir = config.MOCKUP_THUMBNAIL_DIR / aspect
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / source_path.name

    if not thumb_path.exists():
        try:
            with Image.open(source_path) as img:
                # Use thumbnail dimensions from config
                img.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
                img.convert("RGB").save(thumb_path, "JPEG", quality=85)
        except Exception as e:
            logger.error(f"Could not create thumbnail for {source_path.name}: {e}")


# ===========================================================================
# 4. Main Dashboard Route
# ===========================================================================

@bp.route("/", defaults={'aspect': '4x5'})
@bp.route("/<aspect>")
def dashboard(aspect: str):
    """Display the paginated and sorted mockup management dashboard."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category_filter = request.args.get('category', 'All')
    sort_by = request.args.get('sort', 'name')

    all_mockups = []
    
    categorised_path = config.MOCKUPS_CATEGORISED_DIR / aspect
    categorised_path.mkdir(parents=True, exist_ok=True)
    all_categories = sorted([d.name for d in categorised_path.iterdir() if d.is_dir()])
    
    def collect_mockups(folder_path, category_name):
        for item in folder_path.iterdir():
            if item.is_file() and item.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                generate_thumbnail(item, aspect)
                all_mockups.append({
                    "filename": item.name, 
                    "category": category_name,
                    "mtime": item.stat().st_mtime
                })

    if category_filter in {'All', 'Uncategorised'}:
        staging_path = config.MOCKUPS_STAGING_DIR / aspect
        staging_path.mkdir(parents=True, exist_ok=True)
        collect_mockups(staging_path, "Uncategorised")

    if category_filter != 'Uncategorised':
        for category_name in all_categories:
            if category_filter in {'All', category_name}:
                collect_mockups(categorised_path / category_name, category_name)

    all_mockups.sort(key=lambda x: x['mtime'] if sort_by == 'date' else x['filename'], reverse=(sort_by == 'date'))

    total_mockups = len(all_mockups)
    start = (page - 1) * per_page
    paginated_mockups = all_mockups[start:start + per_page]
    total_pages = (total_mockups + per_page - 1) // per_page

    return render_template(
        "admin/mockups.html",
        menu=get_menu(),
        mockups=paginated_mockups,
        categories=all_categories,
        current_aspect=aspect,
        aspect_ratios=get_available_aspects(),
        page=page, per_page=per_page, total_pages=total_pages,
        total_mockups=total_mockups, category_filter=category_filter, sort_by=sort_by
    )


# ===========================================================================
# 5. Image Serving Routes
# ===========================================================================
    
@bp.route("/thumbnail/<aspect>/<path:filename>")
def mockup_thumbnail(aspect, filename):
    """Serves the generated thumbnail for a mockup."""
    return send_from_directory(config.MOCKUP_THUMBNAIL_DIR / aspect, filename)


@bp.route("/image/<aspect>/<category>/<path:filename>")
def mockup_image(aspect, category, filename):
    """Serves the full-size mockup image."""
    if category == "Uncategorised":
        image_path = config.MOCKUPS_STAGING_DIR / aspect
    else:
        image_path = config.MOCKUPS_CATEGORISED_DIR / aspect / category
    return send_from_directory(image_path, filename)


# ===========================================================================
# 6. Mockup Management API Routes
# ===========================================================================

@bp.route("/upload/<aspect>", methods=["POST"])
def upload_mockup(aspect):
    """Handles file uploads for new mockups."""
    files = request.files.getlist('mockup_files')
    staging_path = config.MOCKUPS_STAGING_DIR / aspect
    count = 0
    for file in files:
        if file and file.filename:
            saved_path = staging_path / file.filename
            file.save(saved_path)
            generate_thumbnail(saved_path, aspect)
            count += 1
    if count > 0:
        logger.info(f"Uploaded {count} new mockup(s) to aspect '{aspect}'.")
        flash(f"Uploaded and created thumbnails for {count} new mockup(s).", "success")
    return redirect(url_for("mockup_admin.dashboard", aspect=aspect))


@bp.route("/find-duplicates/<aspect>")
def find_duplicates(aspect):
    """Scans for visually similar mockups using image hashing."""
    hashes = {}
    duplicates = []
    # Note: This route depends on the 'imagehash' library.
    all_paths = list((config.MOCKUPS_STAGING_DIR / aspect).glob("*.*"))
    all_paths.extend(list((config.MOCKUPS_CATEGORISED_DIR / aspect).rglob("*.*")))

    for path in all_paths:
        if path.suffix.lower() not in ['.png', '.jpg', '.jpeg']: continue
        try:
            with Image.open(path) as img:
                h = str(imagehash.phash(img))
                if h in hashes:
                    duplicates.append({"original": hashes[h], "duplicate": str(path.relative_to(config.BASE_DIR))})
                else:
                    hashes[h] = str(path.relative_to(config.BASE_DIR))
        except Exception as e:
            logger.warning(f"Could not hash image {path}: {e}")
            
    return jsonify({"duplicates": duplicates})


@bp.route("/create-category/<aspect>", methods=["POST"])
def create_category(aspect):
    """Creates a new category folder for an aspect ratio."""
    category_name = request.form.get("category_name", "").strip()
    if category_name:
        new_dir = config.MOCKUPS_CATEGORISED_DIR / aspect / category_name
        new_dir.mkdir(exist_ok=True)
        logger.info(f"Created new mockup category: '{category_name}' in aspect '{aspect}'.")
        flash(f"Category '{category_name}' created.", "success")
    else:
        flash("Category name cannot be empty.", "danger")
    return redirect(url_for("mockup_admin.dashboard", aspect=aspect))
    

@bp.route("/suggest-category", methods=["POST"])
def suggest_category():
    """Uses an AI script to suggest a category for an uncategorised mockup."""
    filename = request.json.get("filename")
    aspect = request.json.get("aspect")
    file_to_process = config.MOCKUPS_STAGING_DIR / aspect / filename
    
    if not file_to_process.exists():
        return jsonify({"success": False, "error": f"File not found: {filename}"}), 404
        
    try:
        # Use the new config variable for the script path
        cmd = ["python3", str(config.MOCKUP_CATEGORISER_SCRIPT_PATH), "--file", str(file_to_process), "--no-move"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        return jsonify({"success": True, "suggestion": result.stdout.strip()})
    except subprocess.CalledProcessError as e:
        logger.error(f"Mockup categoriser script failed for {filename}: {e.stderr}")
        return jsonify({"success": False, "error": f"AI categorizer failed: {e.stderr}"}), 500
    except Exception as e:
        logger.error(f"Error calling mockup categoriser script for {filename}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/move-mockup", methods=["POST"])
def move_mockup():
    """Moves a mockup from one category (or uncategorised) to another."""
    data = request.json
    filename, aspect = data.get("filename"), data.get("aspect")
    original_category, new_category = data.get("original_category"), data.get("new_category")
    
    source_path = (config.MOCKUPS_STAGING_DIR / aspect / filename) if original_category == "Uncategorised" \
        else (config.MOCKUPS_CATEGORISED_DIR / aspect / original_category / filename)
    
    dest_dir = config.MOCKUPS_CATEGORISED_DIR / aspect / new_category
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        shutil.move(str(source_path), str(dest_dir / filename))
        logger.info(f"Moved mockup '{filename}' from '{original_category}' to '{new_category}' in aspect '{aspect}'.")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to move mockup '{filename}': {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/delete-mockup", methods=["POST"])
def delete_mockup():
    """Deletes a mockup image and its corresponding thumbnail."""
    data = request.json
    filename, aspect, category = data.get("filename"), data.get("aspect"), data.get("category")

    path_to_delete = (config.MOCKUPS_STAGING_DIR / aspect / filename) if category == "Uncategorised" \
        else (config.MOCKUPS_CATEGORISED_DIR / aspect / category / filename)

    try:
        if path_to_delete.is_file():
            path_to_delete.unlink()
            (config.MOCKUP_THUMBNAIL_DIR / aspect / filename).unlink(missing_ok=True)
            logger.info(f"Deleted mockup '{filename}' from '{category}' in aspect '{aspect}'.")
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "File not found."}), 404
    except Exception as e:
        logger.error(f"Error deleting mockup '{filename}': {e}")
        return jsonify({"success": False, "error": f"Error deleting file: {e}"}), 500
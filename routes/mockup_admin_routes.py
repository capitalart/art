"""Admin dashboard for managing and categorising mockups."""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_from_directory
from pathlib import Path
import subprocess
import os
import shutil
from PIL import Image
import imagehash

import config
from routes.utils import get_menu

bp = Blueprint("mockup_admin", __name__, url_prefix="/admin/mockups")

THUMBNAIL_DIR = config.MOCKUPS_INPUT_DIR / ".thumbnails"
THUMBNAIL_SIZE = (400, 400)

def get_available_aspects():
    """Finds available aspect ratio staging folders."""
    if not config.MOCKUPS_STAGING_DIR.exists():
        return []
    return sorted([d.name for d in config.MOCKUPS_STAGING_DIR.iterdir() if d.is_dir()])

def generate_thumbnail(source_path: Path, aspect: str):
    """Creates a thumbnail for a mockup image if it doesn't exist."""
    thumb_dir = THUMBNAIL_DIR / aspect
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / source_path.name

    if not thumb_path.exists():
        try:
            with Image.open(source_path) as img:
                img.thumbnail(THUMBNAIL_SIZE)
                img.convert("RGB").save(thumb_path, "JPEG", quality=85)
        except Exception as e:
            print(f"Could not create thumbnail for {source_path.name}: {e}")

@bp.route("/", defaults={'aspect': '4x5'})
@bp.route("/<aspect>")
def dashboard(aspect):
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

    if category_filter == 'All' or category_filter == 'Uncategorised':
        staging_path = config.MOCKUPS_STAGING_DIR / aspect
        staging_path.mkdir(parents=True, exist_ok=True)
        collect_mockups(staging_path, "Uncategorised")

    if category_filter != 'Uncategorised':
        for category_name in all_categories:
            if category_filter == 'All' or category_filter == category_name:
                collect_mockups(categorised_path / category_name, category_name)

    if sort_by == 'date':
        all_mockups.sort(key=lambda x: x['mtime'], reverse=True)
    else:
        all_mockups.sort(key=lambda x: x['filename'])

    total_mockups = len(all_mockups)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_mockups = all_mockups[start:end]
    total_pages = (total_mockups + per_page - 1) // per_page

    return render_template(
        "admin/mockups.html",
        menu=get_menu(),
        mockups=paginated_mockups,
        categories=all_categories,
        current_aspect=aspect,
        aspect_ratios=get_available_aspects(),
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_mockups=total_mockups,
        category_filter=category_filter,
        sort_by=sort_by
    )
    
@bp.route("/thumbnail/<aspect>/<path:filename>")
def mockup_thumbnail(aspect, filename):
    return send_from_directory(THUMBNAIL_DIR / aspect, filename)

@bp.route("/image/<aspect>/<category>/<path:filename>")
def mockup_image(aspect, category, filename):
    if category == "Uncategorised":
        image_path = config.MOCKUPS_STAGING_DIR / aspect
    else:
        image_path = config.MOCKUPS_CATEGORISED_DIR / aspect / category
    return send_from_directory(image_path, filename)

@bp.route("/upload/<aspect>", methods=["POST"])
def upload_mockup(aspect):
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
        flash(f"Uploaded and created thumbnails for {count} new mockup(s).", "success")
    return redirect(url_for("mockup_admin.dashboard", aspect=aspect))

@bp.route("/find-duplicates/<aspect>")
def find_duplicates(aspect):
    hashes = {}
    duplicates = []
    all_paths = []
    
    staging_path = config.MOCKUPS_STAGING_DIR / aspect
    all_paths.extend(p for p in staging_path.glob("*.*") if p.suffix.lower() in ['.png', '.jpg', '.jpeg'])
    categorised_path = config.MOCKUPS_CATEGORISED_DIR / aspect
    all_paths.extend(p for p in categorised_path.rglob("*.*") if p.suffix.lower() in ['.png', '.jpg', '.jpeg'])

    for path in all_paths:
        try:
            with Image.open(path) as img:
                h = str(imagehash.phash(img))
                if h in hashes:
                    duplicates.append({"original": hashes[h], "duplicate": str(path.relative_to(config.BASE_DIR))})
                else:
                    hashes[h] = str(path.relative_to(config.BASE_DIR))
        except Exception as e:
            print(f"Could not hash {path}: {e}")
            
    return jsonify({"duplicates": duplicates})

@bp.route("/create-category/<aspect>", methods=["POST"])
def create_category(aspect):
    category_name = request.form.get("category_name", "").strip()
    if category_name:
        new_dir = config.MOCKUPS_CATEGORISED_DIR / aspect / category_name
        new_dir.mkdir(exist_ok=True)
        flash(f"Category '{category_name}' created.", "success")
    else:
        flash("Category name cannot be empty.", "danger")
    return redirect(url_for("mockup_admin.dashboard", aspect=aspect))
    
@bp.route("/suggest-category", methods=["POST"])
def suggest_category():
    filename = request.json.get("filename")
    aspect = request.json.get("aspect")
    script_path = config.SCRIPTS_DIR / "mockup_categoriser.py"
    file_to_process = config.MOCKUPS_STAGING_DIR / aspect / filename
    if not file_to_process.exists():
        return jsonify({"success": False, "error": f"File not found: {filename}"}), 404
    try:
        result = subprocess.run(
            ["python3", str(script_path), "--file", str(file_to_process), "--no-move"],
            capture_output=True, text=True, check=True, timeout=120
        )
        return jsonify({"success": True, "suggestion": result.stdout.strip()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/move-mockup", methods=["POST"])
def move_mockup():
    data = request.json
    filename, aspect, original_category, new_category = data.get("filename"), data.get("aspect"), data.get("original_category"), data.get("new_category")
    
    if original_category == "Uncategorised":
        source_path = config.MOCKUPS_STAGING_DIR / aspect / filename
    else:
        source_path = config.MOCKUPS_CATEGORISED_DIR / aspect / original_category / filename
    
    dest_dir = config.MOCKUPS_CATEGORISED_DIR / aspect / new_category
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        shutil.move(str(source_path), str(dest_dir / filename))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/delete-mockup", methods=["POST"])
def delete_mockup():
    data = request.json
    filename, aspect, category = data.get("filename"), data.get("aspect"), data.get("category")

    if category == "Uncategorised":
        path_to_delete = config.MOCKUPS_STAGING_DIR / aspect / filename
    else:
        path_to_delete = config.MOCKUPS_CATEGORISED_DIR / aspect / category / filename

    try:
        if path_to_delete.is_file():
            path_to_delete.unlink()
            (THUMBNAIL_DIR / aspect / filename).unlink(missing_ok=True)
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "File not found."}), 404
    except Exception as e:
        return jsonify({"success": False, "error": f"Error deleting file: {e}"}), 500
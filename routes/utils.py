# routes/artwork_routes.py
# -*- coding: utf-8 -*-
"""
Artwork-related Flask routes for the ArtNarrator application.

This module powers the core artwork workflow, from upload and analysis to
finalisation and gallery displays. It does not handle the editing of a listing.
"""
from __future__ import annotations
import json, subprocess, uuid, logging, shutil, os, datetime, time, sys
from pathlib import Path

from PIL import Image
import google.generativeai as genai
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, send_from_directory, abort, Response, jsonify,
)

import config
from helpers.listing_utils import (
    create_unanalysed_subfolder, load_json_file_safe,
    generate_public_image_urls, delete_artwork as delete_artwork_files,
    update_artwork_registry
)
import scripts.analyze_artwork as aa
from scripts import signing_service
from . import utils as routes_utils
from utils.logger_utils import log_action
from utils.sku_assigner import peek_next_sku

bp = Blueprint("artwork", __name__)


# === [ 1. Health Checks, Status API & Subprocess Helpers | artwork-routes-py-1 ] ===
@bp.get("/health/openai")
def health_openai():
    logger = logging.getLogger(__name__)
    try:
        # A simple, lightweight call to check connectivity.
        aa.client.models.list()
        return jsonify({"ok": True})
    except Exception as exc:
        logger.error("OpenAI health check failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500

@bp.get("/health/google")
def health_google():
    logger = logging.getLogger(__name__)
    try:
        # A simple, lightweight call to check connectivity.
        genai.list_models()
        return jsonify({"ok": True})
    except Exception as exc:
        logger.error("Google health check failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500

def _write_analysis_status(step: str, percent: int, file: str | None = None, status: str | None = None, error: str | None = None) -> None:
    """Safely writes the current analysis status to a JSON file."""
    payload = {"step": step, "percent": percent, "file": file, "status": status, "error": error}
    try:
        # Filter out None values before writing
        config.ANALYSIS_STATUS_FILE.write_text(json.dumps({k: v for k, v in payload.items() if v is not None}))
    except Exception as exc:
        logging.getLogger(__name__).error(f"Failed writing analysis status: {exc}")

@bp.route("/status/analyze")
def analysis_status():
    """API endpoint for the frontend to poll for analysis progress."""
    if config.ANALYSIS_STATUS_FILE.exists():
        return Response(config.ANALYSIS_STATUS_FILE.read_text(), mimetype="application/json")
    # Return a default idle state if the file doesn't exist
    return jsonify({"step": "idle", "percent": 0})

def _run_ai_analysis(img_path: Path, provider: str) -> dict:
    """Executes the AI analysis script as a secure subprocess."""
    logger = logging.getLogger("art_analysis")
    # FIX: Pass provider to the analysis script
    cmd = [sys.executable, str(config.ANALYZE_SCRIPT_PATH), str(img_path), "--provider", provider, "--json-output"]
    logger.info(f"Executing analysis command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        error_msg = (result.stderr or 'Unknown error').strip()
        logger.error(f"AI analysis script failed: {error_msg}")
        raise RuntimeError(f"AI analysis failed: {error_msg}")
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        logger.error(f"AI analysis output could not be parsed: {result.stdout}")
        raise RuntimeError("AI analysis output could not be parsed.") from e

def _generate_composites(log_id: str) -> None:
    """Executes the composite generation script as a secure subprocess."""
    cmd = [sys.executable, str(config.GENERATE_SCRIPT_PATH)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=config.BASE_DIR, timeout=600)
    log_file = config.LOGS_DIR / "composite-generation-logs" / f"composite_gen_{log_id}.log"
    log_file.parent.mkdir(exist_ok=True, parents=True)
    log_file.write_text(f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
    if result.returncode != 0:
        raise RuntimeError(f"Composite generation failed ({result.returncode}). See log {log_file.name}")


# === [ 2. Core Navigation, Galleries & Upload | artwork-routes-py-2 ] ===
@bp.app_context_processor
def inject_latest_artwork():
    """Injects latest artwork info into all templates for the nav link."""
    return dict(latest_artwork=routes_utils.latest_analyzed_artwork())

@bp.route("/")
def home():
    """Renders the main home/dashboard page."""
    return render_template("index.html", menu=routes_utils.get_menu())

@bp.route("/upload", methods=["GET", "POST"])
def upload_artwork():
    """Handles both GET request for the upload page and POST for file uploads."""
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if request.method == "POST":
        files = request.files.getlist("images")
        success_count = 0
        error_messages = []
        user = session.get("username", "unknown")

        if not files or all(not f.filename for f in files):
            msg = "No files were selected for upload."
            if is_ajax: return jsonify({"success": False, "message": msg})
            flash(msg, "warning")
            return redirect(request.url)

        for f in files:
            if not f or not f.filename:
                continue

            try:
                # Create a unique subfolder for each uploaded file to prevent name collisions.
                temp_subfolder_name = f"{Path(f.filename).stem}-{uuid.uuid4().hex[:8]}"
                folder = config.UNANALYSED_ROOT / temp_subfolder_name
                folder.mkdir(parents=True, exist_ok=True)

                res = _process_upload_file(f, folder)
                if res["success"]:
                    success_count += 1
                    log_action("upload", f.filename, user, "Uploaded successfully", status="success")
                else:
                    error_messages.append(f"{f.filename}: {res['error']}")
                    log_action("upload", f.filename, user, res['error'], status="fail")
                    shutil.rmtree(folder, ignore_errors=True) # Clean up failed upload folder

            except Exception as exc:
                logging.getLogger(__name__).error(f"Upload failed for {f.filename}: {exc}", exc_info=True)
                error_messages.append(f"{f.filename}: An unexpected server error occurred.")
                log_action("upload", f.filename, user, str(exc), status="fail")

        # FIX: Correctly handle AJAX responses for all cases.
        if is_ajax:
            if success_count > 0 and not error_messages:
                return jsonify({"success": True, "message": f"Uploaded {success_count} file(s) successfully."})
            elif success_count > 0 and error_messages:
                 return jsonify({"success": True, "message": f"Completed with {success_count} success(es) and {len(error_messages)} error(s). Errors: {', '.join(error_messages)}"})
            else:
                 return jsonify({"success": False, "message": f"Upload failed for all files. Errors: {', '.join(error_messages)}"})

        # Standard HTML form response
        if success_count > 0:
            flash(f"Uploaded {success_count} file(s) successfully.", "success")
        for error in error_messages:
            flash(error, "danger")
        return redirect(url_for("artwork.artworks"))

    return render_template("upload.html", menu=routes_utils.get_menu())

@bp.route("/artworks")
def artworks():
    """Displays the main gallery of all artworks at different stages."""
    processed, processed_names = routes_utils.list_processed_artworks()
    ready = routes_utils.list_ready_to_analyze(processed_names)
    finalised = routes_utils.list_finalised_artworks()
    return render_template("artworks.html", ready_artworks=ready, processed_artworks=processed, finalised_artworks=finalised, menu=routes_utils.get_menu())

@bp.route("/finalised")
def finalised_gallery():
    """Displays the gallery of finalised artworks ready for export."""
    from routes import sellbrite_service
    artworks_list = [a for a in routes_utils.get_all_artworks() if a['status'] == 'finalised']
    is_connected = sellbrite_service.test_sellbrite_connection()
    sellbrite_defaults = config.SELLBRITE_DEFAULTS
    for art in artworks_list:
        art['sellbrite_category'] = sellbrite_defaults['CATEGORY']
        art['sellbrite_condition'] = sellbrite_defaults['CONDITION']
        art['sellbrite_quantity'] = sellbrite_defaults['QUANTITY']
        if is_connected and art.get('sku'):
            product = sellbrite_service.get_product_by_sku(art['sku'])
            art['sellbrite_status'] = 'Synced' if product else 'Not Found'
        elif is_connected:
            art['sellbrite_status'] = 'No SKU'
        else:
            art['sellbrite_status'] = 'API Offline'
    return render_template("finalised.html", artworks=artworks_list, menu=routes_utils.get_menu())

@bp.route("/locked")
def locked_gallery():
    """Displays the gallery of locked artworks in the vault."""
    locked_items = [a for a in routes_utils.get_all_artworks() if a.get('locked')]
    return render_template("locked.html", artworks=locked_items, menu=routes_utils.get_menu())


# === [ 3. Analysis & Workflow Triggers | artwork-routes-py-3 ] ===
@bp.route("/analyze/<aspect>/<filename>", methods=["POST"])
def analyze_artwork(aspect, filename):
    """Triggers the AI analysis and composite generation workflow."""
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    provider = request.form.get("provider", "openai").lower()
    base_name = Path(filename).stem
    _write_analysis_status("starting", 0, base_name, status="analyzing")

    # The analysis image is in a subfolder named after its base name.
    unanalysed_folder = config.UNANALYSED_ROOT / base_name
    src_path = unanalysed_folder / f"{base_name}-analyse.jpg"

    if not src_path.exists():
        msg = f"Artwork file not found for analysis: {filename}"
        flash(msg, "danger")
        if is_ajax: return jsonify({"success": False, "message": msg}), 404
        return redirect(url_for("artwork.artworks"))

    try:
        _write_analysis_status("ai_analysis", 25, base_name, status="running")
        analysis_result = _run_ai_analysis(src_path, provider)
        seo_folder_name = Path(analysis_result.get("processed_folder", "")).name
        if not seo_folder_name: raise RuntimeError("Analysis script did not return a valid folder name.")

        _write_analysis_status("composites", 75, base_name, status="running")
        _generate_composites(uuid.uuid4().hex)

        # On success, clean up the original unanalysed folder
        shutil.rmtree(unanalysed_folder, ignore_errors=True)
        _write_analysis_status("complete", 100, seo_folder_name, status="complete")

        # FIX: Redirect to the correct blueprint for the edit page.
        edit_url = url_for("edit_listing.edit_listing", aspect=aspect, filename=f"{seo_folder_name}.jpg")

        if is_ajax:
            # FIX: Return a JSON response for AJAX requests, passing the redirect URL.
            return jsonify({"success": True, "redirect_url": edit_url, "message": "Analysis complete."})

        flash("✅ Analysis complete! Review your new listing.", "success")
        return redirect(edit_url)

    except Exception as exc:
        # FIX: Properly handle byte-string errors from subprocess and provide clean JSON response.
        error_msg = str(exc)
        if isinstance(getattr(exc, 'args', [None])[0], bytes):
            error_msg = getattr(exc, 'args', [''])[0].decode('utf-8', 'ignore')

        _write_analysis_status("error", 100, base_name, status="error", error=error_msg)
        logging.error(f"Error running analysis for {filename}: {error_msg}", exc_info=True)

        if is_ajax:
             return jsonify({"success": False, "message": f"Analysis failed: {error_msg}"}), 500

        flash(f"❌ Error running analysis: {error_msg}", "danger")
        return redirect(url_for("artwork.artworks"))


# === [ 4. Image & File Serving | artwork-routes-py-4 ] ===
@bp.route(f"/{config.PROCESSED_URL_PATH}/<path:filename>")
def processed_image(filename):
    """Serves images from the 'processed' directory."""
    return send_from_directory(config.PROCESSED_ROOT, filename)

@bp.route(f"/{config.FINALISED_URL_PATH}/<path:filename>")
def finalised_image(filename):
    """Serves images from the 'finalised' directory."""
    return send_from_directory(config.FINALISED_ROOT, filename)

@bp.route(f"/{config.LOCKED_URL_PATH}/<path:filename>")
def locked_image(filename):
    """Serves images from the 'locked' (vault) directory."""
    return send_from_directory(config.ARTWORK_VAULT_ROOT, filename)

@bp.route(f"/{config.MOCKUP_THUMB_URL_PREFIX}/<path:filepath>")
def serve_mockup_thumb(filepath: str):
    """Serves mockup thumbnails, searching across all potential parent directories."""
    for base_dir in [config.PROCESSED_ROOT, config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT]:
        full_path = base_dir / filepath
        if full_path.is_file():
            return send_from_directory(full_path.parent, full_path.name)
    abort(404)

@bp.route(f"/{config.UNANALYSED_IMG_URL_PREFIX}/<path:filename>")
def unanalysed_image(filename: str):
    """Serves images from the 'unanalysed' directory, looking in the correct subfolder."""
    # Correctly search for the image inside its unique subfolder, identified by its base name.
    base_name = Path(filename).stem
    if base_name.endswith(('-thumb', '-analyse')):
        base_name = base_name.rsplit('-', 1)[0]

    search_dir = config.UNANALYSED_ROOT / base_name
    if search_dir.exists() and search_dir.is_dir():
        path = search_dir / filename
        if path.is_file():
            return send_from_directory(path.parent, path.name)

    # Fallback just in case, but the logic above should be primary.
    path_fallback = next((p for p in config.UNANALYSED_ROOT.rglob(filename) if p.is_file()), None)
    if path_fallback:
        return send_from_directory(path_fallback.parent, path_fallback.name)

    abort(404)


# === [ 5. Internal Helpers & Other Routes | artwork-routes-py-5 ] ===
def _process_upload_file(file_storage, dest_folder: Path):
    """Processes a single uploaded file: saves, validates, and creates derivatives."""
    filename = file_storage.filename
    if not filename: return {"success": False, "error": "No filename provided."}

    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_EXTENSIONS:
        return {"success": False, "error": f"Invalid file type: .{ext}"}

    try:
        # Save the original file to its unique folder.
        orig_path = dest_folder / f"{dest_folder.name}.{ext}"
        file_storage.save(orig_path)

        with Image.open(orig_path) as img:
            # FIX: The .load() call is crucial for detecting corrupt files early.
            img.load()
            width, height = img.size

            # Create thumbnail
            thumb_path = dest_folder / f"{dest_folder.name}-thumb.jpg"
            thumb = img.copy()
            thumb.thumbnail(config.THUMBNAIL_SIZE)
            thumb.convert("RGB").save(thumb_path, "JPEG", quality=80)

            # Create analysis version
            analyse_path = dest_folder / f"{dest_folder.name}-analyse.jpg"
            routes_utils.resize_for_analysis(img, analyse_path)

    except Exception as exc:
        logging.error(f"Image processing failed for {filename}: {exc}", exc_info=True)
        shutil.rmtree(dest_folder, ignore_errors=True) # Clean up partial upload
        return {"success": False, "error": f"Image processing failed. The file may be corrupt or not a valid image."}

    qc_data = {
        "original_filename": filename,
        "extension": ext,
        "image_shape": [width, height],
        "filesize_bytes": orig_path.stat().st_size,
        "aspect_ratio": aa.get_aspect_ratio(orig_path),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    qc_path = dest_folder / f"{dest_folder.name}.qc.json"
    qc_path.write_text(json.dumps(qc_data, indent=2))

    return {"success": True, "base": dest_folder.name, "aspect": qc_data["aspect_ratio"], "original": filename}

@bp.route("/next-sku")
def preview_next_sku():
    """A simple endpoint to get the next available SKU for display."""
    return Response(peek_next_sku(config.SKU_TRACKER), mimetype="text/plain")
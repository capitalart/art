# routes/artwork_routes.py
# -*- coding: utf-8 -*-
"""
Artwork-related Flask routes for the ArtNarrator application.

This module powers the entire artwork processing workflow, from initial
upload and AI analysis to mockup review, finalization, and state management.

Table of Contents (ToC)
-----------------------
[artwork-routes-py-1] Imports & Initialisation
    [artwork-routes-py-1a] Imports
    [artwork-routes-py-1b] Blueprint Setup

[artwork-routes-py-2] Health Checks and Status API
    [artwork-routes-py-2a] health_openai
    [artwork-routes-py-2b] health_google
    [artwork-routes-py-2c] _write_analysis_status
    [artwork-routes-py-2d] analysis_status

[artwork-routes-py-3] AI Analysis & Subprocess Helpers
    [artwork-routes-py-3a] _run_ai_analysis
    [artwork-routes-py-3b] _generate_composites

[artwork-routes-py-4] Validation and Data Helpers
    [artwork-routes-py-4a] validate_listing_fields
    [artwork-routes-py-4b] get_categories_for_aspect

[artwork-routes-py-5] Core Navigation & Upload Routes
    [artwork-routes-py-5a] inject_latest_artwork
    [artwork-routes-py-5b] home
    [artwork-routes-py-5c] upload_artwork
    [artwork-routes-py-5d] artworks

[artwork-routes-py-6] Mockup Selection Workflow Routes
    [artwork-routes-py-6a] select
    [artwork-routes-py-6b] regenerate
    [artwork-routes-py-6c] swap
    [artwork-routes-py-6d] proceed

[artwork-routes-py-7] Artwork Analysis Trigger Routes
    [artwork-routes-py-7a] analyze_artwork_route
    [artwork-routes-py-7b] analyze_upload

[artwork-routes-py-8] Artwork Editing and Listing Management
    [artwork-routes-py-8a] edit_listing

[artwork-routes-py-9] Static File and Image Serving Routes
    [artwork-routes-py-9a] processed_image
    [artwork-routes-py-9b] finalised_image
    [artwork-routes-py-9c] locked_image
    [artwork-routes-py-9d] serve_mockup_thumb
    [artwork-routes-py-9e] unanalysed_image
    [artwork-routes-py-9f] composite_img
    [artwork-routes-py-9g] mockup_img

[artwork-routes-py-10] Composite Image Preview Routes
    [artwork-routes-py-10a] composites_preview
    [artwork-routes-py-10b] composites_specific
    [artwork-routes-py-10c] approve_composites

[artwork-routes-py-11] Artwork Finalisation and Gallery Routes
    [artwork-routes-py-11a] finalise_artwork
    [artwork-routes-py-11b] finalised_gallery
    [artwork-routes-py-11c] locked_gallery
    [artwork-routes-py-11d] lock_it_in

[artwork-routes-py-12] Listing State Management (Lock, Unlock, Delete)
    [artwork-routes-py-12a] delete_finalised
    [artwork-routes-py-12b] lock_listing
    [artwork-routes-py-12c] unlock_listing
    [artwork-routes-py-12d] unlock_artwork

[artwork-routes-py-13] Asynchronous API Endpoints
    [artwork-routes-py-13a] update_links
    [artwork-routes-py-13b] reset_sku
    [artwork-routes-py-13c] delete_artwork
    [artwork-routes-py-13d] reword_generic_text_api

[artwork-routes-py-14] File Processing and Utility Helpers
    [artwork-routes-py-14a] preview_next_sku
    [artwork-routes-py-14b] _process_upload_file

[artwork-routes-py-15] Artwork Signing Route
    [artwork-routes-py-15a] sign_artwork_route
"""

# === [ Section 1: Imports & Initialisation | artwork-routes-py-1 ] ===
# Handles all necessary library imports and sets up the Flask Blueprint.
# Cross-references: config.py, helpers/listing_utils.py, routes/utils.py
# ---------------------------------------------------------------------------------

# --- [ 1a: Imports | artwork-routes-py-1a ] ---
# FIX: This section has been corrected to include all necessary imports.
from __future__ import annotations
import json, subprocess, uuid, random, logging, shutil, os, traceback, datetime, time, sys
from pathlib import Path
from PIL import Image
import google.generativeai as genai
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, send_from_directory, abort, Response, jsonify,
)
import re

# Local Application Imports
import config
from helpers.listing_utils import (
    resolve_listing_paths,
    create_unanalysed_subfolder,
    cleanup_unanalysed_folders,
    load_json_file_safe,
    generate_public_image_urls,
    remove_artwork_from_registry,
    delete_artwork as delete_artwork_files,
    update_artwork_registry,
)
import scripts.analyze_artwork as aa
from scripts import signing_service
from . import utils
from utils.logger_utils import log_action
from utils.sku_assigner import peek_next_sku
from utils import ai_services
from .utils import (
    ALLOWED_COLOURS_LOWER, read_generic_text, clean_terms, infer_sku_from_filename,
    is_finalised_image, get_allowed_colours, update_listing_paths
)


# --- [ 1b: Blueprint Setup | artwork-routes-py-1b ] ---
bp = Blueprint("artwork", __name__)


# === [ Section 2: Health Checks and Status API | artwork-routes-py-2 ] ===
# Endpoints for monitoring the health of external services (OpenAI, Google)
# and for providing real-time status updates on background analysis jobs.
# ---------------------------------------------------------------------------------

# --- [ 2a: health_openai | artwork-routes-py-2a ] ---
@bp.get("/health/openai")
def health_openai():
    """Provides a health check endpoint for the OpenAI API connection."""
    logger = logging.getLogger(__name__)
    try:
        aa.client.models.list()
        return jsonify({"ok": True})
    except Exception as exc:
        logger.error("OpenAI health check failed: %s", exc)
        error = str(exc)
        if config.DEBUG:
            error += "\n" + traceback.format_exc()
        return jsonify({"ok": False, "error": error}), 500


# --- [ 2b: health_google | artwork-routes-py-2b ] ---
@bp.get("/health/google")
def health_google():
    """Provides a health check endpoint for the Google Gemini API connection."""
    logger = logging.getLogger(__name__)
    try:
        genai.list_models()
        return jsonify({"ok": True})
    except Exception as exc:
        logger.error("Google health check failed: %s", exc)
        error = str(exc)
        if config.DEBUG:
            error += "\n" + traceback.format_exc()
        return jsonify({"ok": False, "error": error}), 500


# --- [ 2c: _write_analysis_status | artwork-routes-py-2c ] ---
def _write_analysis_status(step: str, percent: int, file: str | None = None, status: str | None = None, error: str | None = None) -> None:
    """
    Writes the current progress of an analysis job to a shared JSON file.
    This file is polled by the frontend to update the UI modal.
    """
    logger = logging.getLogger(__name__)
    payload = {"step": step, "percent": percent, "file": file, "status": status, "error": error}
    try:
        config.ANALYSIS_STATUS_FILE.write_text(json.dumps({k: v for k, v in payload.items() if v is not None}))
    except Exception as exc:
        logger.error("Failed writing analysis status: %s", exc)


# --- [ 2d: analysis_status | artwork-routes-py-2d ] ---
@bp.route("/status/analyze")
def analysis_status():
    """Returns the content of the analysis status JSON file for frontend polling."""
    return Response(config.ANALYSIS_STATUS_FILE.read_text(), mimetype="application/json")


# === [ Section 3: AI Analysis & Subprocess Helpers | artwork-routes-py-3 ] ===
# Helper functions for invoking external Python scripts (like AI analysis
# and mockup generation) as separate processes.
# ---------------------------------------------------------------------------------

# --- [ 3a: _run_ai_analysis | artwork-routes-py-3a ] ---
def _run_ai_analysis(img_path: Path, provider: str) -> dict:
    """
    Executes the AI analysis script as a subprocess and captures its JSON output.

    Args:
        img_path: The absolute path to the image file to be analyzed.
        provider: The AI provider to use (e.g., 'openai').

    Returns:
        A dictionary parsed from the script's JSON output.
    """
    logger = logging.getLogger("art_analysis")
    logger.info("[DEBUG] _run_ai_analysis: img_path=%s provider=%s", img_path, provider)

    if provider == "openai":
        cmd = [sys.executable, str(config.ANALYZE_SCRIPT_PATH), str(img_path), "--json-output"]
    else:
        raise ValueError(f"Unknown provider: {provider}")

    logger.info("[DEBUG] Subprocess cmd: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        msg = (result.stderr or "Unknown error").strip()
        raise RuntimeError(f"AI analysis failed: {msg}")
    
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s", e)
        raise RuntimeError("AI analysis output could not be parsed.") from e


# --- [ 3b: _generate_composites | artwork-routes-py-3b ] ---
def _generate_composites(log_id: str) -> None:
    """Triggers the queue-based composite/mockup generation script as a subprocess."""
    cmd = [sys.executable, str(config.GENERATE_SCRIPT_PATH)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=config.BASE_DIR, timeout=600)
    composite_log = config.LOGS_DIR / "composite-generation-logs" / f"composite_gen_{log_id}.log"
    composite_log.parent.mkdir(exist_ok=True, parents=True)
    composite_log.write_text(f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}")
    if result.returncode != 0:
        raise RuntimeError(f"Composite generation failed ({result.returncode})")


# === [ Section 4: Validation and Data Helpers | artwork-routes-py-4 ] ===
# Functions for validating form data and retrieving data needed by templates.
# ---------------------------------------------------------------------------------

# --- [ 4a: validate_listing_fields | artwork-routes-py-4a ] ---
def validate_listing_fields(data: dict, generic_text: str) -> list[str]:
    """
    Validates all fields from the edit listing form against business rules.

    Args:
        data: A dictionary of form data.
        generic_text: The boilerplate text block to check for inclusion.

    Returns:
        A list of string error messages. An empty list indicates success.
    """
    errors: list[str] = []
    title = data.get("title", "").strip()
    if not title: errors.append("Title cannot be blank")
    if len(title) > 140: errors.append("Title exceeds 140 characters")
    tags = data.get("tags", [])
    if len(tags) > 13: errors.append("Too many tags (max 13)")
    for t in tags:
        if not t or len(t) > 20: errors.append(f"Invalid tag: '{t}'")
        if not re.fullmatch(r"[A-Za-z0-9 ]+", t): errors.append(f"Tag has invalid characters: '{t}'")
    seo_filename = data.get("seo_filename", "")
    if len(seo_filename) > 70: errors.append("SEO filename exceeds 70 characters")
    if not re.search(r"-by-robin-custance-RJC-[A-Za-z0-9-]+\.jpg$", seo_filename, re.IGNORECASE):
        errors.append("SEO filename must end with '-by-robin-custance-RJC-XXXX.jpg'")
    sku = data.get("sku", "")
    if not sku: errors.append("SKU is required")
    if sku and not sku.startswith("RJC-"): errors.append("SKU must start with 'RJC-'")
    if sku and utils.infer_sku_from_filename(seo_filename or "") != sku:
        errors.append("SKU must match value in SEO filename")
    try:
        if abs(float(data.get("price")) - 18.27) > 1e-2: errors.append("Price must be 18.27")
    except (ValueError, TypeError): errors.append("Price must be a number (18.27)")
    for key in ("primary_colour", "secondary_colour"):
        col = data.get(key, "").strip()
        if not col: errors.append(f"{key.replace('_', ' ').title()} is required")
        elif col.lower() not in utils.ALLOWED_COLOURS_LOWER: errors.append(f"{key.replace('_', ' ').title()} invalid")
    images = [i.strip() for i in data.get("images", []) if str(i).strip()]
    if not images: errors.append("At least one image required")
    desc = data.get("description", "").strip()
    if len(desc.split()) < 400: errors.append("Description must be at least 400 words")
    if generic_text and "About the Artist – Robin Custance".lower() not in " ".join(desc.split()).lower():
        errors.append("Description must include the correct generic context block.")
    return errors


# --- [ 4b: get_categories_for_aspect | artwork-routes-py-4b ] ---
def get_categories_for_aspect(aspect: str) -> list[str]:
    """Returns a sorted list of available mockup category names for a given aspect ratio."""
    base = config.MOCKUPS_CATEGORISED_DIR / aspect
    return sorted([f.name for f in base.iterdir() if f.is_dir()]) if base.exists() else []


# === [ Section 5: Core Navigation & Upload Routes | artwork-routes-py-5 ] ===
# Handles the main UI pages: the homepage, the artwork gallery/dashboard,
# and the file upload page.
# ---------------------------------------------------------------------------------

# --- [ 5a: inject_latest_artwork | artwork-routes-py-5a ] ---
@bp.app_context_processor
def inject_latest_artwork():
    """Injects data about the latest analyzed artwork into all templates."""
    return dict(latest_artwork=utils.latest_analyzed_artwork())


# --- [ 5b: home | artwork-routes-py-5b ] ---
@bp.route("/")
def home():
    """Renders the main home/dashboard page."""
    return render_template("index.html", menu=utils.get_menu())


# --- [ 5c: upload_artwork | artwork-routes-py-5c ] ---
@bp.route("/upload", methods=["GET", "POST"])
def upload_artwork():
    """Handles new artwork file uploads and runs initial QC checks."""
    if request.method == "POST":
        files = request.files.getlist("images")
        results = []
        user = session.get("username")
        
        for f in files:
            folder = create_unanalysed_subfolder(f.filename)
            try:
                res = _process_upload_file(f, folder)
            except Exception as exc:
                logging.getLogger(__name__).error("Upload failed for %s: %s", f.filename, exc)
                res = {"original": f.filename, "success": False, "error": str(exc)}
            
            log_action("upload", res.get("original", f.filename), user, res.get("error", "uploaded"), status="success" if res.get("success") else "fail")
            results.append(res)
        
        if "XMLHttpRequest" in request.headers.get("X-Requested-With", ""):
            return jsonify(results)
        
        if any(r["success"] for r in results):
            flash(f"Uploaded {sum(1 for r in results if r['success'])} file(s) successfully", "success")
        for r in [r for r in results if not r["success"]]:
            flash(f"{r['original']}: {r['error']}", "danger")

        return redirect(url_for("artwork.artworks"))
        
    return render_template("upload.html", menu=utils.get_menu())


# --- [ 5d: artworks | artwork-routes-py-5d ] ---
@bp.route("/artworks")
def artworks():
    """Displays galleries of artworks in 'Ready to Analyze', 'Processed', and 'Finalised' states."""
    processed, processed_names = utils.list_processed_artworks()
    ready = utils.list_ready_to_analyze(processed_names)
    finalised = utils.list_finalised_artworks()
    return render_template("artworks.html", ready_artworks=ready, processed_artworks=processed, finalised_artworks=finalised, menu=utils.get_menu())
    

# === [ Section 6: Mockup Selection Workflow Routes | artwork-routes-py-6 ] ===
# DEPRECATED: These routes were part of an older, manual mockup selection flow.
# They are kept for reference but are no longer active in the main UI.
# ---------------------------------------------------------------------------------

# --- [ 6a: select | artwork-routes-py-6a ] ---
@bp.route("/select", methods=["GET", "POST"])
def select():
    """(DEPRECATED) Displays the old mockup selection interface."""
    if "slots" not in session or request.args.get("reset") == "1":
        utils.init_slots()
    slots = session["slots"]
    options = utils.compute_options(slots)
    zipped = list(zip(slots, options))
    return render_template("mockup_selector.html", zipped=zipped, menu=utils.get_menu())


# --- [ 6b: regenerate | artwork-routes-py-6b ] ---
@bp.route("/regenerate", methods=["POST"])
def regenerate():
    """(DEPRECATED) Regenerates a random mockup for a specific slot."""
    slot_idx = int(request.form["slot"])
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        cat = slots[slot_idx]["category"]
        slots[slot_idx]["image"] = utils.random_image(cat, "4x5")
        session["slots"] = slots
    return redirect(url_for("artwork.select"))


# --- [ 6c: swap | artwork-routes-py-6c ] ---
@bp.route("/swap", methods=["POST"])
def swap():
    """(DEPRECATED) Swaps a mockup slot to a new category."""
    slot_idx = int(request.form["slot"])
    new_cat = request.form["new_category"]
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        slots[slot_idx]["category"] = new_cat
        slots[slot_idx]["image"] = utils.random_image(new_cat, "4x5")
        session["slots"] = slots
    return redirect(url_for("artwork.select"))


# --- [ 6d: proceed | artwork-routes-py-6d ] ---
@bp.route("/proceed", methods=["POST"])
def proceed():
    """(DEPRECATED) Finalises mockup selections and triggers composite generation."""
    flash("Composite generation process initiated!", "success")
    latest = utils.latest_composite_folder()
    if latest:
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    return redirect(url_for("artwork.composites_preview"))


# === [ Section 7: Artwork Analysis Trigger Routes | artwork-routes-py-7 ] ===
# These routes handle the initiation of the AI analysis process. They are
# triggered from the artwork gallery page.
# ---------------------------------------------------------------------------------

# --- [ 7a: analyze_artwork_route | artwork-routes-py-7a ] ---
@bp.route("/analyze/<aspect>/<filename>", methods=["POST"], endpoint="analyze_artwork")
def analyze_artwork_route(aspect, filename):
    """
    Runs AI analysis on a given artwork file. This can be a fresh analysis
    from the 'unanalysed' folder or a re-analysis of a 'processed' artwork.
    """
    logger, provider = logging.getLogger(__name__), request.form.get("provider", "openai").lower()
    base_name = Path(filename).name
    _write_analysis_status("starting", 0, base_name, status="analyzing")
    is_ajax = "XMLHttpRequest" in request.headers.get("X-Requested-With", "")

    src_path = next((p for p in config.UNANALYSED_ROOT.rglob(base_name) if p.is_file()), None)
    
    old_processed_folder_path = None
    is_reanalysis = False
    
    if not src_path:
        try:
            seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
            potential_path = config.PROCESSED_ROOT / seo_folder / f"{seo_folder}.jpg"
            if potential_path.exists():
                src_path = potential_path
                is_reanalysis = True
                old_processed_folder_path = src_path.parent
        except FileNotFoundError: pass

    if not src_path or not src_path.exists():
        flash(f"Artwork file not found: {filename}", "danger")
        if is_ajax: return jsonify({"success": False, "error": "Artwork file not found"}), 404
        return redirect(url_for("artwork.artworks"))

    try:
        analysis_result = _run_ai_analysis(src_path, provider)
        new_seo_folder_name = Path(analysis_result.get("processed_folder", "")).name
        
        if not new_seo_folder_name: raise RuntimeError("Analysis script did not return a valid folder name.")

        _generate_composites(uuid.uuid4().hex)
        
        if config.UNANALYSED_ROOT in src_path.parents:
            shutil.rmtree(src_path.parent, ignore_errors=True)
            log_action("cleanup", src_path.parent.name, session.get("username"), "Deleted unanalysed artwork folder.")
            logger.info(f"Cleaned up unanalysed source folder: {src_path.parent}")
        
        new_folder_path = config.PROCESSED_ROOT / new_seo_folder_name
        if is_reanalysis and old_processed_folder_path and old_processed_folder_path.exists() and old_processed_folder_path != new_folder_path:
            shutil.rmtree(old_processed_folder_path)
            log_action("cleanup", old_processed_folder_path.name, session.get("username"), "Deleted old folder after re-analysis.")
            logger.info(f"Cleaned up old processed folder after re-analysis: {old_processed_folder_path}")

    except Exception as exc:
        logger.error(f"Error running analysis for {filename}: {exc}", exc_info=True)
        flash(f"❌ Error running analysis: {exc}", "danger")
        if is_ajax: return jsonify({"success": False, "error": str(exc)}), 500
        return redirect(url_for("artwork.artworks"))

    redirect_filename = f"{new_seo_folder_name}.jpg"
    redirect_url = url_for("artwork.edit_listing", aspect=aspect, filename=redirect_filename)

    if is_ajax:
        return jsonify({
            "success": True,
            "message": "Analysis complete.",
            "redirect_url": redirect_url
        })
    
    return redirect(redirect_url)


# --- [ 7b: analyze_upload | artwork-routes-py-7b ] ---
@bp.post("/analyze-upload/<base>")
def analyze_upload(base):
    """(DEPRECATED) Legacy route to analyze an uploaded image from the unanalysed folder."""
    uid, rec = utils.get_record_by_base(base)
    if not rec:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
        
    folder = Path(rec["current_folder"])
    qc_path = folder / f"{base}.qc.json"
    qc = load_json_file_safe(qc_path)
    orig_path = folder / f"{base}.{qc.get('extension', 'jpg')}"
    provider = request.form.get("provider", "openai")
    
    _write_analysis_status("starting", 0, orig_path.name, status="analyzing")
    try:
        analysis_result = _run_ai_analysis(orig_path, provider)
        processed_folder_path = Path(analysis_result.get("processed_folder", ""))
        seo_folder = processed_folder_path.name
        
        if not seo_folder:
            raise RuntimeError("Analysis script did not return a valid folder name.")
            
        _write_analysis_status("generating", 60, orig_path.name, status="analyzing")
        _generate_composites(uuid.uuid4().hex)
        
    except Exception as e:
        flash(f"❌ Error running analysis: {e}", "danger")
        _write_analysis_status("failed", 100, orig_path.name, status="failed", error=str(e))
        return redirect(url_for("artwork.artworks"))
    
    cleanup_unanalysed_folders()
    _write_analysis_status("done", 100, orig_path.name, status="complete")
    
    redirect_filename = f"{seo_folder}.jpg"
    return redirect(url_for("artwork.edit_listing", aspect=qc.get("aspect_ratio", ""), filename=redirect_filename))


# === [ Section 8: Artwork Editing and Listing Management | artwork-routes-py-8 ] ===
# The main route for editing an artwork's listing details, handling both
# displaying the form (GET) and saving changes (POST).
# ---------------------------------------------------------------------------------

# --- [ 8a: edit_listing | artwork-routes-py-8a ] ---
@bp.route("/edit-listing/<aspect>/<filename>", methods=["GET", "POST"])
def edit_listing(aspect, filename):
    """Displays and updates a processed or finalised artwork listing."""
    try:
        seo_folder, folder, listing_path, finalised = resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))
    
    data = load_json_file_safe(listing_path)
    is_locked_in_vault = config.ARTWORK_VAULT_ROOT in folder.parents

    stage = "vault" if (config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}").exists() else "processed"
    public_image_urls = generate_public_image_urls(seo_folder, stage)

    if request.method == "POST":
        form_data = {
            "title": request.form.get("title", "").strip(),
            "description": request.form.get("description", "").strip(),
            "tags": [t.strip() for t in request.form.get("tags", "").split(',') if t.strip()],
            "materials": [m.strip() for m in request.form.get("materials", "").split(',') if m.strip()],
            "images": [i.strip() for i in request.form.get("images", "").splitlines() if i.strip()],
        }
        data.update(form_data)
        with open(listing_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        flash("Listing updated", "success")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))

    artwork = utils.populate_artwork_data_from_json(data, seo_folder)
    artwork["images"] = "\n".join(public_image_urls)
    mockups = utils.get_mockup_details_for_template(data.get("mockups", []), folder, seo_folder, aspect)
    
    return render_template(
        "edit_listing.html",
        artwork=artwork,
        aspect=aspect,
        filename=filename,
        seo_folder=seo_folder,
        mockups=mockups,
        finalised=finalised,
        locked=data.get("locked", False),
        is_locked_in_vault=is_locked_in_vault,
        editable=not data.get("locked", False),
        public_image_urls=public_image_urls,
        cache_ts=int(time.time()),
    )


# === [ Section 9: Static File and Image Serving Routes | artwork-routes-py-9 ] ===
# These routes serve images from various processing directories. They are essential
# for displaying thumbnails and full-size images throughout the application.
# ---------------------------------------------------------------------------------

# --- [ 9a: processed_image | artwork-routes-py-9a ] ---
@bp.route(f"/{config.PROCESSED_URL_PATH}/<path:filename>")
def processed_image(filename):
    """Serves images from the 'processed-artwork' directory."""
    return send_from_directory(config.PROCESSED_ROOT, filename)


# --- [ 9b: finalised_image | artwork-routes-py-9b ] ---
@bp.route(f"/{config.FINALISED_URL_PATH}/<path:filename>")
def finalised_image(filename):
    """Serves images from the 'finalised-artwork' directory."""
    return send_from_directory(config.FINALISED_ROOT, filename)


# --- [ 9c: locked_image | artwork-routes-py-9c ] ---
@bp.route(f"/{config.LOCKED_URL_PATH}/<path:filename>")
def locked_image(filename):
    """Serves images from the 'artwork-vault' (locked) directory."""
    return send_from_directory(config.ARTWORK_VAULT_ROOT, filename)


# --- [ 9d: serve_mockup_thumb | artwork-routes-py-9d ] ---
@bp.route(f"/{config.MOCKUP_THUMB_URL_PREFIX}/<path:filepath>")
def serve_mockup_thumb(filepath: str):
    """Serves mockup thumbnail images from any potential artwork directory."""
    for base_dir in [config.PROCESSED_ROOT, config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT]:
        full_path = base_dir / filepath
        if full_path.is_file():
            return send_from_directory(full_path.parent, full_path.name)
    abort(404)


# --- [ 9e: unanalysed_image | artwork-routes-py-9e ] ---
@bp.route(f"/{config.UNANALYSED_IMG_URL_PREFIX}/<filename>")
def unanalysed_image(filename: str):
    """Serves images from the 'unanalysed-artwork' directory."""
    path = next((p for p in config.UNANALYSED_ROOT.rglob(filename) if p.is_file()), None)
    if path:
        return send_from_directory(path.parent, path.name)
    abort(404)


# --- [ 9f: composite_img | artwork-routes-py-9f ] ---
@bp.route(f"/{config.COMPOSITE_IMG_URL_PREFIX}/<folder>/<filename>")
def composite_img(folder, filename):
    """(DEPRECATED) Serves a specific composite image."""
    return send_from_directory(config.PROCESSED_ROOT / folder, filename)


# --- [ 9g: mockup_img | artwork-routes-py-9g ] ---
@bp.route("/mockup-img/<category>/<filename>")
def mockup_img(category, filename):
    """Serves a mockup template image from the central inputs directory."""
    return send_from_directory(config.MOCKUPS_INPUT_DIR / category, filename)


# === [ Section 10: Composite Image Preview Routes | artwork-routes-py-10 ] ===
# Routes for the composite/mockup preview page.
# ---------------------------------------------------------------------------------

# --- [ 10a: composites_preview | artwork-routes-py-10a ] ---
@bp.route("/composites")
def composites_preview():
    """Redirects to the latest composite folder or the main artworks page."""
    latest = utils.latest_composite_folder()
    if latest:
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    flash("No composites found", "warning")
    return redirect(url_for("artwork.artworks"))


# --- [ 10b: composites_specific | artwork-routes-py-10b ] ---
@bp.route("/composites/<seo_folder>")
def composites_specific(seo_folder):
    """Displays the composite images for a specific artwork."""
    folder = config.PROCESSED_ROOT / seo_folder
    json_path = folder / f"{seo_folder}-listing.json"
    images = []
    if json_path.exists():
        listing = load_json_file_safe(json_path)
        images = utils.get_mockup_details_for_template(
            listing.get("mockups", []), folder, seo_folder, listing.get("aspect_ratio", "")
        )
    return render_template(
        "composites_preview.html",
        images=images,
        folder=seo_folder,
        menu=utils.get_menu(),
    )


# --- [ 10c: approve_composites | artwork-routes-py-10c ] ---
@bp.route("/approve_composites/<seo_folder>", methods=["POST"])
def approve_composites(seo_folder):
    """Approves composites and redirects to the edit/review page."""
    listing_path = next((config.PROCESSED_ROOT / seo_folder).glob("*-listing.json"), None)
    if listing_path:
        data = load_json_file_safe(listing_path)
        aspect = data.get("aspect_ratio", "4x5")
        filename = data.get("seo_filename", f"{seo_folder}.jpg")
        flash("Composites approved. Please review and finalise.", "success")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))
    flash("Could not find listing data.", "danger")
    return redirect(url_for("artwork.artworks"))


# === [ Section 11: Artwork Finalisation and Gallery Routes | artwork-routes-py-11 ] ===
# Routes for the final step of the workflow: moving an artwork to the
# 'finalised' directory, and viewing the finalised/locked galleries.
# ---------------------------------------------------------------------------------

# --- [ 11a: finalise_artwork | artwork-routes-py-11a ] ---
@bp.route("/finalise-artwork/<seo_folder>", methods=["POST"])
def finalise_artwork(seo_folder):
    """Move a processed artwork into the locked vault and refresh its paths."""
    processed_path = config.PROCESSED_ROOT / seo_folder
    vault_path = config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}"
    try:
        if not processed_path.exists():
            raise FileNotFoundError(f"Processed artwork '{seo_folder}' not found.")
        shutil.move(str(processed_path), str(vault_path))
        listing_file = vault_path / f"{seo_folder}-listing.json"
        utils.update_listing_paths(listing_file, config.PROCESSED_ROOT, config.ARTWORK_VAULT_ROOT)
        data = load_json_file_safe(listing_file)
        data["locked"] = True
        data["images"] = generate_public_image_urls(seo_folder, "vault")
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        update_artwork_registry(seo_folder, vault_path, "locked")
        log_action("finalise", seo_folder, session.get("username"), "Artwork finalised and moved to vault")
        flash(f"Artwork '{seo_folder}' successfully finalised!", "success")
    except Exception as exc:
        flash(f"Error during finalisation: {exc}", "danger")

    return redirect(url_for("artwork.locked_gallery"))


# --- [ 11b: finalised_gallery | artwork-routes-py-11b ] ---
@bp.route("/finalised")
def finalised_gallery():
    """Displays all finalised artworks in a gallery view."""
    artworks = [a for a in utils.get_all_artworks() if a['status'] == 'finalised']
    return render_template("finalised.html", artworks=artworks, menu=utils.get_menu())


# --- [ 11c: locked_gallery | artwork-routes-py-11c ] ---
@bp.route("/locked")
def locked_gallery():
    """Displays all locked artworks from the vault."""
    locked_items = [a for a in utils.get_all_artworks() if a.get('locked')]
    return render_template("locked.html", artworks=locked_items, menu=utils.get_menu())


# --- [ 11d: lock_it_in | artwork-routes-py-11d ] ---
@bp.post("/lock-it-in/<seo_folder>")
def lock_it_in(seo_folder: str):
    """Mark a processed artwork as ready while keeping it in place."""
    processed_path = config.PROCESSED_ROOT / seo_folder
    listing_file = processed_path / f"{seo_folder}-listing.json"
    try:
        utils.assign_or_get_sku(listing_file, config.SKU_TRACKER)
        data = load_json_file_safe(listing_file)
        data["locked"] = True
        data["images"] = generate_public_image_urls(seo_folder, "processed")
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        update_artwork_registry(seo_folder, processed_path, "processed")
        log_action("lock-it-in", seo_folder, session.get("username"), "Artwork locked in")
        flash("Artwork details locked. Ready for finalisation.", "success")
    except Exception as e:
        flash(f"Error locking in artwork: {e}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect='processed', filename=f"{seo_folder}.jpg"))


# === [ Section 12: Listing State Management (Lock, Unlock, Delete) | artwork-routes-py-12 ] ===
# Routes for managing the lifecycle of a finalised artwork: locking (moving
# to vault), unlocking (making editable again), and deletion.
# ---------------------------------------------------------------------------------

# --- [ 12a: delete_finalised | artwork-routes-py-12a ] ---
@bp.post("/finalise/delete/<aspect>/<filename>")
def delete_finalised(aspect, filename):
    """Deletes a finalised or locked artwork and all its files."""
    try:
        _, folder, listing_file, _ = resolve_listing_paths(aspect, filename, allow_locked=True)
        info = load_json_file_safe(listing_file)
        if info.get("locked") and request.form.get("confirm") != "DELETE":
            flash("Type DELETE to confirm deletion of a locked item.", "warning")
            return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))
        
        shutil.rmtree(folder)
        flash("Artwork deleted successfully.", "success")
        log_action("delete", filename, session.get("username"), f"Deleted folder {folder}")
    except FileNotFoundError:
        flash("Artwork not found.", "danger")
    except Exception as e:
        flash(f"Delete failed: {e}", "danger")
    return redirect(url_for("artwork.finalised_gallery"))


# --- [ 12b: lock_listing | artwork-routes-py-12b ] ---
@bp.post("/lock/<aspect>/<filename>")
def lock_listing(aspect, filename):
    """Locks an artwork by moving it to the 'artwork-vault' directory."""
    try:
        seo, folder, listing_path, finalised = resolve_listing_paths(aspect, filename)
        if not finalised:
            flash("Artwork must be finalised before locking.", "danger")
            return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))
        
        target = config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo}"
        config.ARTWORK_VAULT_ROOT.mkdir(parents=True, exist_ok=True)
        if target.exists(): shutil.rmtree(target)
        shutil.move(str(folder), str(target))

        new_listing_path = target / listing_path.name
        utils.update_listing_paths(new_listing_path, folder, target)
        data = load_json_file_safe(new_listing_path)
        data["locked"] = True
        data["images"] = generate_public_image_urls(seo, "vault")
        with open(new_listing_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        flash("Artwork locked.", "success")
        log_action("lock", filename, session.get("username"), "locked artwork")
    except Exception as exc:
        flash(f"Failed to lock: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


# --- [ 12c: unlock_listing | artwork-routes-py-12c ] ---
@bp.post("/unlock/<aspect>/<filename>")
def unlock_listing(aspect, filename):
    """Unlocks an artwork, making it editable again but keeping files in the vault."""
    if request.form.get("confirm_unlock") != "UNLOCK":
        flash("Incorrect confirmation text. Please type UNLOCK to proceed.", "warning")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))

    try:
        _, _, listing_path, _ = resolve_listing_paths(aspect, filename, allow_locked=True)
        if config.ARTWORK_VAULT_ROOT not in listing_path.parents:
            flash("Cannot unlock an item that is not in the vault.", "danger")
            return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))

        with open(listing_path, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data["locked"] = False
            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()
        
        log_action("unlock", filename, session.get("username"), "unlocked artwork")
        flash("Artwork unlocked and is now editable. File paths remain unchanged.", "success")
    
    except FileNotFoundError:
        flash("Locked artwork not found.", "danger")
        return redirect(url_for("artwork.artworks"))
    except Exception as exc:
        log_action("unlock", filename, session.get("username"), "unlock failed", status="fail", error=str(exc))
        flash(f"Failed to unlock: {exc}", "danger")
        
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


# --- [ 12d: unlock_artwork | artwork-routes-py-12d ] ---
@bp.route("/unlock-artwork/<seo_folder>", methods=["POST"])
def unlock_artwork(seo_folder: str):
    """Move a locked artwork from the vault back to processed state."""
    locked_path = config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}"
    processed_path = config.PROCESSED_ROOT / seo_folder
    try:
        shutil.move(str(locked_path), str(processed_path))
        listing_file = processed_path / f"{seo_folder}-listing.json"
        utils.update_listing_paths(listing_file, config.ARTWORK_VAULT_ROOT, config.PROCESSED_ROOT)
        data = load_json_file_safe(listing_file)
        data["locked"] = False
        data["images"] = generate_public_image_urls(seo_folder, "processed")
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        update_artwork_registry(seo_folder, processed_path, "processed")
        flash("Artwork successfully unlocked.", "success")
    except Exception as exc:
        flash(f"Error during unlocking: {exc}", "danger")
    return redirect(url_for("artwork.artworks"))


# === [ Section 13: Asynchronous API Endpoints | artwork-routes-py-13 ] ===
# API-style endpoints called via JavaScript from the frontend to perform
# specific, targeted actions without a full page reload.
# ---------------------------------------------------------------------------------

# --- [ 13a: update_links | artwork-routes-py-13a ] ---
@bp.post("/update-links/<aspect>/<filename>")
def update_links(aspect, filename):
    """Regenerates the image URL list from disk and returns it as JSON."""
    wants_json = "application/json" in request.headers.get("Accept", "")
    try:
        seo_folder, _, listing_file, _ = resolve_listing_paths(aspect, filename)
        stage = "vault" if (config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}").exists() else "processed"
        data = load_json_file_safe(listing_file)
        data["images"] = generate_public_image_urls(seo_folder, stage)
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        msg = "Image links updated"
        if wants_json: return jsonify({"success": True, "message": msg, "images": data["images"]})
        flash(msg, "success")
    except Exception as e:
        msg = f"Failed to update links: {e}"
        if wants_json: return jsonify({"success": False, "message": msg, "images": []}), 500
        flash(msg, "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


# --- [ 13b: reset_sku | artwork-routes-py-13b ] ---
@bp.post("/reset-sku/<aspect>/<filename>")
def reset_sku(aspect, filename):
    """Forces the assignment of a new SKU for a given artwork."""
    try:
        _, _, listing, _ = resolve_listing_paths(aspect, filename)
        utils.assign_or_get_sku(listing, config.SKU_TRACKER, force=True)
        flash("SKU has been reset.", "success")
    except Exception as exc:
        flash(f"Failed to reset SKU: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


# --- [ 13c: delete_artwork | artwork-routes-py-13c ] ---
@bp.route("/delete-artwork/<seo_folder>", methods=["POST"])
def delete_artwork(seo_folder: str):
    """Completely remove an artwork folder and registry entry."""
    user = session.get("username", "unknown")
    log_action("delete", seo_folder, user, f"Initiating delete for '{seo_folder}'")
    try:
        if delete_artwork_files(seo_folder):
            flash(f"Artwork '{seo_folder}' deleted successfully.", "success")
            log_action("delete", seo_folder, user, "Delete process completed.")
        else:
            flash(f"Failed to delete artwork '{seo_folder}'.", "danger")
            log_action("delete", seo_folder, user, "Delete failed", status="fail")
    except Exception as exc:
        flash(f"An error occurred during deletion: {exc}", "danger")
        log_action("delete", seo_folder, user, str(exc), status="fail")
    return redirect(url_for("artwork.artworks"))


# --- [ 13d: reword_generic_text_api | artwork-routes-py-13d ] ---
@bp.post("/api/reword-generic-text")
def reword_generic_text_api():
    """Handles an async request to reword the generic part of a description using AI."""
    logger = logging.getLogger(__name__)
    data = request.json

    provider = data.get("provider")
    artwork_desc = data.get("artwork_description")
    generic_text = data.get("generic_text")

    if not all([provider, artwork_desc, generic_text]):
        logger.error("Reword API call missing required data.")
        return jsonify({"success": False, "error": "Missing required data."}), 400

    try:
        reworded_text = ai_services.call_ai_to_reword_text(
            provider=provider,
            artwork_description=artwork_desc,
            generic_text=generic_text
        )
        logger.info(f"Successfully reworded text with {provider}.")
        return jsonify({"success": True, "reworded_text": reworded_text})

    except Exception as e:
        logger.error(f"Failed to reword generic text: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# === [ Section 14: File Processing and Utility Helpers | artwork-routes-py-14 ] ===
# Internal helper functions used by the routes in this file, primarily for
# handling the initial processing of uploaded files.
# ---------------------------------------------------------------------------------

# --- [ 14a: preview_next_sku | artwork-routes-py-14a ] ---
@bp.route("/next-sku")
def preview_next_sku():
    """Returns the next available SKU without consuming it."""
    return Response(peek_next_sku(config.SKU_TRACKER), mimetype="text/plain")


# --- [ 14b: _process_upload_file | artwork-routes-py-14b ] ---
def _process_upload_file(file_storage, dest_folder):
    """Validates, saves, and preprocesses a single uploaded file."""
    filename = file_storage.filename
    if not filename: return {"original": filename, "success": False, "error": "No filename"}

    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_EXTENSIONS:
        return {"original": filename, "success": False, "error": "Invalid file type"}
    
    data = file_storage.read()
    if len(data) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        return {"original": filename, "success": False, "error": "File too large"}

    safe, unique, uid = utils.prettify_slug(Path(filename).stem), uuid.uuid4().hex[:8], uuid.uuid4().hex
    base = f"{safe}-{unique}"
    dest_folder.mkdir(parents=True, exist_ok=True)
    orig_path = dest_folder / f"{base}.{ext}"

    try:
        orig_path.write_bytes(data)
        with Image.open(orig_path) as img:
            width, height = img.size
            thumb_path = dest_folder / f"{base}-thumb.jpg"
            thumb = img.copy()
            thumb.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
            thumb.save(thumb_path, "JPEG", quality=80)
            analyse_path = dest_folder / f"{base}-analyse.jpg"
            utils.resize_for_analysis(img, analyse_path)
    except Exception as exc:
        logging.getLogger(__name__).error("Image processing failed: %s", exc)
        return {"original": filename, "success": False, "error": "Image processing failed"}
    
    qc_data = {
        "original_filename": filename, "extension": ext, "image_shape": [width, height],
        "filesize_bytes": len(data), "aspect_ratio": aa.get_aspect_ratio(orig_path),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    qc_path = dest_folder / f"{base}.qc.json"
    qc_path.write_text(json.dumps(qc_data, indent=2))

    utils.register_new_artwork(uid, f"{base}.{ext}", dest_folder, [orig_path.name, thumb_path.name, analyse_path.name, qc_path.name], "unanalysed", base)
    
    return {"success": True, "base": base, "aspect": qc_data["aspect_ratio"], "uid": uid, "original": filename}


# === [ Section 15: Artwork Signing Route | artwork-routes-py-15 ] ===
# Endpoint for applying a digital signature to an artwork.
# ---------------------------------------------------------------------------------

# --- [ 15a: sign_artwork_route | artwork-routes-py-15a ] ---
@bp.post("/sign-artwork/<base_name>")
def sign_artwork_route(base_name: str):
    """
    Finds an unanalysed artwork by its base name, applies a smart
    signature, and replaces the original file and its derivatives.
    """
    logger = logging.getLogger(__name__)
    source_path = next((p for p in config.UNANALYSED_ROOT.rglob(f"{base_name}.*") if "-thumb" not in p.name and "-analyse" not in p.name), None)

    if not source_path:
        return jsonify({"success": False, "error": "Original artwork file not found."}), 404
        
    destination_path = source_path
    
    success, message = signing_service.add_smart_signature(source_path, destination_path)
    
    if success:
        try:
            logger.info(f"Regenerating derivatives for signed artwork: {source_path.name}")
            dest_folder = source_path.parent
            thumb_path = dest_folder / f"{base_name}-thumb.jpg"
            analyse_path = dest_folder / f"{base_name}-analyse.jpg"

            with Image.open(source_path) as img:
                thumb = img.copy()
                thumb.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
                thumb.save(thumb_path, "JPEG", quality=80)
                
                utils.resize_for_analysis(img, analyse_path)
            
            logger.info(f"Successfully regenerated thumb and analyse images for {base_name}.")
            log_action("sign", source_path.name, session.get("username"), "Artwork signed and derivatives regenerated.")
            return jsonify({"success": True, "message": message})

        except Exception as e:
            error_msg = f"Artwork was signed, but failed to regenerate derivatives: {e}"
            logger.error(error_msg, exc_info=True)
            log_action("sign", source_path.name, session.get("username"), "Artwork signed but derivative regeneration failed.", status="fail", error=str(e))
            return jsonify({"success": True, "message": "Artwork signed, but an error occurred updating preview images."})
    else:
        log_action("sign", source_path.name, session.get("username"), "Artwork signing failed", status="fail", error=message)
        return jsonify({"success": False, "error": message}), 500
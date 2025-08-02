# routes/artwork_routes.py

# -*- coding: utf-8 -*-
"""Artwork-related Flask routes.

This module powers the full listing workflow from initial review to
finalisation. It handles validation, moving files, regenerating image link
lists and serving gallery pages for processed and finalised artworks.

INDEX
-----
1.  Imports and Initialisation
2.  Health Checks and Status API
3.  AI Analysis & Subprocess Helpers
4.  Validation and Data Helpers
5.  Core Navigation & Upload Routes
6.  Mockup Selection Workflow Routes
7.  Artwork Analysis Trigger Routes
8.  Artwork Editing and Listing Management
9.  Static File and Image Serving Routes
10. Composite Image Preview Routes
11. Artwork Finalisation and Gallery Routes
12. Listing State Management (Lock, Unlock, Delete)
13. Asynchronous API Endpoints
14. File Processing and Utility Helpers
15. Artwork Signing Route
"""

# ===========================================================================
# 1. Imports and Initialisation
# ===========================================================================
from __future__ import annotations
import json, subprocess, uuid, random, logging, shutil, os, traceback, datetime, time, sys
from pathlib import Path

# --- Local Application Imports ---
from utils.logger_utils import log_action
from utils.sku_assigner import peek_next_sku
from utils import ai_services
from routes import sellbrite_service
import config
from helpers.listing_utils import (
    resolve_listing_paths,
    create_unanalysed_subfolder,
    cleanup_unanalysed_folders,
)
from config import (
    PROCESSED_ROOT, FINALISED_ROOT, UNANALYSED_ROOT, ARTWORK_VAULT_ROOT,
    ANALYSIS_STATUS_FILE,
)
import scripts.analyze_artwork as aa
from scripts import signing_service

# --- Third-Party Imports ---
from PIL import Image
import google.generativeai as genai
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, send_from_directory, abort, Response, jsonify,
)
import re

# --- Local Route-Specific Imports ---
from . import utils
from .utils import (
    ALLOWED_COLOURS_LOWER, read_generic_text, clean_terms, infer_sku_from_filename,
    sync_filename_with_sku, is_finalised_image, get_allowed_colours,
    load_json_file_safe,
)

bp = Blueprint("artwork", __name__)

# ===========================================================================
# 2. Health Checks and Status API
# ===========================================================================
@bp.get("/health/openai")
def health_openai():
    """Return status of OpenAI connection."""
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

@bp.get("/health/google")
def health_google():
    """Return status of Google Vision connection."""
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

load_json_file_safe(ANALYSIS_STATUS_FILE)

def _write_analysis_status(step: str, percent: int, file: str | None = None, status: str | None = None, error: str | None = None) -> None:
    """Write progress info for frontend polling."""
    logger = logging.getLogger(__name__)
    payload = {"step": step, "percent": percent, "file": file, "status": status, "error": error}
    try:
        ANALYSIS_STATUS_FILE.write_text(json.dumps({k: v for k, v in payload.items() if v is not None}))
    except Exception as exc:
        logger.error("Failed writing analysis status: %s", exc)

@bp.route("/status/analyze")
def analysis_status():
    """Return JSON progress info for the current analysis job."""
    return Response(ANALYSIS_STATUS_FILE.read_text(), mimetype="application/json")

# ===========================================================================
# 3. AI Analysis & Subprocess Helpers
# ===========================================================================
def _run_ai_analysis(img_path: Path, provider: str) -> dict:
    """Run the AI analysis script and return its JSON output."""
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

def _generate_composites(log_id: str) -> None:
    """Triggers the queue-based composite generation script."""
    cmd = [sys.executable, str(config.GENERATE_SCRIPT_PATH)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=config.BASE_DIR, timeout=600)
    composite_log = config.LOGS_DIR / "composite-generation-logs" / f"composite_gen_{log_id}.log"
    composite_log.parent.mkdir(exist_ok=True)
    composite_log.write_text(f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}")
    if result.returncode != 0:
        raise RuntimeError(f"Composite generation failed ({result.returncode})")

# ===========================================================================
# 4. Validation and Data Helpers
# ===========================================================================
def validate_listing_fields(data: dict, generic_text: str) -> list[str]:
    """Return a list of validation error messages for the listing."""
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
    if not re.search(r"artwork-by-robin-custance-RJC-[A-Za-z0-9-]+\.jpg$", seo_filename, re.IGNORECASE):
        errors.append("SEO filename must end with 'artwork-by-robin-custance-RJC-XXXX.jpg'")
    sku = data.get("sku", "")
    if not sku: errors.append("SKU is required")
    if sku and not sku.startswith("RJC-"): errors.append("SKU must start with 'RJC-'")
    if sku and infer_sku_from_filename(seo_filename or "") != sku:
        errors.append("SKU must match value in SEO filename")
    try:
        if abs(float(data.get("price")) - 18.27) > 1e-2: errors.append("Price must be 18.27")
    except Exception: errors.append("Price must be a number (18.27)")
    for key in ("primary_colour", "secondary_colour"):
        col = data.get(key, "").strip()
        if not col: errors.append(f"{key.replace('_', ' ').title()} is required")
        elif col.lower() not in ALLOWED_COLOURS_LOWER: errors.append(f"{key.replace('_', ' ').title()} invalid")
    images = [i.strip() for i in data.get("images", []) if str(i).strip()]
    if not images: errors.append("At least one image required")
    for img in images:
        if not is_finalised_image(img): errors.append(f"Image not in finalised-artwork folder: '{img}'")
    desc = data.get("description", "").strip()
    if len(desc.split()) < 400: errors.append("Description must be at least 400 words")
    if generic_text and "About the Artist – Robin Custance".lower() not in " ".join(desc.split()).lower():
        errors.append("Description must include the correct generic context block.")
    return errors

def get_categories_for_aspect(aspect: str) -> list[str]:
    """Return list of mockup categories available for the given aspect."""
    base = config.MOCKUPS_CATEGORISED_DIR / aspect
    return sorted([f.name for f in base.iterdir() if f.is_dir()]) if base.exists() else []

# ===========================================================================
# 5. Core Navigation & Upload Routes
# ===========================================================================
@bp.app_context_processor
def inject_latest_artwork():
    """Injects the latest analyzed artwork data into all templates."""
    return dict(latest_artwork=utils.latest_analyzed_artwork())

@bp.route("/")
def home():
    """Renders the main home page."""
    return render_template("index.html", menu=utils.get_menu())

@bp.route("/upload", methods=["GET", "POST"])
def upload_artwork():
    """Handle new artwork file uploads and run pre-QC checks."""
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

@bp.route("/artworks")
def artworks():
    """Display lists of artworks ready for analysis, processed, and finalised."""
    processed, processed_names = utils.list_processed_artworks()
    ready = utils.list_ready_to_analyze(processed_names)
    finalised = utils.list_finalised_artworks()
    return render_template("artworks.html", ready_artworks=ready, processed_artworks=processed, finalised_artworks=finalised, menu=utils.get_menu())
    
# ===========================================================================
# 6. Mockup Selection Workflow Routes
# ===========================================================================
@bp.route("/select", methods=["GET", "POST"])
def select():
    """Display the mockup selection interface."""
    if "slots" not in session or request.args.get("reset") == "1":
        utils.init_slots()
    slots = session["slots"]
    options = utils.compute_options(slots)
    zipped = list(zip(slots, options))
    return render_template("mockup_selector.html", zipped=zipped, menu=utils.get_menu())

@bp.route("/regenerate", methods=["POST"])
def regenerate():
    """Regenerate a random mockup image for a specific slot."""
    slot_idx = int(request.form["slot"])
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        cat = slots[slot_idx]["category"]
        slots[slot_idx]["image"] = utils.random_image(cat, "4x5")
        session["slots"] = slots
    return redirect(url_for("artwork.select"))

@bp.route("/swap", methods=["POST"])
def swap():
    """Swap a mockup slot to a new category."""
    slot_idx = int(request.form["slot"])
    new_cat = request.form["new_category"]
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        slots[slot_idx]["category"] = new_cat
        slots[slot_idx]["image"] = utils.random_image(new_cat, "4x5")
        session["slots"] = slots
    return redirect(url_for("artwork.select"))

@bp.route("/proceed", methods=["POST"])
def proceed():
    """Finalise mockup selections and trigger composite generation."""
    flash("Composite generation process initiated!", "success")
    latest = utils.latest_composite_folder()
    if latest:
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    return redirect(url_for("artwork.composites_preview"))

# ===========================================================================
# 7. Artwork Analysis Trigger Routes
# ===========================================================================
@bp.route("/analyze/<aspect>/<filename>", methods=["POST"], endpoint="analyze_artwork")
def analyze_artwork_route(aspect, filename):
    """Run analysis on `filename` using the selected provider."""
    logger, provider = logging.getLogger(__name__), request.form.get("provider", "openai").lower()
    base_name = Path(filename).name
    _write_analysis_status("starting", 0, base_name, status="analyzing")
    is_ajax = "XMLHttpRequest" in request.headers.get("X-Requested-With", "")

    src_path = next((p for p in config.UNANALYSED_ROOT.rglob(base_name) if p.is_file()), None)
    if not src_path:
        try:
            seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
            src_path = PROCESSED_ROOT / seo_folder / f"{seo_folder}.jpg"
        except FileNotFoundError: pass

    if not src_path or not src_path.exists():
        flash(f"Artwork file not found: {filename}", "danger")
        if is_ajax: return jsonify({"success": False, "error": "Artwork file not found"}), 404
        return redirect(url_for("artwork.artworks"))

    try:
        analysis_result = _run_ai_analysis(src_path, provider)
        seo_folder = Path(analysis_result.get("processed_folder", "")).name
        
        if not seo_folder: raise RuntimeError("Analysis script did not return a valid folder name.")

        _generate_composites(uuid.uuid4().hex)
        
        if config.UNANALYSED_ROOT in src_path.parents:
            shutil.rmtree(src_path.parent, ignore_errors=True)
            log_action("cleanup", src_path.parent.name, session.get("username"), "Deleted unanalysed artwork folder.")
            logger.info(f"Cleaned up unanalysed source folder: {src_path.parent}")

    except Exception as exc:
        logger.error(f"Error running analysis for {filename}: {exc}", exc_info=True)
        flash(f"❌ Error running analysis: {exc}", "danger")
        if is_ajax: return jsonify({"success": False, "error": str(exc)}), 500
        return redirect(url_for("artwork.artworks"))

    redirect_filename = f"{seo_folder}.jpg"
    redirect_url = url_for("artwork.edit_listing", aspect=aspect, filename=redirect_filename)

    if is_ajax:
        return jsonify({
            "success": True,
            "message": "Analysis complete.",
            "redirect_url": redirect_url
        })
    
    return redirect(redirect_url)

@bp.post("/analyze-upload/<base>")
def analyze_upload(base):
    """Analyze an uploaded image from the unanalysed folder."""
    uid, rec = utils.get_record_by_base(base)
    if not rec:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
        
    folder = Path(rec["current_folder"])
    qc_path = folder / f"{base}.qc.json"
    qc = utils.load_json_file_safe(qc_path)
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

# ===========================================================================
# 8. Artwork Editing and Listing Management
# ===========================================================================
@bp.route("/edit-listing/<aspect>/<filename>", methods=["GET", "POST"])
def edit_listing(aspect, filename):
    """Display and update a processed or finalised artwork listing."""
    try:
        seo_folder, folder, listing_path, finalised = resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))
    
    data = utils.load_json_file_safe(listing_path)
    is_locked_in_vault = ARTWORK_VAULT_ROOT in folder.parents

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
        openai_analysis=data.get("openai_analysis"),
        cache_ts=int(time.time()),
    )

# ===========================================================================
# 9. Static File and Image Serving Routes
# ===========================================================================
@bp.route(f"/{config.PROCESSED_URL_PATH}/<path:filename>")
def processed_image(filename):
    return send_from_directory(config.PROCESSED_ROOT, filename)

@bp.route(f"/{config.FINALISED_URL_PATH}/<path:filename>")
def finalised_image(filename):
    return send_from_directory(config.FINALISED_ROOT, filename)

@bp.route(f"/{config.LOCKED_URL_PATH}/<path:filename>")
def locked_image(filename):
    return send_from_directory(config.ARTWORK_VAULT_ROOT, filename)

@bp.route(f"/{config.MOCKUP_THUMB_URL_PREFIX}/<path:filepath>")
def serve_mockup_thumb(filepath: str):
    for base_dir in [config.PROCESSED_ROOT, config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT]:
        full_path = base_dir / filepath
        if full_path.is_file():
            return send_from_directory(full_path.parent, full_path.name)
    abort(404)

@bp.route(f"/{config.UNANALYSED_IMG_URL_PREFIX}/<filename>")
def unanalysed_image(filename: str):
    path = next((p for p in config.UNANALYSED_ROOT.rglob(filename) if p.is_file()), None)
    if path:
        return send_from_directory(path.parent, path.name)
    abort(404)

@bp.route(f"/{config.COMPOSITE_IMG_URL_PREFIX}/<folder>/<filename>")
def composite_img(folder, filename):
    return send_from_directory(config.PROCESSED_ROOT / folder, filename)

@bp.route("/mockup-img/<category>/<filename>")
def mockup_img(category, filename):
    return send_from_directory(config.MOCKUPS_INPUT_DIR / category, filename)

# ===========================================================================
# 10. Composite Image Preview Routes
# ===========================================================================
@bp.route("/composites")
def composites_preview():
    latest = utils.latest_composite_folder()
    if latest:
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    flash("No composites found", "warning")
    return redirect(url_for("artwork.artworks"))

@bp.route("/composites/<seo_folder>")
def composites_specific(seo_folder):
    folder = utils.PROCESSED_ROOT / seo_folder
    json_path = folder / f"{seo_folder}-listing.json"
    images = []
    if json_path.exists():
        listing = utils.load_json_file_safe(json_path)
        images = utils.get_mockup_details_for_template(
            listing.get("mockups", []), folder, seo_folder, listing.get("aspect_ratio", "")
        )
    return render_template(
        "composites_preview.html",
        images=images,
        folder=seo_folder,
        menu=utils.get_menu(),
    )

@bp.route("/approve_composites/<seo_folder>", methods=["POST"])
def approve_composites(seo_folder):
    listing_path = next((PROCESSED_ROOT / seo_folder).glob("*-listing.json"), None)
    if listing_path:
        data = utils.load_json_file_safe(listing_path)
        aspect = data.get("aspect_ratio", "4x5")
        filename = data.get("seo_filename", f"{seo_folder}.jpg")
        flash("Composites approved. Please review and finalise.", "success")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))
    flash("Could not find listing data.", "danger")
    return redirect(url_for("artwork.artworks"))

# ===========================================================================
# 11. Artwork Finalisation and Gallery Routes
# ===========================================================================
@bp.route("/finalise/<aspect>/<filename>", methods=["GET", "POST"])
def finalise_artwork(aspect, filename):
    try:
        seo_folder, _, _, _ = resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))

    processed_dir = utils.PROCESSED_ROOT / seo_folder
    final_dir = utils.FINALISED_ROOT / seo_folder
    user = session.get("username")

    try:
        if final_dir.exists(): shutil.rmtree(final_dir)
        shutil.move(str(processed_dir), str(final_dir))

        listing_file = final_dir / f"{seo_folder}-listing.json"
        if listing_file.exists():
            utils.assign_or_get_sku(listing_file, config.SKU_TRACKER)
            utils.update_listing_paths(listing_file, PROCESSED_ROOT, FINALISED_ROOT)

        log_action("finalise", filename, user, f"finalised to {final_dir}")
        flash("Artwork finalised", "success")
    except Exception as e:
        log_action("finalise", filename, user, "finalise failed", status="fail", error=str(e))
        flash(f"Failed to finalise artwork: {e}", "danger")
        if final_dir.exists() and not processed_dir.exists():
            shutil.move(str(final_dir), str(processed_dir))
            flash("Attempted to roll back the move.", "info")

    return redirect(url_for("artwork.finalised_gallery"))

@bp.route("/finalised")
def finalised_gallery():
    artworks = [a for a in utils.get_all_artworks() if a['status'] == 'finalised']
    return render_template("finalised.html", artworks=artworks, menu=utils.get_menu())

@bp.route("/locked")
def locked_gallery():
    locked_items = [a for a in utils.get_all_artworks() if a.get('locked')]
    return render_template("locked.html", artworks=locked_items, menu=utils.get_menu())

# ===========================================================================
# 12. Listing State Management (Lock, Unlock, Delete)
# ===========================================================================
@bp.post("/finalise/delete/<aspect>/<filename>")
def delete_finalised(aspect, filename):
    try:
        _, folder, listing_file, _ = resolve_listing_paths(aspect, filename)
        info = utils.load_json_file_safe(listing_file)
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

@bp.post("/lock/<aspect>/<filename>")
def lock_listing(aspect, filename):
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
        with open(new_listing_path, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data["locked"] = True
            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()
        utils.update_listing_paths(new_listing_path, folder, target)
        flash("Artwork locked.", "success")
        log_action("lock", filename, session.get("username"), "locked artwork")
    except Exception as exc:
        flash(f"Failed to lock: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))

@bp.post("/unlock/<aspect>/<filename>")
def unlock_listing(aspect, filename):
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

# ===========================================================================
# 13. Asynchronous API Endpoints
# ===========================================================================
@bp.post("/update-links/<aspect>/<filename>")
def update_links(aspect, filename):
    """Regenerate the image URL list from disk and return as JSON."""
    wants_json = "application/json" in request.headers.get("Accept", "")
    try:
        _, folder, listing_file, _ = resolve_listing_paths(aspect, filename)
        data = utils.load_json_file_safe(listing_file)
        imgs = [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        data["images"] = [utils.relative_to_base(p) for p in sorted(imgs)]
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

@bp.post("/reset-sku/<aspect>/<filename>")
def reset_sku(aspect, filename):
    """Force reassign a new SKU for the given artwork."""
    try:
        _, _, listing, _ = resolve_listing_paths(aspect, filename)
        utils.assign_or_get_sku(listing, config.SKU_TRACKER, force=True)
        flash("SKU has been reset.", "success")
    except Exception as exc:
        flash(f"Failed to reset SKU: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))

@bp.post("/delete/<filename>")
def delete_artwork(filename: str):
    """Delete all files and registry entries for an artwork."""
    logger, user = logging.getLogger(__name__), session.get("username", "unknown")
    log_action("delete", filename, user, f"Initiating delete for '{filename}'")
    
    base_stem = Path(filename).stem

    try:
        seo_folder = utils.find_seo_folder_from_filename("", filename)
        if seo_folder:
            shutil.rmtree(config.PROCESSED_ROOT / seo_folder, ignore_errors=True)
            shutil.rmtree(config.FINALISED_ROOT / seo_folder, ignore_errors=True)
            shutil.rmtree(config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}", ignore_errors=True)
            logger.info(f"Deleted processed/finalised/locked folders for {seo_folder}")
    except FileNotFoundError:
        logger.info(f"No processed folder found for '{filename}', proceeding to clean unanalysed files.")
        pass

    found_files = list(config.UNANALYSED_ROOT.rglob(f"{base_stem}*"))
    if found_files:
        parent_dir = found_files[0].parent
        if parent_dir != config.UNANALYSED_ROOT:
             shutil.rmtree(parent_dir, ignore_errors=True)
             logger.info(f"Deleted unanalysed folder: {parent_dir}")
    
    uid, _ = utils.get_record_by_base(base_stem)
    if uid:
        utils.remove_record_from_registry(uid)
        logger.info(f"Removed registry record {uid}")
    
    log_action("delete", filename, user, "Delete process completed.")
    return jsonify({"success": True})

@bp.post("/api/reword-generic-text")
def reword_generic_text_api():
    """Handles an asynchronous request to reword the generic part of a description."""
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

# ===========================================================================
# 14. File Processing and Utility Helpers
# ===========================================================================
@bp.route("/next-sku")
def preview_next_sku():
    """Return the next available SKU without reserving it."""
    return Response(peek_next_sku(config.SKU_TRACKER), mimetype="text/plain")

def _process_upload_file(file_storage, dest_folder):
    """Validate, save, and preprocess a single uploaded file."""
    filename = file_storage.filename
    if not filename: return {"original": filename, "success": False, "error": "No filename"}

    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_EXTENSIONS:
        return {"original": filename, "success": False, "error": "Invalid file type"}
    
    data = file_storage.read()
    if len(data) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        return {"original": filename, "success": False, "error": "File too large"}

    safe, unique, uid = aa.slugify(Path(filename).stem), uuid.uuid4().hex[:8], uuid.uuid4().hex
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

# ===========================================================================
# 15. Artwork Signing Route
# ===========================================================================
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
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
"""

# ===========================================================================
# 1. Imports and Initialisation
# ===========================================================================
# This section handles all necessary imports, configuration loading, and
# the initial setup of the Flask Blueprint and logging.
# ===========================================================================

from __future__ import annotations
import json, subprocess, uuid, random, logging, shutil, os, traceback, datetime, time, sys
from pathlib import Path

# --- Local Application Imports ---
from utils.logger_utils import log_action, strip_binary
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
    BASE_DIR, ANALYSIS_STATUS_FILE, PROCESSED_URL_PATH, FINALISED_URL_PATH,
    LOCKED_URL_PATH, UNANALYSED_IMG_URL_PREFIX, MOCKUP_THUMB_URL_PREFIX,
    COMPOSITE_IMG_URL_PREFIX,
)
import scripts.analyze_artwork as aa

# --- Third-Party Imports ---
from PIL import Image
import io
import google.generativeai as genai
from flask import (
    Blueprint, current_app, render_template, request, redirect, url_for,
    session, flash, send_from_directory, abort, Response, jsonify,
)
import re

# --- Local Route-Specific Imports ---
from . import utils
from .utils import (
    ALLOWED_COLOURS_LOWER, relative_to_base, read_generic_text, clean_terms, infer_sku_from_filename,
    sync_filename_with_sku, is_finalised_image, get_allowed_colours,
    load_json_file_safe, generate_mockups_for_listing,
)

bp = Blueprint("artwork", __name__)

# ===========================================================================
# 2. Health Checks and Status API
# ===========================================================================
# These endpoints provide status information for external services like
# OpenAI and Google, and for the background artwork analysis process.
# They are used by the frontend to monitor system health.
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

def _generate_composites(seo_folder: str, log_id: str) -> None:
    """Triggers the composite generation script for a specific folder."""
    cmd = [sys.executable, str(config.GENERATE_SCRIPT_PATH), "--folder", seo_folder]
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
    if not data.get("title", "").strip(): errors.append("Title cannot be blank")
    if len(data.get("title", "")) > 140: errors.append("Title exceeds 140 characters")
    if len(data.get("tags", [])) > 13: errors.append("Too many tags (max 13)")
    for t in data.get("tags", []):
        if not t or len(t) > 20: errors.append(f"Invalid tag: '{t}'")
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
        slots[slot_idx]["image"] = utils.random_image(cat, "4x5") # Assuming 4x5 for now
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

# ===========================================================================
# 7. Artwork Analysis Trigger Routes
# ===========================================================================

@bp.route("/analyze/<aspect>/<filename>", methods=["POST"], endpoint="analyze_artwork")
def analyze_artwork_route(aspect, filename):
    """Run analysis on `filename` using the selected provider."""
    logger, provider = logging.getLogger(__name__), request.form.get("provider", "openai").lower()
    base_name = Path(filename).name
    _write_analysis_status("starting", 0, base_name, status="analyzing")

    src_path = next((p for p in config.UNANALYSED_ROOT.rglob(base_name) if p.is_file()), None)
    if not src_path:
        try:
            seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
            src_path = PROCESSED_ROOT / seo_folder / f"{seo_folder}.jpg"
        except FileNotFoundError: pass

    if not src_path or not src_path.exists():
        flash(f"Artwork file not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))

    try:
        analysis_result = _run_ai_analysis(src_path, provider)
        seo_folder = Path(analysis_result.get("processed_folder", "")).name
        
        if not seo_folder: raise RuntimeError("Analysis script did not return a valid folder name.")

        _generate_composites(seo_folder, uuid.uuid4().hex)
        
    except Exception as exc:
        flash(f"❌ Error running analysis: {exc}", "danger")
        return redirect(url_for("artwork.artworks"))

    redirect_filename = f"{seo_folder}.jpg"
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=redirect_filename))

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


# ==============================================================================
# SECTION 9: ADMIN + ANALYSIS API ROUTES
# ==============================================================================

# ------------------------------------------------------------------------------
# 9.1: Admin View of Individual Artwork
# ------------------------------------------------------------------------------

@router.get("/admin/artwork/{artwork_id}", response_class=HTMLResponse, name="admin_artwork_detail_page")
async def admin_artwork_detail_route(
    artwork_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """(Admin) Displays a detailed view of an individual artwork."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")

    artwork = _get_artwork_or_404(artwork_id, db, current_user)
    context = {"page_title": f"Admin View: {artwork.original_filename}", "artwork": artwork}
    return templates.TemplateResponse(request, "artwork_admin_details.html", context)


# ------------------------------------------------------------------------------
# 9.2: API – Get Artworks for Gallery Display
# ------------------------------------------------------------------------------

@router.get("/artworks-for-analysis", response_model=Optional[List[Dict[str, Any]]], name="json_artworks_for_analysis_gallery")
async def get_artworks_for_analysis_gallery_api(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Optional[List[Dict[str, Any]]]:
    """
    Returns artwork metadata for the Analyze Gallery grid.
    Filters by multiple artwork statuses.
    """
    gallery_statuses = [
        "qc_passed",
        "analyzed_pending_acceptance",
        "analysis_rejected",
        "finalized",
        "ready_for_export",
    ]
    artworks_db = crud.get_artworks_by_statuses(
        db,
        statuses=gallery_statuses,
        owner_id=None if current_user.is_superuser else current_user.id,
    )

    return [
        {
            "id": art.id,
            "original_filename": art.original_filename,
            "thumb_url": get_artwork_display_url(request, art.thumb_path, art.status),
            "status_raw": art.status or "unknown",
            "status_display": (art.status or "Unknown").replace("_", " ").title(),
            "generated_title_display": art.generated_title or get_short_prompt_hint(art.original_filename),
            "sku_display": art.sku,
            "resolution": art.resolution,
            "dpi": str(art.dpi) if art.dpi is not None else None,
        }
        for art in artworks_db
    ]


# ------------------------------------------------------------------------------
# 9.3: API – Update Artwork Status
# ------------------------------------------------------------------------------

@router.post("/artwork/{artwork_id}/update-status", name="update_artwork_status_api_analyze")
async def update_artwork_status_api_route_analyze(
    artwork_id: int,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> JSONResponse:
    """
    Updates the status of an artwork via the Analyze section.
    Only allows transitions to pre-defined valid statuses.
    """
    artwork = _get_artwork_or_404(artwork_id, db, current_user)
    valid_statuses = [
        "uploaded_pending_qc",
        "qc_passed",
        "qc_failed_metrics",
        "analyzed_pending_acceptance",
        "analysis_rejected",
        "finalized",
        "ready_for_export",
    ]

    if new_status not in valid_statuses:
        return JSONResponse(status_code=400, content={"error": f"Invalid status: {new_status}"})

    artwork.status = new_status
    artwork.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(artwork)
        return JSONResponse(content={"message": "Status updated", "new_status": new_status})
    except Exception as e_db:
        db.rollback()
        logger.error(f"DB error updating status for ArtID {artwork_id}: {e_db}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Database error on status update."})

# ==============================================================================
# END OF FILE — analyze_routes.py
# ==============================================================================

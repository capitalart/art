# routes/artwork_routes.py
# -*- coding: utf-8 -*-
"""
Artwork-related Flask routes for the ArtNarrator application.

This module powers the core artwork workflow, from upload and analysis to
finalisation and gallery displays. It does not handle the editing of a listing.
"""
# ===========================================================================
# 1. Imports & Initialisation
# ===========================================================================
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
    update_artwork_registry, resolve_listing_paths
)
import scripts.analyze_artwork as aa
from scripts import signing_service
from . import utils
from utils.logger_utils import log_action
from utils.sku_assigner import peek_next_sku

bp = Blueprint("artwork", __name__)


# ===========================================================================
# 2. Health Checks, Status API & Subprocess Helpers
# ===========================================================================
@bp.get("/health/openai")
def health_openai():
    logger = logging.getLogger(__name__)
    try:
        aa.client.models.list()
        return jsonify({"ok": True})
    except Exception as exc:
        logger.error(f"OpenAI health check failed: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 500

@bp.get("/health/google")
def health_google():
    logger = logging.getLogger(__name__)
    try:
        genai.list_models()
        return jsonify({"ok": True})
    except Exception as exc:
        logger.error(f"Google health check failed: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 500

def _write_analysis_status(step: str, percent: int, file: str | None = None, status: str | None = None, error: str | None = None) -> None:
    payload = {"step": step, "percent": percent, "file": file, "status": status, "error": error}
    try:
        config.ANALYSIS_STATUS_FILE.write_text(json.dumps({k: v for k, v in payload.items() if v is not None}))
    except Exception as exc:
        logging.getLogger(__name__).error(f"Failed writing analysis status: {exc}")

@bp.route("/status/analyze")
def analysis_status():
    return Response(config.ANALYSIS_STATUS_FILE.read_text(), mimetype="application/json")

def _run_ai_analysis(img_path: Path, provider: str) -> dict:
    logger = logging.getLogger("art_analysis")
    cmd = [sys.executable, str(config.ANALYZE_SCRIPT_PATH), str(img_path), "--json-output"] if provider == "openai" else []
    if not cmd: raise ValueError(f"Unknown provider: {provider}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0: raise RuntimeError(f"AI analysis failed: {(result.stderr or 'Unknown error').strip()}")
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        raise RuntimeError("AI analysis output could not be parsed.") from e

def _generate_composites(log_id: str) -> None:
    cmd = [sys.executable, str(config.GENERATE_SCRIPT_PATH)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=config.BASE_DIR, timeout=600)
    log_file = config.LOGS_DIR / "composite-generation-logs" / f"composite_gen_{log_id}.log"
    log_file.parent.mkdir(exist_ok=True, parents=True)
    log_file.write_text(f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
    if result.returncode != 0: raise RuntimeError(f"Composite generation failed ({result.returncode})")


# ===========================================================================
# 3. Core Navigation, Galleries & Upload
# ===========================================================================
@bp.app_context_processor
def inject_latest_artwork():
    return dict(latest_artwork=utils.latest_analyzed_artwork())

@bp.route("/")
def home():
    return render_template("index.html", menu=utils.get_menu())

@bp.route("/upload", methods=["GET", "POST"])
def upload_artwork():
    if request.method == "POST":
        files = request.files.getlist("images")
        results = []
        user = session.get("username")
        for f in files:
            folder = create_unanalysed_subfolder(f.filename)
            try:
                res = _process_upload_file(f, folder)
            except Exception as exc:
                logging.getLogger(__name__).error(f"Upload failed for {f.filename}: {exc}")
                res = {"original": f.filename, "success": False, "error": str(exc)}
            log_action("upload", res.get("original", f.filename), user, res.get("error", "uploaded"), status="success" if res.get("success") else "fail")
            results.append(res)
        if any(r["success"] for r in results): flash(f"Uploaded {sum(1 for r in results if r['success'])} file(s) successfully", "success")
        for r in [r for r in results if not r["success"]]: flash(f"{r['original']}: {r['error']}", "danger")
        return redirect(url_for("artwork.artworks"))
    return render_template("upload.html", menu=utils.get_menu())

@bp.route("/artworks")
def artworks():
    processed, processed_names = utils.list_processed_artworks()
    ready = utils.list_ready_to_analyze(processed_names)
    finalised = utils.list_finalised_artworks()
    return render_template("artworks.html", ready_artworks=ready, processed_artworks=processed, finalised_artworks=finalised, menu=utils.get_menu())
<<<<<<< ours
=======
    

# === [ Section 6: Mockup Selection Workflow Routes | artwork-routes-py-6 ] ===
# DEPRECATED: These routes were part of an older, manual mockup selection flow.
# They are kept for reference but are no longer active in the main UI.
# ---------------------------------------------------------------------------------

# --- [ 6a: select | artwork-routes-py-6a ] ---
@bp.route("/select", methods=["GET", "POST"], endpoint="select")
def select():
    """(DEPRECATED) Displays the old mockup selection interface."""
    if "slots" not in session or request.args.get("reset") == "1":
        utils.init_slots()
    slots = session["slots"]
    options = utils.compute_options(slots)
    zipped = list(zip(slots, options))
    return render_template("mockup_selector.html", zipped=zipped, menu=utils.get_menu())
>>>>>>> theirs

@bp.route("/finalised")
def finalised_gallery():
    from routes import sellbrite_service
    artworks_list = [a for a in utils.get_all_artworks() if a['status'] == 'finalised']
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
    return render_template("finalised.html", artworks=artworks_list, menu=utils.get_menu())

<<<<<<< ours
@bp.route("/locked")
def locked_gallery():
    locked_items = [a for a in utils.get_all_artworks() if a.get('locked')]
    return render_template("locked.html", artworks=locked_items, menu=utils.get_menu())
=======
# --- [ 6b: regenerate | artwork-routes-py-6b ] ---
@bp.route("/regenerate", methods=["POST"], endpoint="regenerate")
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
@bp.route("/swap", methods=["POST"], endpoint="swap")
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
@bp.route("/proceed", methods=["POST"], endpoint="proceed")
def proceed():
    """(DEPRECATED) Finalises mockup selections and triggers composite generation."""
    flash("Composite generation process initiated!", "success")
    latest = utils.latest_composite_folder()
    if latest:
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    return redirect(url_for("artwork.composites_preview"))

>>>>>>> theirs


# ===========================================================================
# 4. Analysis & Workflow Triggers
# ===========================================================================
@bp.route("/analyze/<aspect>/<filename>", methods=["POST"])
def analyze_artwork(aspect, filename):
    provider = request.form.get("provider", "openai").lower()
    base_name = Path(filename).stem
    _write_analysis_status("starting", 0, base_name, status="analyzing")
    src_path = next((p for p in config.UNANALYSED_ROOT.rglob(f"{base_name}.*") if p.is_file()), None)
    if not src_path:
        try:
            seo_folder, _, _, _ = resolve_listing_paths(aspect, filename)
            src_path = config.PROCESSED_ROOT / seo_folder / f"{seo_folder}.jpg"
        except FileNotFoundError: pass
    if not src_path or not src_path.exists():
        flash(f"Artwork file not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))
    try:
        analysis_result = _run_ai_analysis(src_path, provider)
        seo_folder = Path(analysis_result.get("processed_folder", "")).name
        if not seo_folder: raise RuntimeError("Analysis script did not return valid folder name.")
        _generate_composites(uuid.uuid4().hex)
        if config.UNANALYSED_ROOT in src_path.parents:
            shutil.rmtree(src_path.parent, ignore_errors=True)
    except Exception as exc:
        flash(f"❌ Error running analysis: {exc}", "danger")
        return redirect(url_for("artwork.artworks"))
    redirect_filename = f"{seo_folder}.jpg"
<<<<<<< ours
    return redirect(url_for("edit_listing.edit_listing", aspect=aspect, filename=redirect_filename))

=======
    return redirect(url_for("artwork.edit_listing", aspect=qc.get("aspect_ratio", ""), filename=redirect_filename))


# === [ Section 8: Artwork Editing and Listing Management | artwork-routes-py-8 ] ===
# The main route for editing an artwork's listing details, handling both
# displaying the form (GET) and saving changes (POST).
# ---------------------------------------------------------------------------------

# --- [ 8a: edit_listing | artwork-routes-py-8a ] ---
@bp.route("/edit-listing/<aspect>/<filename>", methods=["GET", "POST"], endpoint="edit_listing")
def edit_listing(aspect, filename):
    """Displays and updates a processed or finalised artwork listing."""
    try:
        seo_folder, folder, listing_path, finalised = resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))
    
    data = load_json_file_safe(listing_path)
    is_locked_in_vault = config.ARTWORK_VAULT_ROOT in folder.parents

    if (config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}").exists():
        stage = "vault"
    elif (config.FINALISED_ROOT / seo_folder).exists():
        stage = "finalised"
    else:
        stage = "processed"
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
@bp.route("/mockup-img/<category>/<filename>", endpoint="mockup_img")
def mockup_img(category, filename):
    """Serves a mockup template image from the central inputs directory."""
    return send_from_directory(config.MOCKUPS_INPUT_DIR / category, filename)


# === [ Section 10: Composite Image Preview Routes | artwork-routes-py-10 ] ===
# Routes for the composite/mockup preview page.
# ---------------------------------------------------------------------------------

# --- [ 10a: composites_preview | artwork-routes-py-10a ] ---
@bp.route("/composites", endpoint="composites_preview")
def composites_preview():
    """Redirects to the latest composite folder or the main artworks page."""
    latest = utils.latest_composite_folder()
    if latest:
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    flash("No composites found", "warning")
    return redirect(url_for("artwork.artworks"))


# --- [ 10b: composites_specific | artwork-routes-py-10b ] ---
@bp.route("/composites/<seo_folder>", endpoint="composites_specific")
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
@bp.route("/approve_composites/<seo_folder>", methods=["POST"], endpoint="approve_composites")
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
>>>>>>> theirs
@bp.route("/finalise-artwork/<seo_folder>", methods=["POST"])
def finalise_artwork(seo_folder):
    src = config.PROCESSED_ROOT / seo_folder
    dst = config.FINALISED_ROOT / seo_folder
    try:
        if not src.exists(): raise FileNotFoundError(f"Processed artwork '{seo_folder}' not found.")
        shutil.move(str(src), str(dst))
        listing_file = dst / f"{seo_folder}-listing.json"
        utils.update_listing_paths(listing_file, config.PROCESSED_ROOT, config.FINALISED_ROOT)
        data = load_json_file_safe(listing_file)
        data["locked"] = False
        data["images"] = generate_public_image_urls(seo_folder, "finalised")
        with open(listing_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        update_artwork_registry(seo_folder, dst, "finalised")
        flash("Artwork finalised for review", "success")
    except Exception as exc:
        flash(f"Error during finalisation: {exc}", "danger")
    return redirect(url_for("artwork.finalised_gallery"))

@bp.post("/lock-it-in/<seo_folder>")
def lock_it_in(seo_folder: str):
    src = config.FINALISED_ROOT / seo_folder
    dst = config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}"
    try:
        if not src.exists(): raise FileNotFoundError(f"Finalised artwork '{seo_folder}' not found.")
        shutil.move(str(src), str(dst))
        listing_file = dst / f"{seo_folder}-listing.json"
        utils.update_listing_paths(listing_file, config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT)
        data = load_json_file_safe(listing_file)
        data["locked"] = True
        data["images"] = generate_public_image_urls(seo_folder, "vault")
        with open(listing_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        update_artwork_registry(seo_folder, dst, "locked")
        flash("Artwork locked in for export", "success")
    except Exception as e:
        flash(f"Error locking in artwork: {e}", "danger")
    return redirect(url_for("artwork.locked_gallery"))

<<<<<<< ours
=======

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
@bp.post("/lock/<aspect>/<filename>", endpoint="lock_listing")
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
@bp.post("/unlock/<aspect>/<filename>", endpoint="unlock_listing")
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
>>>>>>> theirs
@bp.route("/unlock-artwork/<seo_folder>", methods=["POST"])
def unlock_artwork(seo_folder: str):
    clean = seo_folder.replace("LOCKED-", "")
    src = config.ARTWORK_VAULT_ROOT / f"LOCKED-{clean}"
    dst = config.FINALISED_ROOT / clean
    try:
        shutil.move(str(src), str(dst))
        listing_file = dst / f"{clean}-listing.json"
        utils.update_listing_paths(listing_file, config.ARTWORK_VAULT_ROOT, config.FINALISED_ROOT)
        data = load_json_file_safe(listing_file)
        data["locked"] = False
        data["images"] = generate_public_image_urls(clean, "finalised")
        with open(listing_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        update_artwork_registry(clean, dst, "finalised")
        flash("Artwork unlocked", "success")
    except Exception as exc:
        flash(f"Error during unlocking: {exc}", "danger")
    return redirect(url_for("artwork.finalised_gallery"))

<<<<<<< ours
=======

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
@bp.post("/reset-sku/<aspect>/<filename>", endpoint="reset_sku")
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
>>>>>>> theirs
@bp.route("/delete-artwork/<seo_folder>", methods=["POST"])
def delete_artwork(seo_folder: str):
    user = session.get("username", "unknown")
    clean = seo_folder.replace("LOCKED-", "")
    try:
        if delete_artwork_files(clean):
            flash(f"Artwork '{clean}' deleted successfully.", "success")
        else:
            flash(f"Failed to delete artwork '{clean}'. Some files may not have been found.", "danger")
    except Exception as exc:
        flash(f"An error occurred during deletion: {exc}", "danger")
    return redirect(url_for("artwork.artworks"))


# ===========================================================================
# 5. Image & File Serving
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


# ===========================================================================
# 6. Internal Helpers & Signing Route
# ===========================================================================
@bp.route("/next-sku")
def preview_next_sku():
    return Response(peek_next_sku(config.SKU_TRACKER), mimetype="text/plain")

def _process_upload_file(file_storage, dest_folder):
    filename = file_storage.filename
    if not filename: return {"original": filename, "success": False, "error": "No filename"}
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_EXTENSIONS: return {"original": filename, "success": False, "error": "Invalid file type"}
    data = file_storage.read()
    if len(data) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024: return {"original": filename, "success": False, "error": "File too large"}
    
    safe, unique, uid = utils.slugify(Path(filename).stem), uuid.uuid4().hex[:8], uuid.uuid4().hex
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
        logging.getLogger(__name__).error(f"Image processing failed: {exc}")
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

@bp.post("/sign-artwork/<base_name>")
def sign_artwork_route(base_name: str):
    logger = logging.getLogger(__name__)
    source_path = next((p for p in config.UNANALYSED_ROOT.rglob(f"{base_name}.*") if "-thumb" not in p.name and "-analyse" not in p.name), None)
    if not source_path: return jsonify({"success": False, "error": "Original artwork file not found."}), 404
    destination_path = source_path
    success, message = signing_service.add_smart_signature(source_path, destination_path)
    if success:
        try:
            dest_folder = source_path.parent
            thumb_path = dest_folder / f"{base_name}-thumb.jpg"
            analyse_path = dest_folder / f"{base_name}-analyse.jpg"
            with Image.open(source_path) as img:
                thumb = img.copy()
                thumb.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
                thumb.save(thumb_path, "JPEG", quality=80)
                utils.resize_for_analysis(img, analyse_path)
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
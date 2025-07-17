"""Artwork-related Flask routes.

This module powers the full listing workflow from initial review to
finalisation. It handles validation, moving files, regenerating image link
lists and serving gallery pages for processed and finalised artworks.
"""
from __future__ import annotations

import json
import subprocess
import uuid
import random
from pathlib import Path
import shutil
import os
import datetime
import logging
from config import (
    ARTWORKS_PROCESSED_DIR,
    ARTWORKS_FINALISED_DIR,
    BASE_DIR,
    ANALYSIS_STATUS_FILE,
)
import config

from PIL import Image
import io
import scripts.analyze_artwork as aa

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    Response,
)
import re
from utils.sellbrite_api import SellbriteAPI
from .sellbrite_export import generate_sellbrite_json

from . import utils
from .utils import (
    ALLOWED_COLOURS_LOWER,
    relative_to_base,
    FINALISED_DIR,
    parse_csv_list,
    join_csv_list,
    read_generic_text,
    clean_terms,
    infer_sku_from_filename,
    sync_filename_with_sku,
    is_finalised_image,
    get_allowed_colours,
)

bp = Blueprint("artwork", __name__)


# --- SECTION: Helper Functions ---


def _write_analysis_status(step: str, percent: int, file: str | None = None) -> None:
    """Write simple progress info for frontend polling."""
    try:
        ANALYSIS_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ANALYSIS_STATUS_FILE.write_text(
            json.dumps({"step": step, "percent": percent, "file": file})
        )
    except Exception:
        pass


@bp.route("/status/analyze")
def analysis_status():
    """Return JSON progress info for the current analysis job."""
    if ANALYSIS_STATUS_FILE.exists():
        data = json.loads(ANALYSIS_STATUS_FILE.read_text())
    else:
        data = {"step": "idle", "percent": 0}
    return Response(json.dumps(data), mimetype="application/json")


def validate_listing_fields(data: dict, generic_text: str) -> list[str]:
    """Return a list of validation error messages for the listing."""
    errors: list[str] = []

    title = data.get("title", "").strip()
    if not title:
        errors.append("Title cannot be blank")
    if len(title) > 140:
        errors.append("Title exceeds 140 characters")

    tags = data.get("tags", [])
    if len(tags) > 13:
        errors.append("Too many tags (max 13)")
    seen = set()
    for t in tags:
        if not t or len(t) > 20:
            errors.append(f"Invalid tag: '{t}'")
        if "-" in t or "," in t:
            errors.append(f"Tag may not contain hyphens or commas: '{t}'")
        if not re.fullmatch(r"[A-Za-z0-9 ]+", t):
            errors.append(f"Tag has invalid characters: '{t}'")
        low = t.lower()
        if low in seen:
            errors.append(f"Duplicate tag: '{t}'")
        seen.add(low)

    materials = data.get("materials", [])
    if len(materials) > 13:
        errors.append("Too many materials (max 13)")
    seen_mats = set()
    for m in materials:
        if len(m) > 45:
            errors.append(f"Material too long: '{m}'")
        if not re.fullmatch(r"[A-Za-z0-9 ,]+", m):
            errors.append(f"Material has invalid characters: '{m}'")
        ml = m.lower()
        if ml in seen_mats:
            errors.append(f"Duplicate material: '{m}'")
        seen_mats.add(ml)

    seo_filename = data.get("seo_filename", "")
    if len(seo_filename) > 70:
        errors.append("SEO filename exceeds 70 characters")
    if " " in seo_filename or not re.fullmatch(r"[A-Za-z0-9.-]+", seo_filename):
        errors.append("SEO filename has invalid characters or spaces")
    if not re.search(r"Artwork-by-Robin-Custance-RJC-[A-Za-z0-9-]+\.jpg$", seo_filename):
        errors.append("SEO filename must end with 'Artwork-by-Robin-Custance-RJC-XXXX.jpg'")

    sku = data.get("sku", "")
    if not sku:
        errors.append("SKU is required")
    if len(sku) > 32 or not re.fullmatch(r"[A-Za-z0-9-]+", sku):
        errors.append("SKU must be <=32 chars and alphanumeric/hyphen")
    if sku and not sku.startswith("RJC-"):
        errors.append("SKU must start with 'RJC-'")
    if sku and infer_sku_from_filename(seo_filename or "") != sku:
        errors.append("SKU must match value in SEO filename")

    try:
        price = float(data.get("price"))
        if abs(price - 17.88) > 1e-2:
            errors.append("Price must be 17.88")
    except Exception:
        errors.append("Price must be a number (17.88)")

    for colour_key in ("primary_colour", "secondary_colour"):
        col = data.get(colour_key, "").strip()
        if not col:
            errors.append(f"{colour_key.replace('_', ' ').title()} is required")
            continue
        if col.lower() not in ALLOWED_COLOURS_LOWER:
            errors.append(f"{colour_key.replace('_', ' ').title()} invalid")

    images = [i.strip() for i in data.get("images", []) if str(i).strip()]
    if not images:
        errors.append("At least one image required")
    for img in images:
        if " " in img or not re.search(r"\.(jpg|jpeg|png)$", img, re.I):
            errors.append(f"Invalid image filename: '{img}'")
        if not is_finalised_image(img):
            errors.append(f"Image not in finalised-artwork folder: '{img}'")

    desc = data.get("description", "").strip()
    if len(desc.split()) < 400:
        errors.append("Description must be at least 400 words")
    GENERIC_MARKER = "About the Artist – Robin Custance"
    if generic_text:
        # Normalise whitespace for both description and generic block
        desc_norm = " ".join(desc.split()).lower()
        generic_norm = " ".join(generic_text.split()).lower()
        # Only require that the generic marker exists somewhere in the description (case-insensitive)
        if GENERIC_MARKER.lower() not in desc_norm:
            errors.append(
                f"Description must include the correct generic context block: {GENERIC_MARKER}"
            )
        if "<" in desc or ">" in desc:
            errors.append("Description may not contain HTML")

        return errors


# --- SECTION: Basic Views ---
@bp.app_context_processor
def inject_latest_artwork():
    """Inject info about the most recently analysed artwork into templates."""
    latest = utils.latest_analyzed_artwork()
    return dict(latest_artwork=latest)


@bp.route("/")
def home():
    """Homepage showing the most recently analysed artwork."""
    latest = utils.latest_analyzed_artwork()
    return render_template("index.html", menu=utils.get_menu(), latest_artwork=latest)


@bp.route("/upload", methods=["GET", "POST"])
def upload_artwork():
    """Upload new artwork files and run pre-QC then AI analysis."""
    if request.method == "POST":
        files = request.files.getlist("images")
        results = []
        for f in files:
            res = _process_upload_file(f)
            results.append(res)

        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return json.dumps(results), 200, {"Content-Type": "application/json"}

        successes = [r for r in results if r["success"]]
        if successes:
            flash(f"Uploaded {len(successes)} file(s) successfully", "success")
        failures = [r for r in results if not r["success"]]
        for f in failures:
            flash(f"{f['original']}: {f['error']}", "danger")

        if request.accept_mimetypes.accept_html:
            return redirect(url_for("artwork.artworks"))
        return json.dumps(results), 200, {"Content-Type": "application/json"}
    return render_template("upload.html", menu=utils.get_menu())


@bp.route("/artworks")
def artworks():
    """List artworks in various processing states."""
    processed, processed_names = utils.list_processed_artworks()
    ready = utils.list_ready_to_analyze(processed_names)
    finalised = utils.list_finalised_artworks()
    return render_template(
        "artworks.html",
        ready_artworks=ready,
        processed_artworks=processed,
        finalised_artworks=finalised,
        menu=utils.get_menu(),
    )


# --- SECTION: Mockup Selection ---
@bp.route("/select", methods=["GET", "POST"])
def select():
    """Display and manage mockup slot selections."""
    if "slots" not in session or request.args.get("reset") == "1":
        utils.init_slots()
    slots = session["slots"]
    options = utils.compute_options(slots)
    zipped = list(zip(slots, options))
    return render_template("mockup_selector.html", zipped=zipped, menu=utils.get_menu())


@bp.route("/regenerate", methods=["POST"])
def regenerate():
    """Regenerate a random mockup image for a slot."""
    slot_idx = int(request.form["slot"])
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        cat = slots[slot_idx]["category"]
        slots[slot_idx]["image"] = utils.random_image(cat)
        session["slots"] = slots
    return redirect(url_for("artwork.select"))


@bp.route("/swap", methods=["POST"])
def swap():
    """Swap a slot to a new category and random image."""
    slot_idx = int(request.form["slot"])
    new_cat = request.form["new_category"]
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        slots[slot_idx]["category"] = new_cat
        slots[slot_idx]["image"] = utils.random_image(new_cat)
        session["slots"] = slots
    return redirect(url_for("artwork.select"))


@bp.route("/proceed", methods=["POST"])
def proceed():
    """Persist selected mockups and invoke composite generation."""
    slots = session.get("slots", [])
    if not slots:
        flash("No mockups selected!", "danger")
        return redirect(url_for("artwork.select"))
    utils.SELECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    selection_id = str(uuid.uuid4())
    selection_file = utils.SELECTIONS_DIR / f"{selection_id}.json"
    with open(selection_file, "w") as f:
        json.dump(slots, f, indent=2)
    log_file = utils.LOGS_DIR / f"composites_{selection_id}.log"
    try:
        result = subprocess.run(
            ["python3", str(utils.GENERATE_SCRIPT_PATH), str(selection_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=utils.BASE_DIR,
        )
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode == 0:
            flash("Composites generated successfully!", "success")
        else:
            flash("Composite generation failed. See logs for details.", "danger")
    except Exception as e:
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash("Error running the composite generator.", "danger")

    latest = utils.latest_composite_folder()
    if latest:
        session["latest_seo_folder"] = latest
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    return redirect(url_for("artwork.composites_preview"))
# --- SECTION: Artwork Analysis ---


@bp.route("/analyze/<aspect>/<filename>", methods=["POST"], endpoint="analyze_artwork")
def analyze_artwork_route(aspect, filename):
    """Run the AI analysis pipeline for a stored artwork."""
    artwork_path = utils.ARTWORKS_DIR / aspect / filename
    _write_analysis_status("starting", 0, filename)
    if not artwork_path.exists():
        try:
            fallback_folder = utils.find_seo_folder_from_filename(aspect, filename)
            for base in (utils.ARTWORK_PROCESSED_DIR, utils.FINALISED_DIR):
                candidate = base / fallback_folder / f"{fallback_folder}.jpg"
                if candidate.exists():
                    artwork_path = candidate
                    break
        except FileNotFoundError:
            pass
    log_id = str(uuid.uuid4())
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"
    try:
        cmd = ["python3", str(utils.ANALYZE_SCRIPT_PATH), str(artwork_path)]
        _write_analysis_status("openai_call", 20, filename)
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash(
                f"❌ Analysis failed for {filename}: {result.stderr}",
                "danger",
            )
            _write_analysis_status("failed", 100, filename)
    except Exception as e:
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash(f"❌ Error running analysis: {str(e)}", "danger")
        _write_analysis_status("failed", 100, filename)

    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash(
            f"Analysis complete, but no SEO folder/listing found for {filename} ({aspect}).",
            "warning",
        )
        return redirect(url_for("artwork.artworks"))

    listing_path = (
        utils.ARTWORK_PROCESSED_DIR
        / seo_folder
        / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_folder)
    )
    new_filename = f"{seo_folder}.jpg"
    try:
        with open(listing_path, "r", encoding="utf-8") as lf:
            listing_data = json.load(lf)
            new_filename = listing_data.get("seo_filename", new_filename)
    except Exception:
        pass

    try:
        cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
        _write_analysis_status("generating", 60, filename)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=utils.BASE_DIR, timeout=600)
        composite_log_file = utils.LOGS_DIR / f"composite_gen_{log_id}.log"
        with open(composite_log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash("Artwork analyzed, but mockup generation failed. See logs.", "danger")
    except Exception as e:
        flash(f"Composites generation error: {e}", "danger")
    
    _write_analysis_status("done", 100, filename)
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=new_filename))


@bp.post("/analyze-upload/<base>")
def analyze_upload(base):
    """Analyze an uploaded image from the temporary folder."""
    qc_path = config.UPLOADS_TEMP_DIR / f"{base}.qc.json"
    if not qc_path.exists():
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    try:
        with open(qc_path, "r", encoding="utf-8") as f:
            qc = json.load(f)
    except Exception:
        flash("Invalid QC data", "danger")
        return redirect(url_for("artwork.artworks"))

    ext = qc.get("extension", "jpg")
    orig_path = config.UPLOADS_TEMP_DIR / f"{base}.{ext}"
    processed_root = ARTWORKS_PROCESSED_DIR
    log_id = uuid.uuid4().hex
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"
    _write_analysis_status("starting", 0, orig_path.name)
    try:
        cmd = ["python3", str(utils.ANALYZE_SCRIPT_PATH), str(orig_path)]
        _write_analysis_status("openai_call", 20, orig_path.name)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash(f"❌ Analysis failed: {result.stderr}", "danger")
            _write_analysis_status("failed", 100, orig_path.name)
            return redirect(url_for("artwork.artworks"))
    except Exception as e:  # noqa: BLE001
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash(f"❌ Error running analysis: {e}", "danger")
        _write_analysis_status("failed", 100, orig_path.name)
        return redirect(url_for("artwork.artworks"))

    try:
        seo_folder = utils.find_seo_folder_from_filename(qc.get("aspect_ratio", ""), orig_path.name)
    except FileNotFoundError:
        flash(
            f"Analysis complete, but no SEO folder/listing found for {orig_path.name} ({qc.get('aspect_ratio','')}).",
            "warning",
        )
        return redirect(url_for("artwork.artworks"))

    listing_data = None
    listing_path = (
        utils.ARTWORK_PROCESSED_DIR
        / seo_folder
        / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_folder)
    )
    if listing_path.exists():
        try:
            with open(listing_path, "r", encoding="utf-8") as lf:
                listing_data = json.load(lf)
        except Exception:
            listing_data = None

    for suffix in [f".{ext}", "-thumb.jpg", "-analyse.jpg", ".qc.json"]:
        temp_file = config.UPLOADS_TEMP_DIR / f"{base}{suffix}"
        if not temp_file.exists():
            continue
        template_key = (
            "analyse" if suffix == "-analyse.jpg" else "thumbnail" if suffix == "-thumb.jpg" else "qc_json" if suffix.endswith(".qc.json") else "artwork"
        )
        dest = processed_root / seo_folder / config.FILENAME_TEMPLATES.get(template_key).format(seo_slug=seo_folder)
        if suffix == "-analyse.jpg" and dest.exists():
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            dest = dest.with_name(f"{dest.stem}-{ts}{dest.suffix}")
        shutil.move(str(temp_file), dest)

    try:
        cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
        _write_analysis_status("generating", 60, orig_path.name)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=utils.BASE_DIR, timeout=600)
        composite_log = utils.LOGS_DIR / f"composite_gen_{log_id}.log"
        with open(composite_log, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash("Artwork analyzed, but mockup generation failed.", "danger")
    except Exception as e:  # noqa: BLE001
        flash(f"Composites generation error: {e}", "danger")

    aspect = listing_data.get("aspect_ratio", qc.get("aspect_ratio", "")) if listing_data else qc.get("aspect_ratio", "")
    new_filename = f"{seo_folder}.jpg"
    if listing_data:
        new_filename = listing_data.get("seo_filename", new_filename)
    _write_analysis_status("done", 100, orig_path.name)
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=new_filename))


@bp.route("/review/<aspect>/<filename>")
def review_artwork(aspect, filename):
    """Legacy URL – redirect to the new edit/review page."""
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/review/<aspect>/<filename>/regenerate/<int:slot_idx>", methods=["POST"])
def review_regenerate_mockup(aspect, filename, slot_idx):
    """Regenerate a specific mockup while reviewing legacy listings."""
    seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    utils.regenerate_one_mockup(seo_folder, slot_idx)
    return redirect(url_for("artwork.finalised_gallery"))

@bp.route("/review/<seo_folder>/swap/<int:slot_idx>", methods=["POST"])
def review_swap_mockup(seo_folder, slot_idx):
    """Swap a mockup to a new category during legacy review."""
    new_cat = request.form["new_category"]
    if not utils.swap_one_mockup(seo_folder, slot_idx, new_cat):
        flash("Failed to swap mockup", "danger")

    info = utils.find_aspect_filename_from_seo_folder(seo_folder)
    if info:
        aspect, filename = info
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))

    flash(
        "Could not locate the correct artwork for editing after swap. Please check the gallery.",
        "warning",
    )
    return redirect(url_for("artwork.finalised_gallery"))

@bp.route("/edit-listing/<aspect>/<filename>", methods=["GET", "POST"])
def edit_listing(aspect, filename):
    """Display and update a processed or finalised artwork listing."""

    try:
        seo_folder, folder, listing_path, finalised = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))

    try:
        with open(listing_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        flash(f"Error loading listing: {e}", "danger")
        return redirect(url_for("artwork.artworks"))

    generic_text = read_generic_text(aspect)
    if generic_text:
        data["generic_text"] = generic_text

    openai_info = data.get("openai_analysis")

    if request.method == "POST":
        action = request.form.get("action", "save")

        seo_field = request.form.get("seo_filename", data.get("seo_filename", f"{seo_folder}.jpg")).strip()
        # SKU comes exclusively from the listing JSON; users cannot edit it
        sku_val = str(data.get("sku", "")).strip()
        inferred = infer_sku_from_filename(seo_field) or ""
        if sku_val and inferred and sku_val != inferred:
            sku_val = inferred
            flash("SKU updated to match SEO filename", "info")
        elif not sku_val:
            sku_val = inferred
        seo_val = sync_filename_with_sku(seo_field, sku_val)

        form_data = {
            "title": request.form.get("title", data.get("title", "")).strip(),
            "description": request.form.get("description", data.get("description", "")).strip(),
            "tags": parse_csv_list(request.form.get("tags", "")),
            "materials": parse_csv_list(request.form.get("materials", "")),
            "primary_colour": request.form.get("primary_colour", data.get("primary_colour", "")).strip(),
            "secondary_colour": request.form.get("secondary_colour", data.get("secondary_colour", "")).strip(),
            "seo_filename": seo_val,
            "price": request.form.get("price", data.get("price", "17.88")).strip(),
            "sku": sku_val,
            "images": [i.strip() for i in request.form.get("images", "").splitlines() if i.strip()],
        }

        form_data["tags"], cleaned_tags = clean_terms(form_data["tags"])
        form_data["materials"], cleaned_mats = clean_terms(form_data["materials"])
        if cleaned_tags:
            flash(f"Cleaned tags: {join_csv_list(form_data['tags'])}", "success")
        if cleaned_mats:
            flash(f"Cleaned materials: {join_csv_list(form_data['materials'])}", "success")

        if action == "delete":
            shutil.rmtree(utils.ARTWORK_PROCESSED_DIR / seo_folder, ignore_errors=True)
            shutil.rmtree(utils.FINALISED_DIR / seo_folder, ignore_errors=True)
            try:
                os.remove(utils.ARTWORKS_DIR / aspect / filename)
            except Exception:
                pass
            flash("Artwork deleted", "success")
            return redirect(url_for("artwork.artworks"))

        folder.mkdir(parents=True, exist_ok=True)
        img_files = [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        form_data["images"] = [relative_to_base(p) for p in sorted(img_files)]

        errors = validate_listing_fields(form_data, generic_text)
        if errors:
            form_data["images"] = "\n".join(form_data.get("images", []))
            form_data["tags"] = join_csv_list(form_data.get("tags", []))
            form_data["materials"] = join_csv_list(form_data.get("materials", []))
            mockups = []
            for idx, mp in enumerate(data.get("mockups", [])):
                if isinstance(mp, dict):
                    out = folder / mp.get("composite", "")
                    cat = mp.get("category", "")
                else:
                    p = Path(mp)
                    out = folder / f"{seo_folder}-{p.stem}.jpg"
                    cat = p.parent.name
                mockups.append({"path": out, "category": cat, "exists": out.exists(), "index": idx})
            return render_template(
                "edit_listing.html",
                artwork=form_data,
                errors=errors,
                aspect=aspect,
                filename=filename,
                seo_folder=seo_folder,
                mockups=mockups,
                menu=utils.get_menu(),
                colour_options=get_allowed_colours(),
                categories=utils.get_categories(),
                finalised=finalised,
                locked=data.get("locked", False),
                editable=not data.get("locked", False),
                openai_analysis=openai_info,
                generic_text=generic_text,
            )

        data.update(form_data)
        data["generic_text"] = generic_text

        full_desc = re.sub(r"\s+$", "", form_data["description"])
        gen = generic_text.strip()
        if gen and not full_desc.endswith(gen):
            full_desc = re.sub(r"\n{3,}", "\n\n", full_desc.rstrip()) + "\n\n" + gen
        data["description"] = full_desc.strip()

        with open(listing_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        flash("Listing updated", "success")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))

    raw_ai = data.get("ai_listing")
    ai = {}
    fallback_ai: dict = {}

    def parse_fallback(text: str) -> dict:
        match = re.search(r"```json\s*({.*?})\s*```", text, re.DOTALL)
        if not match:
            match = re.search(r"({.*})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                return {}
        return {}

    if isinstance(raw_ai, dict):
        ai = raw_ai
        if isinstance(raw_ai.get("fallback_text"), str):
            fallback_ai.update(parse_fallback(raw_ai.get("fallback_text")))
    elif isinstance(raw_ai, str):
        try:
            ai = json.loads(raw_ai)
        except Exception:
            fallback_ai.update(parse_fallback(raw_ai))

    if isinstance(data.get("fallback_text"), str):
        fallback_ai.update(parse_fallback(data["fallback_text"]))

    price = data.get("price") or ai.get("price") or fallback_ai.get("price") or "17.88"
    sku = (
        data.get("sku")
        or ai.get("sku")
        or fallback_ai.get("sku")
        or infer_sku_from_filename(data.get("seo_filename", ""))
        or ""
    )
    primary = data.get("primary_colour") or ai.get("primary_colour") or fallback_ai.get("primary_colour", "")
    secondary = data.get("secondary_colour") or ai.get("secondary_colour") or fallback_ai.get("secondary_colour", "")

    images = data.get("images")
    if not images:
        imgs = [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        images = [relative_to_base(p) for p in sorted(imgs)]
    else:
        images = [relative_to_base(Path(p)) for p in images]

    artwork = {
        "title": data.get("title") or ai.get("title") or fallback_ai.get("title", ""),
        "description": data.get("description") or ai.get("description") or fallback_ai.get("description", ""),
        "tags": join_csv_list(data.get("tags") or ai.get("tags") or fallback_ai.get("tags", [])),
        "materials": join_csv_list(data.get("materials") or ai.get("materials") or fallback_ai.get("materials", [])),
        "primary_colour": primary,
        "secondary_colour": secondary,
        "seo_filename": data.get("seo_filename") or ai.get("seo_filename") or fallback_ai.get("seo_filename") or f"{seo_folder}.jpg",
        "price": price,
        "sku": sku,
        "images": "\n".join(images),
    }

    if not artwork.get("title"):
        artwork["title"] = seo_folder.replace("-", " ").title()
    if not artwork.get("description"):
        artwork["description"] = "(No description found. Try re-analyzing or check AI output.)"

    artwork["full_listing_text"] = utils.build_full_listing_text(
        artwork.get("description", ""), data.get("generic_text", "")
    )

    mockups = []
    for idx, mp in enumerate(data.get("mockups", [])):
        if isinstance(mp, dict):
            out = folder / mp.get("composite", "")
            cat = mp.get("category", "")
        else:
            p = Path(mp)
            out = folder / f"{seo_folder}-{p.stem}.jpg"
            cat = p.parent.name
        mockups.append({"path": out, "category": cat, "exists": out.exists(), "index": idx})
    return render_template(
        "edit_listing.html",
        artwork=artwork,
        aspect=aspect,
        filename=filename,
        seo_folder=seo_folder,
        mockups=mockups,
        menu=utils.get_menu(),
        errors=None,
        colour_options=get_allowed_colours(),
        categories=utils.get_categories(),
        finalised=finalised,
        locked=data.get("locked", False),
        editable=not data.get("locked", False),
        openai_analysis=openai_info,
        generic_text=data.get("generic_text", ""),
    )


_PROCESSED_REL = ARTWORKS_PROCESSED_DIR.relative_to(BASE_DIR).as_posix()
_FINALISED_REL = ARTWORKS_FINALISED_DIR.relative_to(BASE_DIR).as_posix()


@bp.route(f"/static/{_PROCESSED_REL}/<seo_folder>/<filename>")
def processed_image(seo_folder, filename):
    """Serve artwork images from processed or finalised folders."""
    final_folder = utils.FINALISED_DIR / seo_folder
    if (final_folder / filename).exists():
        folder = final_folder
    else:
        folder = utils.ARTWORK_PROCESSED_DIR / seo_folder
    return send_from_directory(folder, filename)


@bp.route(f"/static/{_FINALISED_REL}/<seo_folder>/<filename>")
def finalised_image(seo_folder, filename):
    """Serve images strictly from the finalised-artwork folder."""
    folder = utils.FINALISED_DIR / seo_folder
    return send_from_directory(folder, filename)


@bp.route("/artwork-img/<aspect>/<filename>")
def artwork_image(aspect, filename):
    """Serve the original uploaded artwork if it exists."""
    folder = utils.ARTWORKS_DIR / aspect
    candidate = folder / filename
    if candidate.exists():
        return send_from_directory(str(folder.resolve()), filename)
    alt_folder = utils.ARTWORKS_DIR / f"{aspect}-artworks" / Path(filename).stem
    candidate = alt_folder / filename
    if candidate.exists():
        return send_from_directory(str(alt_folder.resolve()), filename)
    return "", 404


@bp.route("/temp-img/<filename>")
def temp_image(filename):
    """Serve images from the temporary upload directory."""
    return send_from_directory(config.UPLOADS_TEMP_DIR, filename)


@bp.route("/mockup-img/<category>/<filename>")
def mockup_img(category, filename):
    """Return a stored mockup image by category."""
    return send_from_directory(utils.MOCKUPS_DIR / category, filename)


@bp.route("/composite-img/<folder>/<filename>")
def composite_img(folder, filename):
    """Serve generated composite images."""
    return send_from_directory(utils.COMPOSITES_DIR / folder, filename)


@bp.route("/composites")
def composites_preview():
    """Redirect to the latest composite preview if available."""
    latest = utils.latest_composite_folder()
    if latest:
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    flash("No composites found", "warning")
    return redirect(url_for("artwork.artworks"))


@bp.route("/composites/<seo_folder>")
def composites_specific(seo_folder):
    """Show composite images for a specific SEO folder."""
    folder = utils.ARTWORK_PROCESSED_DIR / seo_folder
    json_path = folder / f"{seo_folder}-listing.json"
    images = []
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as jf:
            listing = json.load(jf)
        for idx, mp in enumerate(listing.get("mockups", [])):
            if isinstance(mp, dict):
                out = folder / mp.get("composite", "")
                cat = mp.get("category", "")
            else:
                p = Path(mp)
                out = folder / f"{seo_folder}-{p.stem}.jpg"
                cat = p.parent.name
            images.append({"filename": out.name, "category": cat, "index": idx, "exists": out.exists()})
    else:
        for idx, img in enumerate(sorted(folder.glob(f"{seo_folder}-mockup-*.jpg"))):
            images.append({"filename": img.name, "category": None, "index": idx, "exists": True})
    return render_template("composites_preview.html", images=images, folder=seo_folder, menu=utils.get_menu())


@bp.route("/composites/<seo_folder>/regenerate/<int:slot_index>", methods=["POST"])
def regenerate_composite(seo_folder, slot_index):
    """Regenerate a single composite image in-place."""
    utils.regenerate_one_mockup(seo_folder, slot_index)
    return redirect(url_for("artwork.composites_specific", seo_folder=seo_folder))


@bp.route("/approve_composites/<seo_folder>", methods=["POST"])
def approve_composites(seo_folder):
    """Mark composites as approved (placeholder)."""
    flash("Composites approved", "success")
    return redirect(url_for("artwork.composites_specific", seo_folder=seo_folder))


@bp.route("/finalise/<aspect>/<filename>", methods=["GET", "POST"])
def finalise_artwork(aspect, filename):
    """Move processed artwork to finalised location and update listing data."""
    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))

    processed_dir = utils.ARTWORK_PROCESSED_DIR / seo_folder
    final_dir = utils.FINALISED_DIR / seo_folder
    log_path = utils.LOGS_DIR / "finalise.log"

    # ------------------------------------------------------------------
    # Move processed artwork into the finalised location and update paths
    # ------------------------------------------------------------------
    try:
        if final_dir.exists():
            raise FileExistsError(f"{final_dir} already exists")

        shutil.move(str(processed_dir), str(final_dir))

        # Marker file indicating finalisation time
        (final_dir / "finalised.txt").write_text(
            datetime.datetime.now().isoformat(), encoding="utf-8"
        )

        # Remove original artwork from input directory if it still exists
        orig_input = utils.ARTWORKS_DIR / aspect / filename
        try:
            os.remove(orig_input)
        except FileNotFoundError:
            pass

        # Update any stored paths within the listing JSON
        listing_file = final_dir / f"{seo_folder}-listing.json"
        if listing_file.exists():
            # Always allocate a fresh SKU on finalisation
            utils.assign_or_get_sku(listing_file, config.SKU_TRACKER, force=True)
            with open(listing_file, "r", encoding="utf-8") as lf:
                listing_data = json.load(lf)
            listing_data.setdefault("locked", False)

            def _swap_path(p: str) -> str:
                return p.replace(
                    str(utils.ARTWORK_PROCESSED_DIR), str(utils.FINALISED_DIR)
                )

            for key in ("main_jpg_path", "orig_jpg_path", "thumb_jpg_path", "processed_folder"):
                if isinstance(listing_data.get(key), str):
                    listing_data[key] = _swap_path(listing_data[key])

            if isinstance(listing_data.get("images"), list):
                listing_data["images"] = [
                    _swap_path(img) if isinstance(img, str) else img
                    for img in listing_data["images"]
                ]

            imgs = [p for p in final_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
            listing_data["images"] = [utils.relative_to_base(p) for p in sorted(imgs)]

            with open(listing_file, "w", encoding="utf-8") as lf:
                json.dump(listing_data, lf, indent=2, ensure_ascii=False)

        with open(log_path, "a", encoding="utf-8") as log:
            user = session.get("user", "anonymous")
            log.write(f"{datetime.datetime.now().isoformat()} - {seo_folder} by {user}\n")

        flash("Artwork finalised", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Failed to finalise artwork: {e}", "danger")

    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/finalised")
def finalised_gallery():
    """Display all finalised artworks in a gallery view."""
    artworks = []
    if utils.FINALISED_DIR.exists():
        for folder in utils.FINALISED_DIR.iterdir():
            if not folder.is_dir():
                continue
            listing_file = folder / f"{folder.name}-listing.json"
            if not listing_file.exists():
                continue
            try:
                with open(listing_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            entry = {
                "seo_folder": folder.name,
                "title": data.get("title") or utils.prettify_slug(folder.name),
                "description": data.get("description", ""),
                "sku": data.get("sku", ""),
                "primary_colour": data.get("primary_colour", ""),
                "secondary_colour": data.get("secondary_colour", ""),
                "price": data.get("price", ""),
                "seo_filename": data.get("seo_filename", f"{folder.name}.jpg"),
                "tags": data.get("tags", []),
                "materials": data.get("materials", []),
                "aspect": data.get("aspect_ratio", ""),
                "filename": data.get("filename", f"{folder.name}.jpg"),
                "locked": data.get("locked", False),
                "mockups": [],
            }

            for mp in data.get("mockups", []):
                if isinstance(mp, dict):
                    out = folder / mp.get("composite", "")
                else:
                    p = Path(mp)
                    out = folder / f"{folder.name}-{p.stem}.jpg"
                if out.exists():
                    entry["mockups"].append({"filename": out.name})

            # Filter images that actually exist on disk
            images = []
            for img in data.get("images", []):
                img_path = utils.BASE_DIR / img
                if img_path.exists():
                    images.append(img)
            entry["images"] = images

            ts = folder / "finalised.txt"
            entry["date"] = ts.stat().st_mtime if ts.exists() else listing_file.stat().st_mtime

            main_img = folder / f"{folder.name}.jpg"
            entry["main_image"] = main_img.name if main_img.exists() else None

            artworks.append(entry)
    artworks.sort(key=lambda x: x.get("date", 0), reverse=True)
    return render_template("finalised.html", artworks=artworks, menu=utils.get_menu())


@bp.route("/locked")
def locked_gallery():
    """Show gallery of locked artworks only."""
    locked_items = [a for a in utils.list_finalised_artworks_extended() if a.get("locked")]
    return render_template("locked.html", artworks=locked_items, menu=utils.get_menu())


@bp.post("/update-links/<aspect>/<filename>")
def update_links(aspect, filename):
    """Regenerate image URL list from disk for either processed or finalised artwork.

    If the request was sent via AJAX (accepting JSON or using the ``XMLHttpRequest``
    header) the refreshed list of image URLs is returned as JSON rather than
    performing a redirect. This allows the edit page to update the textarea in
    place without losing form state.
    """

    wants_json = "application/json" in request.headers.get("Accept", "") or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    try:
        seo_folder, folder, listing_file, _ = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        msg = "Artwork not found"
        if wants_json:
            return {"success": False, "message": msg, "images": []}, 404
        flash(msg, "danger")
        return redirect(url_for("artwork.artworks"))

    try:
        with open(listing_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        imgs = [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        data["images"] = [utils.relative_to_base(p) for p in sorted(imgs)]
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        msg = "Image links updated"
        if wants_json:
            return {"success": True, "message": msg, "images": data["images"]}
        flash(msg, "success")
    except Exception as e:  # noqa: BLE001
        msg = f"Failed to update links: {e}"
        if wants_json:
            return {"success": False, "message": msg, "images": []}, 500
        flash(msg, "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/finalise/delete/<aspect>/<filename>")
def delete_finalised(aspect, filename):
    """Delete a finalised artwork folder."""
    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.finalised_gallery"))
    folder = utils.FINALISED_DIR / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    locked = False
    if listing_file.exists():
        try:
            with open(listing_file, "r", encoding="utf-8") as f:
                info = json.load(f)
            locked = info.get("locked", False)
        except Exception:
            pass
    if locked and request.form.get("confirm") != "DELETE":
        flash("Type DELETE to confirm", "warning")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))
    try:
        shutil.rmtree(folder)
        flash("Finalised artwork deleted", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Delete failed: {e}", "danger")
    return redirect(url_for("artwork.finalised_gallery"))


@bp.post("/lock/<aspect>/<filename>")
def lock_listing(aspect, filename):
    """Mark a finalised artwork as locked."""
    try:
        seo, folder, listing, finalised = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    if not finalised:
        flash("Artwork must be finalised before locking", "danger")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))
    try:
        with open(listing, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["locked"] = True
        with open(listing, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        payload = generate_sellbrite_json(data)
        payload["quantity"] = config.SELLBRITE_DEFAULT_QUANTITY
        try:
            sb = SellbriteAPI()
            sb.create_product(payload)
            logging.getLogger(__name__).info(
                "Sellbrite product created for %s", data.get("sku")
            )
            flash("Artwork locked and sent to Sellbrite", "success")
        except Exception as exc:  # noqa: BLE001 - external API
            logging.getLogger(__name__).error("Sellbrite sync failed: %s", exc)
            flash(f"Artwork locked but Sellbrite sync failed: {exc}", "warning")
    except Exception as exc:  # noqa: BLE001
        flash(f"Failed to lock: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/unlock/<aspect>/<filename>")
def unlock_listing(aspect, filename):
    """Unlock a previously locked artwork."""
    try:
        seo, folder, listing, _ = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    try:
        with open(listing, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["locked"] = False
        with open(listing, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        flash("Artwork unlocked", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Failed to unlock: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/reset-sku/<aspect>/<filename>")
def reset_sku(aspect, filename):
    """Force reassign a new SKU for the given artwork."""
    try:
        seo, folder, listing, _ = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    try:
        utils.assign_or_get_sku(listing, config.SKU_TRACKER, force=True)
        flash("SKU reset", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Failed to reset SKU: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/finalise/push-sellbrite/<aspect>/<filename>")
def push_sellbrite_placeholder(aspect, filename):
    """Manually push a finalised artwork to Sellbrite."""
    try:
        seo, folder, listing, finalised = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    if not finalised:
        flash("Artwork must be finalised", "danger")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))
    try:
        with open(listing, "r", encoding="utf-8") as f:
            data = json.load(f)
        payload = generate_sellbrite_json(data)
        payload["quantity"] = config.SELLBRITE_DEFAULT_QUANTITY
        sb = SellbriteAPI()
        sb.create_product(payload)
        flash("Artwork pushed to Sellbrite", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Sellbrite push failed: {exc}", "danger")
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/logs/openai")
@bp.route("/logs/openai/<date>")
def view_openai_logs(date: str | None = None):
    """Return the tail of the most recent OpenAI analysis log."""
    logs = sorted(
        config.LOGS_DIR.glob("analyze-openai-calls-*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not logs:
        return Response("No logs found", mimetype="text/plain")

    target = None
    if date:
        cand = config.LOGS_DIR / f"analyze-openai-calls-{date}.log"
        if cand.exists():
            target = cand
    if not target:
        target = logs[0]

    text = target.read_text(encoding="utf-8")
    lines = text.strip().splitlines()[-50:]
    return Response("\n".join(lines), mimetype="text/plain")


@bp.route("/next-sku")
def preview_next_sku():
    """Return the next SKU without reserving it."""
    next_sku = peek_next_sku(config.SKU_TRACKER)
    return Response(next_sku, mimetype="text/plain")


def _process_upload_file(file_storage):
    """Handle single uploaded file through QC, AI and relocation."""
    result = {"original": file_storage.filename, "success": False, "error": ""}
    filename = file_storage.filename
    if not filename:
        result["error"] = "No filename"
        return result
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_EXTENSIONS:
        result["error"] = "Invalid file type"
        return result
    data = file_storage.read()
    if len(data) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        result["error"] = "File too large"
        return result
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except Exception:
        result["error"] = "Corrupted image"
        return result

    safe = aa.slugify(Path(filename).stem)
    unique = uuid.uuid4().hex[:8]
    base = f"{safe}-{unique}"
    config.UPLOADS_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    orig_path = config.UPLOADS_TEMP_DIR / f"{base}.{ext}"
    with open(orig_path, "wb") as f:
        f.write(data)

    with Image.open(orig_path) as img:
        width, height = img.size
        thumb_path = config.UPLOADS_TEMP_DIR / f"{base}-thumb.jpg"
        thumb = img.copy()
        thumb.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
        thumb.save(thumb_path, "JPEG", quality=80)

    analyse_path = config.UPLOADS_TEMP_DIR / f"{base}-analyse.jpg"
    with Image.open(orig_path) as img:
        w, h = img.size
        scale = config.ANALYSE_MAX_DIM / max(w, h)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        img = img.convert("RGB")

        q = 85
        while True:
            img.save(analyse_path, "JPEG", quality=q, optimize=True)
            if analyse_path.stat().st_size <= config.ANALYSE_MAX_MB * 1024 * 1024 or q <= 60:
                break
            q -= 5

    aspect = aa.get_aspect_ratio(orig_path)

    qc_data = {
        "original_filename": filename,
        "extension": ext,
        "image_shape": [width, height],
        "filesize_bytes": len(data),
        "aspect_ratio": aspect,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    qc_path = config.UPLOADS_TEMP_DIR / f"{base}.qc.json"
    qc_path.write_text(json.dumps(qc_data, indent=2))

    result.update({"success": True, "base": base, "aspect": aspect})
    return result


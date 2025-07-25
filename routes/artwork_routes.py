"""Artwork-related Flask routes.

This module powers the full listing workflow from initial review to
finalisation. It handles validation, moving files, regenerating image link
lists and serving gallery pages for processed and finalised artworks.
"""

# This file now references all path, directory, and filename variables strictly from config.py. No local or hardcoded path constants remain.
from __future__ import annotations

import json
import subprocess
import uuid
import random
import logging
from pathlib import Path
import shutil
import os
import traceback
import datetime
import time
from utils.logger_utils import log_action, strip_binary
from config import (
    PROCESSED_ROOT,
    FINALISED_ROOT,
    UNANALYSED_ROOT,
    ARTWORK_VAULT_ROOT,
    BASE_DIR,
    ANALYSIS_STATUS_FILE,
)
import config

# Initialise module logger immediately so early failures are captured
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

from PIL import Image
import io
import scripts.analyze_artwork as aa
import google.generativeai as genai

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    abort,
    Response,
    jsonify,
)
import re

from . import utils
from .utils import (
    ALLOWED_COLOURS_LOWER,
    relative_to_base,
    FINALISED_ROOT,
    parse_csv_list,
    join_csv_list,
    read_generic_text,
    clean_terms,
    infer_sku_from_filename,
    sync_filename_with_sku,
    is_finalised_image,
    get_allowed_colours,
    load_json_file_safe,
    generate_mockups_for_listing,
)
from utils.sku_assigner import peek_next_sku

bp = Blueprint("artwork", __name__)

# ---------------------------------------------------------------------------
# Health-check Endpoints
# ---------------------------------------------------------------------------


@bp.get("/health/openai")
def health_openai():
    """Return status of OpenAI connection."""
    logger = logging.getLogger(__name__)
    try:
        aa.client.models.list()
        return jsonify({"ok": True})
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenAI health check failed: %s", exc)
        debug = config.DEBUG
        error = str(exc)
        if debug:
            error += "\n" + traceback.format_exc()
        return jsonify({"ok": False, "error": error}), 500


@bp.get("/health/google")
def health_google():
    """Return status of Google Vision connection."""
    logger = logging.getLogger(__name__)
    try:
        genai.list_models()
        return jsonify({"ok": True})
    except Exception as exc:  # noqa: BLE001
        logger.error("Google health check failed: %s", exc)
        debug = config.DEBUG
        error = str(exc)
        if debug:
            error += "\n" + traceback.format_exc()
        return jsonify({"ok": False, "error": error}), 500


# Ensure analysis status file exists at import time
load_json_file_safe(ANALYSIS_STATUS_FILE)


def _write_analysis_status(
    step: str,
    percent: int,
    file: str | None = None,
    status: str | None = None,
    error: str | None = None,
) -> None:
    """Write progress info for frontend polling."""

    logger = logging.getLogger(__name__)

    try:
        ANALYSIS_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error(
            "Unable to create status directory %s: %s", ANALYSIS_STATUS_FILE.parent, exc
        )

    payload = {"step": step, "percent": percent, "file": file}
    if status:
        payload["status"] = status
    if error:
        payload["error"] = error

    try:
        ANALYSIS_STATUS_FILE.write_text(json.dumps(payload))
        logger.debug("STATUS WRITTEN %s", payload)
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Failed writing analysis status: %s", exc)
        try:
            ANALYSIS_STATUS_FILE.write_text(
                json.dumps({"step": "error", "error": str(exc)})
            )
        except Exception as sub_exc:
            logger.error("Failed resetting analysis status file: %s", sub_exc)


@bp.route("/status/analyze")
def analysis_status():
    """Return JSON progress info for the current analysis job."""
    data = load_json_file_safe(ANALYSIS_STATUS_FILE)
    if not data:
        data = {"step": "idle", "percent": 0, "status": "idle"}
    return Response(json.dumps(data), mimetype="application/json")


def _run_ai_analysis(img_path: Path, provider: str) -> dict:
    """Run the AI analysis script and return its JSON output."""
    logger = logging.getLogger("art_analysis")
    logger.info("[DEBUG] _run_ai_analysis: img_path=%s provider=%s cwd=%s", img_path, provider, os.getcwd())

    # Log key environment variables with API keys masked
    safe_env = {k: ("***" if "KEY" in k else v) for k, v in os.environ.items()}
    logger.info("[DEBUG] ENV: %s", safe_env)

    if not img_path.exists():
        logger.warning("[DEBUG] Image path does not exist: %s", img_path)

    if provider == "openai":
        script_path = config.SCRIPTS_DIR / "analyze_artwork.py"
        cmd = [
            "python3",
            str(script_path),
            str(img_path),
            "--provider",
            "openai",
            "--json-output",
        ]
    elif provider == "google":
        script_path = config.SCRIPTS_DIR / "analyze_artwork_google.py"
        cmd = ["python3", str(script_path), str(img_path)]
    else:
        raise ValueError(f"Unknown provider: {provider}")

    logger.info("[DEBUG] Subprocess cmd: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        logger.error("AI analysis subprocess timed out for %s", img_path)
        raise RuntimeError("AI analysis timed out after 300 seconds")
    except Exception as exc:  # noqa: BLE001 - unexpected OSError
        logger.error("Subprocess execution failed: %s", exc)
        raise RuntimeError(str(exc)) from exc

    logger.info("[DEBUG] Returncode: %s", result.returncode)
    logger.info("[DEBUG] STDOUT: %s", result.stdout[:2000])
    logger.info("[DEBUG] STDERR: %s", result.stderr[:2000])

    output = result.stdout.strip()
    logger.info("AI Analysis Output: %s", output)

    if result.returncode != 0:
        try:
            err = json.loads(result.stderr)
            msg = err.get("error", "Unknown error")
        except Exception:
            msg = (result.stderr or "Unknown error").strip()
        raise RuntimeError(f"AI analysis failed: {msg}")

    if not output:
        raise RuntimeError("AI analysis failed. Please try again.")

    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s", e)
        raise RuntimeError("AI analysis output could not be parsed.")


def _generate_composites(seo_folder: str, log_id: str) -> None:
    cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=utils.BASE_DIR,
        timeout=600,
    )
    composite_log = utils.LOGS_DIR / f"composite_gen_{log_id}.log"
    with open(composite_log, "w") as log:
        log.write("=== STDOUT ===\n")
        log.write(result.stdout)
        log.write("\n\n=== STDERR ===\n")
        log.write(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Composite generation failed ({result.returncode})")


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
    if not re.search(
        r"Artwork-by-Robin-Custance-RJC-[A-Za-z0-9-]+\.jpg$", seo_filename
    ):
        errors.append(
            "SEO filename must end with 'Artwork-by-Robin-Custance-RJC-XXXX.jpg'"
        )

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


@bp.app_context_processor
def inject_latest_artwork():
    latest = utils.latest_analyzed_artwork()
    return dict(latest_artwork=latest)


@bp.route("/")
def home():
    latest = utils.latest_analyzed_artwork()
    return render_template("index.html", menu=utils.get_menu(), latest_artwork=latest)


@bp.route("/upload", methods=["GET", "POST"])
def upload_artwork():
    """Upload new artwork files and run pre-QC then AI analysis."""
    if request.method == "POST":
        files = request.files.getlist("images")
        folder = utils.create_unanalysed_subfolder()
        results = []
        user = session.get("username")
        for f in files:
            try:
                res = _process_upload_file(f, folder)
            except Exception as exc:  # noqa: BLE001 - unexpected IO
                logging.getLogger(__name__).error(
                    "Upload processing failed for %s: %s", f.filename, exc
                )
                res = {"original": f.filename, "success": False, "error": str(exc)}
            status = "success" if res.get("success") else "fail"
            log_action(
                "upload",
                res.get("original", f.filename),
                user,
                res.get("error", "uploaded"),
                status=status,
                error=res.get("error") if not res.get("success") else None,
            )
            results.append(res)

        if (
            request.accept_mimetypes.accept_json
            and not request.accept_mimetypes.accept_html
        ):
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


@bp.route("/select", methods=["GET", "POST"])
def select():
    if "slots" not in session or request.args.get("reset") == "1":
        utils.init_slots()
    slots = session["slots"]
    options = utils.compute_options(slots)
    zipped = list(zip(slots, options))
    return render_template("mockup_selector.html", zipped=zipped, menu=utils.get_menu())


@bp.route("/regenerate", methods=["POST"])
def regenerate():
    slot_idx = int(request.form["slot"])
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        cat = slots[slot_idx]["category"]
        slots[slot_idx]["image"] = utils.random_image(cat)
        session["slots"] = slots
    return redirect(url_for("artwork.select"))


@bp.route("/swap", methods=["POST"])
def swap():
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


@bp.route("/analyze/<aspect>/<filename>", methods=["POST"], endpoint="analyze_artwork")
def analyze_artwork_route(aspect, filename):
    """Run analysis on ``filename`` using the selected provider."""

    logger = logging.getLogger(__name__)

    provider = request.form.get("provider", "openai").lower()
    base_name = Path(filename).name

    _write_analysis_status("starting", 0, base_name, status="analyzing")

    # ------------------------------------------------------------------
    # Locate the source image from temporary uploads or processed output
    # ------------------------------------------------------------------
    src_path: Path | None = next(
        (p for p in config.UNANALYSED_ROOT.rglob(base_name) if p.is_file()), None
    )
    if not src_path.exists():
        src_path = None
        try:
            seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
            candidate = PROCESSED_ROOT / seo_folder / f"{Path(filename).stem}.jpg"
            if candidate.exists():
                src_path = candidate
        except FileNotFoundError:
            pass

    if not src_path or not src_path.exists():
        flash(f"Artwork file not found: {filename}", "danger")
        _write_analysis_status(
            "failed", 100, base_name, status="failed", error="file not found"
        )
        return redirect(url_for("artwork.artworks"))

    # ------------------------------------------------------------------
    # Copy file to provider input folder
    # ------------------------------------------------------------------
    dest_dir = UNANALYSED_ROOT / provider
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / base_name

    try:
        shutil.copy2(src_path, dest_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed copying %s to %s: %s", src_path, dest_path, exc)
        flash(f"Failed preparing file for analysis: {exc}", "danger")
        _write_analysis_status(
            "failed", 100, base_name, status="failed", error=str(exc)
        )
        return redirect(url_for("artwork.artworks"))

    # ------------------------------------------------------------------
    # Invoke the analyzer script with the provider-specific path
    # ------------------------------------------------------------------
    log_id = uuid.uuid4().hex
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"

    try:
        if provider == "google":
            script = config.SCRIPTS_DIR / "analyze_artwork_google.py"
            cmd = ["python3", str(script), str(dest_path)]
        else:
            cmd = [
                "python3",
                str(utils.ANALYZE_SCRIPT_PATH),
                str(dest_path),
                "--provider",
                "openai",
            ]
        env = os.environ.copy()
        env["USER_ID"] = session.get("user", "anonymous")
        _write_analysis_status(f"{provider}_call", 20, base_name, status="analyzing")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            env=env,
        )
        with open(log_file, "w", encoding="utf-8") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash(f"❌ Analysis failed for {filename}: {result.stderr}", "danger")
            _write_analysis_status(
                "failed",
                100,
                base_name,
                status="failed",
                error=result.stderr.strip(),
            )
            return redirect(
                url_for("artwork.edit_listing", aspect=aspect, filename=filename)
            )
    except Exception as exc:  # noqa: BLE001
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"\n\n=== Exception ===\n{exc}")
        logger.error("Error running analysis for %s: %s", filename, exc)
        flash(f"❌ Error running analysis: {exc}", "danger")
        _write_analysis_status(
            "failed", 100, base_name, status="failed", error=str(exc)
        )
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )

    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash(
            f"Analysis complete, but no SEO folder/listing found for {filename} ({aspect}).",
            "warning",
        )
        return redirect(url_for("artwork.artworks"))

    listing_path = (
        utils.PROCESSED_ROOT
        / seo_folder
        / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_folder)
    )
    new_filename = f"{seo_folder}.jpg"
    try:
        data = utils.load_json_file_safe(listing_path)
        new_filename = data.get("seo_filename", new_filename)
    except Exception:
        pass

    try:
        cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
        _write_analysis_status("generating", 60, filename, status="analyzing")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=utils.BASE_DIR,
            timeout=600,
        )
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

    _write_analysis_status("done", 100, filename, status="complete")
    return redirect(
        url_for("artwork.edit_listing", aspect=aspect, filename=new_filename)
    )


@bp.post("/analyze-upload/<base>")
def analyze_upload(base):
    """Analyze an uploaded image from the unanalysed folder."""
    uid, rec = utils.get_record_by_base(base)
    if not rec:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    folder = Path(rec["current_folder"])
    qc_path = folder / f"{base}.qc.json"
    try:
        qc = utils.load_json_file_safe(qc_path)
    except Exception:
        flash("Invalid QC data", "danger")
        return redirect(url_for("artwork.artworks"))

    ext = qc.get("extension", "jpg")
    orig_path = folder / f"{base}.{ext}"
    processed_root = PROCESSED_ROOT
    log_id = uuid.uuid4().hex
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"
    provider = request.form.get("provider", "openai")
    _write_analysis_status("starting", 0, orig_path.name, status="analyzing")
    try:
        if provider == "google":
            script = config.SCRIPTS_DIR / "analyze_artwork_google.py"
            cmd = ["python3", str(script), str(orig_path)]
        else:
            cmd = [
                "python3",
                str(utils.ANALYZE_SCRIPT_PATH),
                str(orig_path),
                "--provider",
                "openai",
            ]
        env = os.environ.copy()
        env["USER_ID"] = session.get("user", "anonymous")
        _write_analysis_status(
            f"{provider}_call", 20, orig_path.name, status="analyzing"
        )
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            env=env,
        )
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash(f"❌ Analysis failed: {result.stderr}", "danger")
            _write_analysis_status(
                "failed",
                100,
                orig_path.name,
                status="failed",
                error=result.stderr.strip(),
            )
            return redirect(url_for("artwork.artworks"))
    except Exception as e:  # noqa: BLE001
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash(f"❌ Error running analysis: {e}", "danger")
        _write_analysis_status(
            "failed", 100, orig_path.name, status="failed", error=str(e)
        )
        return redirect(url_for("artwork.artworks"))

    try:
        seo_folder = utils.find_seo_folder_from_filename(
            qc.get("aspect_ratio", ""), orig_path.name
        )
    except FileNotFoundError:
        flash(
            f"Analysis complete, but no SEO folder/listing found for {orig_path.name} ({qc.get('aspect_ratio','')}).",
            "warning",
        )
        return redirect(url_for("artwork.artworks"))

    listing_data = None
    listing_path = (
        utils.PROCESSED_ROOT
        / seo_folder
        / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_folder)
    )
    if listing_path.exists():
        # Use helper to guarantee a dict and avoid list-index errors
        listing_data = utils.load_json_file_safe(listing_path)

    for suffix in [f".{ext}", "-thumb.jpg", "-analyse.jpg", ".qc.json"]:
        temp_file = folder / f"{base}{suffix}"
        if not temp_file.exists():
            continue
        template_key = (
            "analyse"
            if suffix == "-analyse.jpg"
            else (
                "thumbnail"
                if suffix == "-thumb.jpg"
                else "qc_json" if suffix.endswith(".qc.json") else "artwork"
            )
        )
        dest = (
            processed_root
            / seo_folder
            / config.FILENAME_TEMPLATES.get(template_key).format(seo_slug=seo_folder)
        )
        if suffix == "-analyse.jpg" and dest.exists():
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            dest = dest.with_name(f"{dest.stem}-{ts}{dest.suffix}")
        utils.move_and_log(temp_file, dest, uid, "processed")

    try:
        cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
        _write_analysis_status("generating", 60, orig_path.name, status="analyzing")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=utils.BASE_DIR,
            timeout=600,
        )
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

    utils.cleanup_unanalysed_folders()

    aspect = (
        listing_data.get("aspect_ratio", qc.get("aspect_ratio", ""))
        if listing_data
        else qc.get("aspect_ratio", "")
    )
    new_filename = f"{seo_folder}.jpg"
    if listing_data:
        new_filename = listing_data.get("seo_filename", new_filename)
    _write_analysis_status("done", 100, orig_path.name, status="complete")
    return redirect(
        url_for("artwork.edit_listing", aspect=aspect, filename=new_filename)
    )


@bp.route("/review/<aspect>/<filename>")
def review_artwork(aspect, filename):
    """Legacy URL – redirect to the new edit/review page."""
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/review/<aspect>/<filename>/regenerate/<int:slot_idx>", methods=["POST"])
def review_regenerate_mockup(aspect, filename, slot_idx):
    seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    utils.regenerate_one_mockup(seo_folder, slot_idx)
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/review/<seo_folder>/swap/<int:slot_idx>", methods=["POST"])
def review_swap_mockup(seo_folder, slot_idx):
    new_cat = request.form["new_category"]
    success = utils.swap_one_mockup(seo_folder, slot_idx, new_cat)

    info = utils.find_aspect_filename_from_seo_folder(seo_folder)

    if (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    ):
        img_url = ""
        if success and info:
            aspect, _filename = info
            folder = utils.PROCESSED_ROOT / seo_folder
            listing = folder / f"{seo_folder}-listing.json"
            if not listing.exists():
                folder = utils.FINALISED_ROOT / seo_folder
                listing = folder / f"{seo_folder}-listing.json"
            try:
                data = utils.load_json_file_safe(listing)
                mp = data.get("mockups", [])[slot_idx]
                if isinstance(mp, dict):
                    comp = mp.get("composite")
                    if comp:
                        img_url = url_for(
                            "artwork.processed_image",
                            seo_folder=seo_folder,
                            filename=comp,
                        )
            except Exception:  # noqa: BLE001
                img_url = ""
        return jsonify({"success": success, "img_url": img_url})

    if not success:
        flash("Failed to swap mockup", "danger")

    if info:
        aspect, filename = info
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )

    flash(
        "Could not locate the correct artwork for editing after swap. Please check the gallery.",
        "warning",
    )
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/edit-listing/<aspect>/<filename>", methods=["GET", "POST"])
def edit_listing(aspect, filename):
    """Display and update a processed or finalised artwork listing."""

    try:
        seo_folder, folder, listing_path, finalised = utils.resolve_listing_paths(
            aspect, filename
        )
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))

    try:
        data = utils.load_json_file_safe(listing_path)
    except Exception as e:  # noqa: BLE001
        flash(f"Error loading listing: {e}", "danger")
        return redirect(url_for("artwork.artworks"))

    generic_text = read_generic_text(aspect)
    if generic_text:
        data["generic_text"] = generic_text

    openai_info = data.get("openai_analysis")

    if request.method == "POST":
        action = request.form.get("action", "save")

        seo_field = request.form.get(
            "seo_filename", data.get("seo_filename", f"{seo_folder}.jpg")
        ).strip()
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
            "description": request.form.get(
                "description", data.get("description", "")
            ).strip(),
            "tags": parse_csv_list(request.form.get("tags", "")),
            "materials": parse_csv_list(request.form.get("materials", "")),
            "primary_colour": request.form.get(
                "primary_colour", data.get("primary_colour", "")
            ).strip(),
            "secondary_colour": request.form.get(
                "secondary_colour", data.get("secondary_colour", "")
            ).strip(),
            "seo_filename": seo_val,
            "price": request.form.get("price", data.get("price", "17.88")).strip(),
            "sku": sku_val,
            "images": [
                i.strip()
                for i in request.form.get("images", "").splitlines()
                if i.strip()
            ],
        }

        form_data["tags"], cleaned_tags = clean_terms(form_data["tags"])
        form_data["materials"], cleaned_mats = clean_terms(form_data["materials"])
        if cleaned_tags:
            flash(f"Cleaned tags: {join_csv_list(form_data['tags'])}", "success")
        if cleaned_mats:
            flash(
                f"Cleaned materials: {join_csv_list(form_data['materials'])}", "success"
            )

        if action == "delete":
            shutil.rmtree(utils.PROCESSED_ROOT / seo_folder, ignore_errors=True)
            shutil.rmtree(utils.FINALISED_ROOT / seo_folder, ignore_errors=True)
            try:
                os.remove(utils.UNANALYSED_ROOT / aspect / filename)
            except Exception:
                pass
            flash("Artwork deleted", "success")
            log_action("edits", filename, session.get("username"), "deleted listing")
            return redirect(url_for("artwork.artworks"))

        folder.mkdir(parents=True, exist_ok=True)
        img_files = [
            p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
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
                mockups.append(
                    {"path": out, "category": cat, "exists": out.exists(), "index": idx}
                )
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
                categories=utils.get_mockup_categories(
                    config.MOCKUPS_INPUT_DIR / f"{aspect}-categorised"
                ),
                finalised=finalised,
                locked=data.get("locked", False),
                editable=not data.get("locked", False),
                openai_analysis=openai_info,
                cache_ts=int(time.time()),
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
        log_action("edits", filename, session.get("username"), "listing updated")
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )

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
    primary = (
        data.get("primary_colour")
        or ai.get("primary_colour")
        or fallback_ai.get("primary_colour", "")
    )
    secondary = (
        data.get("secondary_colour")
        or ai.get("secondary_colour")
        or fallback_ai.get("secondary_colour", "")
    )

    images = data.get("images")
    if not images:
        imgs = [
            p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        images = [relative_to_base(p) for p in sorted(imgs)]
    else:
        images = [relative_to_base(Path(p)) for p in images]

    artwork = {
        "title": data.get("title") or ai.get("title") or fallback_ai.get("title", ""),
        "description": data.get("description")
        or ai.get("description")
        or fallback_ai.get("description", ""),
        "tags": join_csv_list(
            data.get("tags") or ai.get("tags") or fallback_ai.get("tags", [])
        ),
        "materials": join_csv_list(
            data.get("materials")
            or ai.get("materials")
            or fallback_ai.get("materials", [])
        ),
        "primary_colour": primary,
        "secondary_colour": secondary,
        "seo_filename": data.get("seo_filename")
        or ai.get("seo_filename")
        or fallback_ai.get("seo_filename")
        or f"{seo_folder}.jpg",
        "price": price,
        "sku": sku,
        "images": "\n".join(images),
    }

    if not artwork.get("title"):
        artwork["title"] = seo_folder.replace("-", " ").title()
    if not artwork.get("description"):
        artwork["description"] = (
            "(No description found. Try re-analyzing or check AI output.)"
        )

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
        mockups.append(
            {"path": out, "category": cat, "exists": out.exists(), "index": idx}
        )
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
        categories=utils.get_mockup_categories(
            config.MOCKUPS_INPUT_DIR / f"{aspect}-categorised"
        ),
        finalised=finalised,
        locked=data.get("locked", False),
        editable=not data.get("locked", False),
        openai_analysis=openai_info,
        cache_ts=int(time.time()),
    )


_PROCESSED_REL = PROCESSED_ROOT.relative_to(BASE_DIR).as_posix()
_FINALISED_REL = FINALISED_ROOT.relative_to(BASE_DIR).as_posix()
_LOCKED_REL = utils.ARTWORK_VAULT_ROOT.relative_to(BASE_DIR).as_posix()


@bp.route(f"/static/{_PROCESSED_REL}/<seo_folder>/<filename>")
def processed_image(seo_folder, filename):
    """Serve artwork images from processed or finalised folders."""
    final_folder = utils.FINALISED_ROOT / seo_folder
    if (final_folder / filename).exists():
        folder = final_folder
    else:
        folder = utils.PROCESSED_ROOT / seo_folder
    file_path = folder / filename
    if not file_path.exists():
        current_app.logger.error("Image not found: %s", file_path)
        return "", 404
    return send_from_directory(folder, filename)


@bp.route(f"/static/{_FINALISED_REL}/<seo_folder>/<filename>")
def finalised_image(seo_folder, filename):
    """Serve images strictly from the finalised-artwork folder."""
    folder = utils.FINALISED_ROOT / seo_folder
    return send_from_directory(folder, filename)


@bp.route(f"/static/{_LOCKED_REL}/<seo_folder>/<filename>")
def locked_image(seo_folder, filename):
    """Serve images from the locked artwork vault."""
    folder = utils.ARTWORK_VAULT_ROOT / seo_folder
    return send_from_directory(folder, filename)


@bp.route("/artwork-img/<aspect>/<filename>")
def artwork_image(aspect, filename):
    folder = utils.UNANALYSED_ROOT / aspect
    candidate = folder / filename
    if candidate.exists():
        return send_from_directory(str(folder.resolve()), filename)
    alt_folder = utils.UNANALYSED_ROOT / f"{aspect}-artworks" / Path(filename).stem
    candidate = alt_folder / filename
    if candidate.exists():
        return send_from_directory(str(alt_folder.resolve()), filename)
    return "", 404


@bp.route("/unanalysed-img/<filename>")
def unanalysed_image(filename: str):
    """Serve images from the unanalysed artwork folders."""
    path = next(
        (p for p in config.UNANALYSED_ROOT.rglob(filename) if p.is_file()), None
    )
    if path:
        return send_from_directory(path.parent, path.name)
    abort(404)


@bp.route("/mockup-img/<category>/<filename>")
def mockup_img(category, filename):
    return send_from_directory(utils.MOCKUPS_DIR / category, filename)


@bp.route("/composite-img/<folder>/<filename>")
def composite_img(folder, filename):
    return send_from_directory(utils.COMPOSITES_DIR / folder, filename)


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
        for idx, mp in enumerate(listing.get("mockups", [])):
            if isinstance(mp, dict):
                out = folder / mp.get("composite", "")
                cat = mp.get("category", "")
            else:
                p = Path(mp)
                out = folder / f"{seo_folder}-{p.stem}.jpg"
                cat = p.parent.name
            images.append(
                {
                    "filename": out.name,
                    "category": cat,
                    "index": idx,
                    "exists": out.exists(),
                }
            )
    else:
        for idx, img in enumerate(sorted(folder.glob(f"{seo_folder}-mockup-*.jpg"))):
            images.append(
                {"filename": img.name, "category": None, "index": idx, "exists": True}
            )
    return render_template(
        "composites_preview.html",
        images=images,
        folder=seo_folder,
        menu=utils.get_menu(),
    )


@bp.route("/composites/<seo_folder>/regenerate/<int:slot_index>", methods=["POST"])
def regenerate_composite(seo_folder, slot_index):
    utils.regenerate_one_mockup(seo_folder, slot_index)
    return redirect(url_for("artwork.composites_specific", seo_folder=seo_folder))


@bp.route("/approve_composites/<seo_folder>", methods=["POST"])
def approve_composites(seo_folder):
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

    processed_dir = utils.PROCESSED_ROOT / seo_folder
    final_dir = utils.FINALISED_ROOT / seo_folder
    user = session.get("username")

    # ------------------------------------------------------------------
    # Move processed artwork into the finalised location and update paths
    # ------------------------------------------------------------------
    try:
        if final_dir.exists():
            raise FileExistsError(f"{final_dir} already exists")

        shutil.move(str(processed_dir), str(final_dir))
        uid, _rec = utils.get_record_by_seo_filename(filename)
        if uid:
            utils.update_status(uid, final_dir, "finalised")

        # Marker file indicating finalisation time
        (final_dir / "finalised.txt").write_text(
            datetime.datetime.now().isoformat(), encoding="utf-8"
        )

        # Remove original artwork from input directory if it still exists
        orig_input = utils.UNANALYSED_ROOT / aspect / filename
        try:
            os.remove(orig_input)
        except FileNotFoundError:
            pass

        # Update any stored paths within the listing JSON
        listing_file = final_dir / f"{seo_folder}-listing.json"
        if listing_file.exists():
            # Always allocate a fresh SKU on finalisation
            utils.assign_or_get_sku(listing_file, config.SKU_TRACKER, force=True)
            listing_data = utils.load_json_file_safe(listing_file)
            listing_data.setdefault("locked", False)

            def _swap_path(p: str) -> str:
                return p.replace(str(utils.PROCESSED_ROOT), str(utils.FINALISED_ROOT))

            for key in (
                "main_jpg_path",
                "orig_jpg_path",
                "thumb_jpg_path",
                "processed_folder",
            ):
                if isinstance(listing_data.get(key), str):
                    listing_data[key] = _swap_path(listing_data[key])

            if isinstance(listing_data.get("images"), list):
                listing_data["images"] = [
                    _swap_path(img) if isinstance(img, str) else img
                    for img in listing_data["images"]
                ]

            imgs = [
                p
                for p in final_dir.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ]
            listing_data["images"] = [utils.relative_to_base(p) for p in sorted(imgs)]

            with open(listing_file, "w", encoding="utf-8") as lf:
                json.dump(listing_data, lf, indent=2, ensure_ascii=False)

        log_action("finalise", filename, user, f"finalised to {final_dir}")
        flash("Artwork finalised", "success")
    except Exception as e:  # noqa: BLE001
        log_action(
            "finalise", filename, user, "finalise failed", status="fail", error=str(e)
        )
        flash(f"Failed to finalise artwork: {e}", "danger")

    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/finalised")
def finalised_gallery():
    """Display all finalised artworks in a gallery view."""
    artworks = []
    if utils.FINALISED_ROOT.exists():
        for folder in utils.FINALISED_ROOT.iterdir():
            if not folder.is_dir():
                continue
            listing_file = folder / f"{folder.name}-listing.json"
            if not listing_file.exists():
                continue
            try:
                data = utils.load_json_file_safe(listing_file)
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
            entry["date"] = (
                ts.stat().st_mtime if ts.exists() else listing_file.stat().st_mtime
            )

            main_img = folder / f"{folder.name}.jpg"
            entry["main_image"] = main_img.name if main_img.exists() else None

            artworks.append(entry)
    artworks.sort(key=lambda x: x.get("date", 0), reverse=True)
    return render_template("finalised.html", artworks=artworks, menu=utils.get_menu())


@bp.route("/locked")
def locked_gallery():
    """Show gallery of locked artworks only."""
    locked_items = [
        a for a in utils.list_finalised_artworks_extended() if a.get("locked")
    ]
    return render_template("locked.html", artworks=locked_items, menu=utils.get_menu())


@bp.post("/update-links/<aspect>/<filename>")
def update_links(aspect, filename):
    """Regenerate image URL list from disk for either processed or finalised artwork.

    If the request was sent via AJAX (accepting JSON or using the ``XMLHttpRequest``
    header) the refreshed list of image URLs is returned as JSON rather than
    performing a redirect. This allows the edit page to update the textarea in
    place without losing form state.
    """

    wants_json = (
        "application/json" in request.headers.get("Accept", "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )

    try:
        seo_folder, folder, listing_file, _ = utils.resolve_listing_paths(
            aspect, filename
        )
    except FileNotFoundError:
        msg = "Artwork not found"
        if wants_json:
            return {"success": False, "message": msg, "images": []}, 404
        flash(msg, "danger")
        return redirect(url_for("artwork.artworks"))

    try:
        data = utils.load_json_file_safe(listing_file)
        imgs = [
            p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
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
    folder = utils.FINALISED_ROOT / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    locked = False
    if listing_file.exists():
        try:
            info = utils.load_json_file_safe(listing_file)
            locked = info.get("locked", False)
        except Exception:
            pass
    if locked and request.form.get("confirm") != "DELETE":
        flash("Type DELETE to confirm", "warning")
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )
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
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )
    try:
        target = utils.ARTWORK_VAULT_ROOT / f"LOCKED-{seo}"
        utils.ARTWORK_VAULT_ROOT.mkdir(parents=True, exist_ok=True)
        if target.exists():
            idx = 1
            base = target
            while target.exists():
                target = base.with_name(f"{base.name}_{idx}")
                idx += 1
        shutil.move(str(folder), str(target))
        listing = target / f"{seo}-listing.json"
        utils.update_listing_paths(listing, folder, target)
        with open(listing, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["locked"] = True
        with open(listing, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_action("lock", filename, session.get("username"), "locked artwork")
        flash("Artwork locked", "success")
    except Exception as exc:  # noqa: BLE001
        log_action(
            "lock",
            filename,
            session.get("username"),
            "lock failed",
            status="fail",
            error=str(exc),
        )
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
        target = utils.FINALISED_ROOT / seo
        if target.exists():
            idx = 1
            base = target
            while target.exists():
                target = base.with_name(f"{base.name}_{idx}")
                idx += 1
        shutil.move(str(folder), str(target))
        listing = target / f"{seo}-listing.json"
        utils.update_listing_paths(listing, folder, target)
        data = utils.load_json_file_safe(listing)
        data["locked"] = False
        with open(listing, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_action("lock", filename, session.get("username"), "unlocked artwork")
        flash("Artwork unlocked", "success")
    except Exception as exc:  # noqa: BLE001
        log_action(
            "lock",
            filename,
            session.get("username"),
            "unlock failed",
            status="fail",
            error=str(exc),
        )
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
    """Placeholder endpoint for future Sellbrite integration."""
    flash("Coming soon!", "info")
    return redirect(url_for("artwork.finalised_gallery"))


@bp.post("/analyze-<provider>/<filename>")
def analyze_api(provider: str, filename: str):
    """Analyze an artwork then redirect or return JSON for editing."""

    logger = logging.getLogger(__name__)
    debug = config.DEBUG
    user = session.get("username")
    logger.info("ROUTE START provider=%s file=%s", provider, filename)
    print(f"ROUTE START provider={provider} file={filename}")

    if provider not in {"openai", "google"}:
        logger.error("Invalid provider %s", provider)
        return jsonify({"success": False, "error": "Invalid provider"}), 400

    if provider == "openai" and not current_app.config.get("OPENAI_CONFIGURED"):
        msg = "OpenAI API Key is not configured"
        _write_analysis_status("failed", 100, filename, status="failed", error=msg)
        log_action("analyse-openai", filename, user, "analysis failed", status="fail", error=msg)
        return jsonify({"success": False, "error": msg}), 400
    if provider == "google" and not current_app.config.get("GOOGLE_CONFIGURED"):
        msg = "Google API Key is not configured"
        _write_analysis_status("failed", 100, filename, status="failed", error=msg)
        log_action("analyse-google", filename, user, "analysis failed", status="fail", error=msg)
        return jsonify({"success": False, "error": msg}), 400

    base = Path(filename).stem
    temp_file = next(
        (p for p in config.UNANALYSED_ROOT.rglob(filename) if p.is_file()), None
    )
    log_id = uuid.uuid4().hex
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"

    _write_analysis_status("starting", 0, filename, status="analyzing")

    try:
        if temp_file and temp_file.exists():
            print("Using temporary uploaded file", temp_file)
            qc_path = next(
                (
                    p
                    for p in config.UNANALYSED_ROOT.rglob(f"{base}.qc.json")
                    if p.is_file()
                ),
                None,
            )
            qc = json.load(open(qc_path, "r", encoding="utf-8")) if qc_path else {}
            _write_analysis_status(f"{provider}_call", 20, filename, status="analyzing")
            entry = _run_ai_analysis(temp_file, provider)
            seo_folder = entry["seo_name"]
            listing_json = (
                Path(entry["processed_folder"]) / f"{seo_folder}-listing.json"
            )
            listing = utils.load_json_file_safe(listing_json)
            for suffix in [
                f".{qc.get('extension', 'jpg')}",
                "-thumb.jpg",
                "-analyse.jpg",
                ".qc.json",
            ]:
                src = next(
                    (
                        p
                        for p in config.UNANALYSED_ROOT.rglob(f"{base}{suffix}")
                        if p.is_file()
                    ),
                    None,
                )
                if not src:
                    continue
                key = (
                    "analyse"
                    if suffix == "-analyse.jpg"
                    else (
                        "thumbnail"
                        if suffix == "-thumb.jpg"
                        else "qc_json" if suffix.endswith(".qc.json") else "artwork"
                    )
                )
                dest = Path(entry["processed_folder"]) / config.FILENAME_TEMPLATES[
                    key
                ].format(seo_slug=seo_folder)
                shutil.move(src, dest)
        else:
            print("Resolving processed image for", filename)
            seo_folder, folder, listing_path, _ = utils.resolve_listing_paths(
                "", filename
            )
            img_path = folder / f"{seo_folder}.jpg"
            _write_analysis_status(f"{provider}_call", 20, filename, status="analyzing")
            entry = _run_ai_analysis(img_path, provider)
            seo_folder = entry["seo_name"]
            listing_json = (
                Path(entry["processed_folder"]) / f"{seo_folder}-listing.json"
            )
            listing = utils.load_json_file_safe(listing_json)

        entry = strip_binary(entry)

        with open(log_file, "w", encoding="utf-8") as log:
            log.write(json.dumps(strip_binary(entry), indent=2))

        print("Generating composites for", seo_folder)
        _write_analysis_status("generating", 60, filename, status="analyzing")
        _generate_composites(seo_folder, log_id)
        utils.generate_mockups_for_listing(seo_folder)

        utils.cleanup_unanalysed_folders()

        _write_analysis_status("done", 100, filename, status="complete")
        logger.info("SUCCESS %s", filename)

        edit_info = utils.find_aspect_filename_from_seo_folder(seo_folder)
        edit_url = ""
        if edit_info:
            aspect, seo_file = edit_info
            edit_url = url_for("artwork.edit_listing", aspect=aspect, filename=seo_file)

            # --- ADD THIS BLOCK TO WAIT FOR THE THUMBNAIL ---
            try:
                thumb_filename = config.FILENAME_TEMPLATES["thumbnail"].format(seo_slug=seo_folder)
                thumb_path = config.PROCESSED_ROOT / seo_folder / thumb_filename

                timeout = 5  # seconds
                start_time = time.time()
                while not thumb_path.exists():
                    if time.time() - start_time > timeout:
                        logger.warning(f"Timeout waiting for thumbnail: {thumb_path}")
                        break
                    time.sleep(0.2) # Check every 200ms
            except Exception as e:
                logger.error(f"Error while waiting for thumbnail: {e}")
            # --- END OF NEW BLOCK ---

        # Build response with URL to the edit page. Clients using JavaScript
        # (fetch/XHR) expect JSON and will handle the redirect manually. A
        # normal form POST should receive an HTTP redirect.
        response_payload = {
            "success": True,
            "seo_folder": seo_folder,
            "listing": strip_binary(listing),
            "edit_url": edit_url,
        }

        action = f"analyse-{provider}"
        log_action(action, filename, user, "analysis complete", status="success")
        if (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.accept_mimetypes.best == "application/json"
        ):
            return jsonify(response_payload)

        return redirect(edit_url)

    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        logger.error("Analyze error for %s: %s", filename, exc)
        logger.error(tb)
        print(tb)
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(str(exc) + "\n" + tb)
        msg = exc.args[0] if exc.args else exc
        if isinstance(msg, (bytes, bytearray)):
            masked = f"<{len(msg)} bytes>"
            if debug:
                tb_mask = repr(msg)
                tb = tb.replace(tb_mask, masked)
            msg = masked
        error = str(msg)
        _write_analysis_status("failed", 100, filename, status="failed", error=error)
        if debug:
            error += "\n" + tb
        action = f"analyse-{provider}"
        log_action(
            action,
            filename,
            user,
            "analysis failed",
            status="fail",
            error=error,
        )
        return jsonify({"success": False, "error": error}), 500


# Convenience wrappers for explicit endpoints
@bp.post("/analyze-openai/<filename>")
def analyze_openai(filename: str):
    """Analyze using OpenAI provider."""
    return analyze_api("openai", filename)


@bp.post("/analyze-google/<filename>")
def analyze_google(filename: str):
    """Analyze using Google provider."""
    return analyze_api("google", filename)


@bp.post("/delete/<filename>")
def delete_artwork(filename: str):
    """Delete all files for an artwork."""
    logger = logging.getLogger(__name__)
    base = Path(filename).stem
    try:
        deleted = False
        for p in config.UNANALYSED_ROOT.rglob(f"{base}*"):
            p.unlink(missing_ok=True)
            deleted = True
        try:
            seo_folder, folder, listing_path, _ = utils.resolve_listing_paths(
                "", filename
            )
            with open(listing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            aspect = data.get("aspect_ratio", "")
            for target in [
                utils.PROCESSED_ROOT / seo_folder,
                utils.FINALISED_ROOT / seo_folder,
                utils.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}",
            ]:
                shutil.rmtree(target, ignore_errors=True)
            if aspect:
                try:
                    os.remove(utils.UNANALYSED_ROOT / aspect / filename)
                except Exception:
                    pass
            deleted = True
        except FileNotFoundError:
            pass
        if deleted:
            utils.cleanup_unanalysed_folders()
            logger.info("Deleted artwork %s", filename)
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Artwork not found"}), 404
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        logger.error("Delete error for %s: %s", filename, exc)
        logger.error(tb)
        debug = config.DEBUG
        error = str(exc)
        if debug:
            error += "\n" + tb
        return jsonify({"success": False, "error": error}), 500


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


def _process_upload_file(file_storage, dest_folder):
    """Return result dict for a single uploaded file.

    This helper performs validation, thumbnail generation and JSON QC file
    creation. Any IO or processing error is caught and returned in the
    ``error`` field instead of raising so the caller can continue processing
    remaining files.
    """
    result = {"original": file_storage.filename, "success": False, "error": ""}
    filename = file_storage.filename
    if not filename:
        result["error"] = "No filename"
        return result
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_EXTENSIONS:
        result["error"] = "Invalid file type"
        return result
    try:
        data = file_storage.read()
        if len(data) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            result["error"] = "File too large"
            return result
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except Exception as exc:  # noqa: BLE001 - PIL/IO errors
        result["error"] = "Corrupted image"
        logging.getLogger(__name__).error("Image validation failed: %s", exc)
        return result

    safe = aa.slugify(Path(filename).stem)
    unique = uuid.uuid4().hex[:8]
    uid = uuid.uuid4().hex
    base = f"{safe}-{unique}"
    dest_folder.mkdir(parents=True, exist_ok=True)
    orig_path = dest_folder / f"{base}.{ext}"
    try:
        with open(orig_path, "wb") as f:
            f.write(data)
    except Exception as exc:  # noqa: BLE001 - disk IO errors
        logging.getLogger(__name__).error("Failed writing %s: %s", orig_path, exc)
        result["error"] = "Failed saving file"
        return result

    try:
        with Image.open(orig_path) as img:
            width, height = img.size
            thumb_path = dest_folder / f"{base}-thumb.jpg"
            thumb = img.copy()
            thumb.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
            thumb.save(thumb_path, "JPEG", quality=80)

        analyse_path = dest_folder / f"{base}-analyse.jpg"
        with Image.open(orig_path) as img:
            w, h = img.size
            scale = config.ANALYSE_MAX_DIM / max(w, h)
            if scale < 1.0:
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            img = img.convert("RGB")

            q = 85
            while True:
                img.save(analyse_path, "JPEG", quality=q, optimize=True)
                if (
                    analyse_path.stat().st_size <= config.ANALYSE_MAX_MB * 1024 * 1024
                    or q <= 60
                ):
                    break
                q -= 5
    except Exception as exc:  # noqa: BLE001 - image processing errors
        logging.getLogger(__name__).error("Thumbnail/preview creation failed: %s", exc)
        result["error"] = "Image processing failed"
        return result

    aspect = aa.get_aspect_ratio(orig_path)

    qc_data = {
        "original_filename": filename,
        "extension": ext,
        "image_shape": [width, height],
        "filesize_bytes": len(data),
        "aspect_ratio": aspect,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    qc_path = dest_folder / f"{base}.qc.json"
    try:
        qc_path.write_text(json.dumps(qc_data, indent=2))
    except Exception as exc:  # noqa: BLE001 - disk IO errors
        logging.getLogger(__name__).error("Failed writing QC file %s: %s", qc_path, exc)
        result["error"] = "Failed writing QC file"
        return result

    utils.register_new_artwork(
        uid,
        f"{base}.{ext}",
        dest_folder,
        [orig_path.name, thumb_path.name, analyse_path.name, qc_path.name],
        "unanalysed",
        base,
    )

    result.update({"success": True, "base": base, "aspect": aspect, "uid": uid})
    return result
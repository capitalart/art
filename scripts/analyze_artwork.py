#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""ART Narrator | analyze_artwork.py
===============================================================
Professional, production-ready, fully sectioned and sub-sectioned
Robbie Mode™ script for analyzing artworks with OpenAI.
"""
# This file now references all path, directory, and filename variables strictly from config.py. No local or hardcoded path constants remain.

# ============================== [ Imports ] ===============================
import argparse
import datetime as _dt
import json
import logging
import os
import random
import re
import shutil
import sys
import traceback
from pathlib import Path
import contextlib
import fcntl

# Ensure project root is on sys.path for ``config`` import when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
import base64
from dotenv import load_dotenv
from openai import OpenAI
from config import (
    BASE_DIR,
    UNANALYSED_ROOT,
    MOCKUPS_INPUT_DIR as MOCKUPS_DIR,
    ONBOARDING_PATH,
    PROCESSED_ROOT,
    LOGS_DIR,
    SKU_TRACKER,
    OUTPUT_JSON,
)
import config
from utils.logger_utils import sanitize_blob_data
# UPDATED IMPORT: We need the new assembler function
from routes.utils import assemble_gdws_description

Image.MAX_IMAGE_PIXELS = None

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in environment")
client = OpenAI(
    api_key=API_KEY,
    project=config.OPENAI_PROJECT_ID,
)


# ======================= [ 1. CONFIGURATION & PATHS ] =======================

MOCKUPS_PER_LISTING = 9  # 1 thumb + 9 mockups

# --- [ 1.3: Etsy Colour Palette ]
ETSY_COLOURS = {
    'Beige': (222, 202, 173), 'Black': (24, 23, 22), 'Blue': (42, 80, 166), 'Bronze': (140, 120, 83),
    'Brown': (110, 72, 42), 'Clear': (240, 240, 240), 'Copper': (181, 101, 29), 'Gold': (236, 180, 63),
    'Grey': (160, 160, 160), 'Green': (67, 127, 66), 'Orange': (237, 129, 40), 'Pink': (229, 100, 156),
    'Purple': (113, 74, 151), 'Rainbow': (170, 92, 152), 'Red': (181, 32, 42), 'Rose gold': (212, 150, 146),
    'Silver': (170, 174, 179), 'White': (242, 242, 243), 'Yellow': (242, 207, 46)
}


# ====================== [ 2. LOGGING CONFIGURATION ] ========================
START_TS = _dt.datetime.now(_dt.timezone.utc).strftime("%a-%d-%b-%Y-%I-%M-%p").upper()
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / f"analyze-artwork-{START_TS}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")]
)
logger = logging.getLogger("analyze_artwork")

# Additional logger for OpenAI API call details
openai_log_path = LOGS_DIR / (
    "analyze-openai-calls-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d") + ".log"
)
openai_logger = logging.getLogger("openai_analysis")
if not openai_logger.handlers:
    openai_handler = logging.FileHandler(openai_log_path, encoding="utf-8")
    openai_handler.setFormatter(logging.Formatter("%(message)s"))
    openai_logger.addHandler(openai_handler)
    openai_logger.setLevel(logging.INFO)


# User/session information for logging
USER_ID = os.getenv("USER_ID", "anonymous")


class _Tee:
    """Simple tee to duplicate stdout/stderr to the log file."""
    def __init__(self, original, log_file):
        self._original = original
        self._log = log_file

    def write(self, data):
        self._original.write(data)
        self._original.flush()
        self._log.write(data)
        self._log.flush()

    def flush(self):
        self._original.flush()
        self._log.flush()


# ======================== [ 3. UTILITY FUNCTIONS ] ==========================

def log_process_time(process_name, duration_seconds, artwork_filename):
    """Logs the duration of a specific process to a dedicated log file."""
    log_file = config.LOGS_DIR / "timer_log.log"
    timestamp = _dt.datetime.now(_dt.timezone.utc).isoformat()
    log_message = f"{timestamp} - PROCESS: {process_name}, DURATION: {duration_seconds:.2f}s, ARTWORK: {artwork_filename}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_message)

def get_aspect_ratio(image_path: Path) -> str:
    """Return closest aspect ratio label for given image."""
    with Image.open(image_path) as img:
        w, h = img.size
    aspect_map = [
        ("1x1", 1 / 1), ("2x3", 2 / 3), ("3x2", 3 / 2), ("3x4", 3 / 4), ("4x3", 4 / 3),
        ("4x5", 4 / 5), ("5x4", 5 / 4), ("5x7", 5 / 7), ("7x5", 7 / 5), ("9x16", 9 / 16),
        ("16x9", 16 / 9), ("A-Series-Horizontal", 1.414 / 1), ("A-Series-Vertical", 1 / 1.414),
    ]
    ar = round(w / h, 4)
    best = min(aspect_map, key=lambda tup: abs(ar - tup[1]))
    logger.info(f"Aspect ratio for {image_path.name}: {best[0]}")
    return best[0]


def pick_mockups(aspect: str, max_count: int = 8) -> list:
    """Select mockup images for the given aspect with graceful fallbacks."""
    primary_dir = MOCKUPS_DIR / f"{aspect}-categorised"
    fallback_dir = MOCKUPS_DIR / aspect

    if primary_dir.exists():
        use_dir = primary_dir
    elif fallback_dir.exists():
        logger.warning(f"Categorised mockup folder missing for {aspect}; using fallback")
        use_dir = fallback_dir
    else:
        logger.error(f"No mockup folder found for aspect {aspect}")
        return []

    candidates = [f for f in use_dir.glob("**/*") if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    random.shuffle(candidates)
    selection = [str(f.resolve()) for f in candidates[:max_count]]
    logger.info(f"Selected {len(selection)} mockups from {use_dir.name} for {aspect}")
    return selection

def read_onboarding_prompt() -> str:
    return Path(ONBOARDING_PATH).read_text(encoding="utf-8")


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\- ]+", "", text)
    text = text.strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()


# Use the central SKU assigner for all SKU operations
from utils.sku_assigner import get_next_sku


def sync_filename_with_sku(seo_filename: str, sku: str) -> str:
    """Update the SKU portion of an SEO filename."""
    if not seo_filename or not sku:
        return seo_filename
    return re.sub(r"RJC-[A-Za-z0-9-]+(?=\.jpg$)", sku, seo_filename)


def parse_text_fallback(text: str) -> dict:
    """Extract key fields from a non-JSON AI response."""
    data = {"fallback_text": text}

    tag_match = re.search(r"Tags:\s*(.*)", text, re.IGNORECASE)
    if tag_match:
        data["tags"] = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]
    else:
        data["tags"] = []

    mat_match = re.search(r"Materials:\s*(.*)", text, re.IGNORECASE)
    if mat_match:
        data["materials"] = [m.strip() for m in mat_match.group(1).split(",") if m.strip()]
    else:
        data["materials"] = []

    title_match = re.search(r"(?:Title|Artwork Title|Listing Title)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if title_match:
        data["title"] = title_match.group(1).strip()

    seo_match = re.search(r"(?:seo[_ ]filename|seo file|filename)\s*[:\-]\s*(.+\.jpe?g)", text, re.IGNORECASE)
    if seo_match:
        data["seo_filename"] = seo_match.group(1).strip()

    prim_match = re.search(r"Primary Colour\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if prim_match:
        data["primary_colour"] = prim_match.group(1).strip()
    sec_match = re.search(r"Secondary Colour\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if sec_match:
        data["secondary_colour"] = sec_match.group(1).strip()

    desc_match = re.search(r"(?:Description|Artwork Description)\s*[:\-]\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if desc_match:
        data["description"] = desc_match.group(1).strip()

    return data


def extract_seo_filename_from_text(text: str, fallback_base: str) -> tuple[str, str]:
    """Attempt to extract an SEO filename from plain text."""
    patterns = [r"^\s*(?:SEO Filename|SEO_FILENAME|SEO FILE|FILENAME)\s*[:\-]\s*(.+)$"]
    for line in text.splitlines():
        for pat in patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                base = re.sub(r"\.jpe?g$", "", m.group(1).strip(), flags=re.IGNORECASE)
                return slugify(base), "regex"

    m = re.search(r"([\w\-]+\.jpe?g)", text, re.IGNORECASE)
    if m:
        base = os.path.splitext(m.group(1))[0]
        return slugify(base), "jpg"

    return slugify(fallback_base), "fallback"


def extract_seo_filename(ai_listing: dict | None, raw_text: str, fallback_base: str) -> tuple[str, bool, str]:
    """Return SEO slug, whether fallback was used, and extraction method."""
    if ai_listing and isinstance(ai_listing, dict) and ai_listing.get("seo_filename"):
        name = os.path.splitext(str(ai_listing["seo_filename"]))[0]
        return slugify(name), False, "json"

    if ai_listing and isinstance(ai_listing, dict) and ai_listing.get("title"):
        slug = slugify(str(ai_listing["title"]))
        return slug, True, "title"

    slug, method = extract_seo_filename_from_text(raw_text, fallback_base)
    return slug, True, method


def make_preview_2000px_max(src_jpg: Path, dest_jpg: Path, target_long_edge: int = 2000, target_kb: int = 700, min_quality: int = 60) -> None:
    with Image.open(src_jpg) as im:
        w, h = im.size
        scale = target_long_edge / max(w, h)
        if scale < 1.0:
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        else:
            im = im.copy()

        q = 92
        for _ in range(12):
            im.save(dest_jpg, "JPEG", quality=q, optimize=True)
            kb = os.path.getsize(dest_jpg) / 1024
            if kb <= target_kb or q <= min_quality:
                break
            q -= 7
    logger.info(f"Saved preview {dest_jpg.name} ({kb:.1f} KB, Q={q})")


def save_finalised_artwork(
    original_path: Path,
    seo_name: str,
    output_base_dir: Path,
    verbose: bool = False,
):
    target_folder = Path(output_base_dir) / seo_name
    target_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created/using folder {target_folder}")

    orig_filename = original_path.name
    seo_main_jpg = target_folder / f"{seo_name}.jpg"
    orig_jpg = target_folder / f"original-{orig_filename}"
    thumb_jpg = target_folder / f"{seo_name}-THUMB.jpg"

    shutil.move(str(original_path), orig_jpg)
    shutil.copy2(orig_jpg, seo_main_jpg)
    logger.info(f"Moved original file for {seo_name}")

    make_preview_2000px_max(seo_main_jpg, thumb_jpg, 2000, 700, 60)
    logger.info(f"Finalised files saved to {target_folder}")

    return str(seo_main_jpg), str(orig_jpg), str(thumb_jpg), str(target_folder)


def add_to_pending_mockups_queue(image_path: str, queue_file: str) -> None:
    try:
        if os.path.exists(queue_file):
            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            if not isinstance(queue, list):
                queue = []
        else:
            queue = []
    except Exception:
        queue = []
    if image_path not in queue:
        queue.append(image_path)
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
    logger.info(f"Added to pending mockups queue: {image_path}")


def make_optimized_image_for_ai(
    src_path: Path,
    out_dir: Path,
    max_edge: int = 2400,
    target_bytes: int = 1024 * 1024,
    start_quality: int = 85,
    min_quality: int = 60,
    verbose: bool = False,
) -> Path:
    """Return path to optimized JPEG for AI analysis."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if verbose:
        print("- Optimizing image for AI input...", end="", flush=True)
    out_path = out_dir / f"{src_path.stem}-OPTIMIZED.jpg"
    try:
        if out_path.exists():
            out_path.unlink()
        with Image.open(src_path) as im:
            w, h = im.size
            scale = max_edge / max(w, h)
            if scale < 1.0:
                im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            else:
                im = im.copy()
            im = im.convert("RGB")

            q = start_quality
            while True:
                im.save(out_path, "JPEG", quality=q, optimize=True)
                if out_path.stat().st_size <= target_bytes or q <= min_quality:
                    break
                q -= 5

            if out_path.stat().st_size > target_bytes:
                logger.warning(
                    f"{out_path.name} exceeds {target_bytes} bytes at Q={q}"
                )

        logger.info(
            f"Optimized image saved for AI: {out_path.name} "
            f"({im.width}x{im.height}, {out_path.stat().st_size} bytes, Q={q})"
        )
        if verbose:
            size_mb = out_path.stat().st_size / 1024 / 1024
            print(
                f" done ({out_path.name}, {size_mb:.1f}MB)"
            )
    except Exception as e:
        logger.error(f"Failed to create optimized image for {src_path}: {e}")
        logger.error(traceback.format_exc())
        raise
    return out_path


# ===================== [ 4. COLOUR DETECTION & MAPPING ] ====================

def closest_colour(rgb_tuple):
    min_dist = float('inf')
    best_colour = None
    for name, rgb in ETSY_COLOURS.items():
        dist = sum((rgb[i] - rgb_tuple[i]) ** 2 for i in range(3)) ** 0.5
        if dist < min_dist:
            min_dist = dist
            best_colour = name
    return best_colour


def get_dominant_colours(img_path: Path, n: int = 2):
    from sklearn.cluster import KMeans
    import numpy as np

    try:
        with Image.open(img_path) as img:
            img = img.convert("RGB")
            w, h = img.size
            crop = img.crop((max(0, w // 2 - 25), max(0, h // 2 - 25), min(w, w // 2 + 25), min(h, h // 2 + 25)))
            crop_dir = LOGS_DIR / "crops"
            crop_dir.mkdir(exist_ok=True)
            crop_path = crop_dir / f"{img_path.stem}-crop.jpg"
            crop.save(crop_path, "JPEG", quality=80)
            logger.debug(f"Saved crop for colour check: {crop_path}")
            img = img.resize((100, 100))
            arr = np.asarray(img).reshape(-1, 3)

        k = max(3, n + 1)
        kmeans = KMeans(n_clusters=k, n_init='auto' if hasattr(KMeans, 'n_init') else 10)
        labels = kmeans.fit_predict(arr)
        counts = np.bincount(labels)
        sorted_idx = counts.argsort()[::-1]
        seen = set()
        colours = []
        for i in sorted_idx:
            rgb = tuple(int(c) for c in kmeans.cluster_centers_[i])
            name = closest_colour(rgb)
            if name not in seen:
                seen.add(name)
                colours.append(name)
            if len(colours) >= n:
                break
        if len(colours) < 2:
            colours = (colours + ["White", "Black"])[:2]
    except Exception as e:
        logger.error(f"Colour detection failed for {img_path}: {e}")
        logger.error(traceback.format_exc())
        colours = ["White", "Black"]

    logger.info(f"Colours for {img_path.name}: {colours}")
    return colours


# ========================= [ 5. OPENAI HANDLER ] ===========================

def generate_ai_listing(
    provider: str,
    system_prompt: str,
    image_path: Path,
    aspect: str,
    assigned_sku: str,
    feedback: str | None = None,
    verbose: bool = False,
) -> tuple[dict | None, bool, str, str, str]:
    """Call the selected AI provider and return listing data."""
    if provider == "google":
        raise NotImplementedError("Google provider logic has been moved to a separate script.")

    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
    except Exception as e:
        logger.error("Failed to read image for OpenAI: %s", e)
        return None, False, "", "filesystem_error", str(e)

    encoded = base64.b64encode(img_bytes).decode("utf-8")
    prompt = (
        system_prompt.strip()
        + f"\n\nThe SKU for this artwork is {assigned_sku}. "
        + "NEVER invent a SKU, ALWAYS use the provided assigned_sku for the 'sku' and filename fields."
    )
    user_content = [
        {"type": "text", "text": f"Artwork filename: {image_path.name}\nAspect ratio: {aspect}\nDescribe and analyze the artwork visually, then generate the listing as per the instructions above."},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
    ]
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": user_content}]
    if feedback:
        messages.append({"role": "user", "content": feedback})
    model = config.OPENAI_MODEL
    if verbose:
        print(f"- Sending to OpenAI API (model={model}, temp=0.92, timeout=60s)...")

    max_retries = 3
    attempt = 1
    last_error = ""
    while attempt <= max_retries:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2100,
                temperature=0.92,
                timeout=60,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()
            safe_msg = sanitize_blob_data(messages)
            openai_logger.info(json.dumps({"provider": "openai", "messages": safe_msg, "response": content[:500]}))
            if verbose:
                print(f"- OpenAI response received (length {len(content)} chars). Parsing...")
            
            try:
                return json.loads(content), True, content, "ok", ""
            except json.JSONDecodeError:
                fallback = parse_text_fallback(content)
                return fallback, False, content, "fallback", "OpenAI response not valid JSON"
        except Exception as exc:
            last_error = str(exc)
            logger.error("OpenAI API error (attempt %s/%s): %s", attempt, max_retries, exc)
            logger.error(traceback.format_exc())
            if verbose:
                print(f"- OpenAI API error: {exc}")
            attempt += 1
            if attempt <= max_retries:
                logger.info("Retrying OpenAI call (attempt %s)...", attempt)
                import time
                time.sleep(2)

    logger.error("OpenAI API failed after %s attempts: %s", max_retries, last_error)
    if verbose:
        print(f"- OpenAI API failed after {max_retries} attempts: {last_error}")
    return (
        {
            "fallback_text": "OpenAI API failed, no listing generated.",
            "error": last_error,
            "model_used": model,
            "attempts": max_retries,
            "image": str(image_path),
            "aspect": aspect,
        },
        False,
        "",
        "api_error",
        last_error,
    )

# ========================= [ 6. MAIN ANALYSIS LOGIC ] =========================

def analyze_single(
    image_path: Path,
    system_prompt: str,
    feedback_text: str | None,
    statuses: list,
    idx: int | None = None,
    total: int | None = None,
    verbose: bool = False,
    provider: str = "openai",
):
    """
    Analyze and process a single image path.
    Handles AI optimization, API calls, result parsing, and saving of outputs.
    """

    # --------------------------------------------------------------------------
    # [6.1] DEFINE TEMP DIRECTORY
    # --------------------------------------------------------------------------
    TEMP_DIR = UNANALYSED_ROOT / "temp"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # [6.2] INITIALIZE STATUS & LOGGING
    # --------------------------------------------------------------------------
    status = {"file": str(image_path), "success": False, "error": "", "provider": provider}
    if verbose:
        msg = f"[{idx}/{total}] " if idx is not None and total is not None else ""
        print(f"{msg}Processing image with {provider}: {image_path}")

    try:
        # ----------------------------------------------------------------------
        # [6.3] VALIDATE IMAGE
        # ----------------------------------------------------------------------
        if not image_path.is_file():
            raise FileNotFoundError(str(image_path))

        # ----------------------------------------------------------------------
        # [6.4] PREPARE DATA FOR AI CALL
        # ----------------------------------------------------------------------
        aspect = get_aspect_ratio(image_path)
        mockups = pick_mockups(aspect, MOCKUPS_PER_LISTING)
        generic_text = assemble_gdws_description(aspect)
        fallback_base = image_path.stem
        assigned_sku = get_next_sku(SKU_TRACKER)

        # ----------------------------------------------------------------------
        # [6.5] OPTIMIZE IMAGE FOR AI
        # ----------------------------------------------------------------------
        opt_img = make_optimized_image_for_ai(image_path, TEMP_DIR, verbose=verbose)
        size_bytes = Path(opt_img).stat().st_size
        with Image.open(opt_img) as _im:
            dimensions = f"{_im.width}x{_im.height}"

        # Prepare log entries
        log_entry = {
            "file": str(image_path),
            "user_id": USER_ID,
            "opt_image": str(opt_img),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1024 / 1024, 2),
            "dimensions": dimensions,
            "time_sent": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "provider": provider,
        }
        start_ts = _dt.datetime.now(_dt.timezone.utc)
        log_process_time("Analysis Start", 0, image_path.name)

        analysis_entry = {
            "original_file": str(image_path),
            "user_id": USER_ID,
            "optimized_file": str(opt_img),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1024 / 1024, 2),
            "dimensions": dimensions,
            "time_sent": start_ts.isoformat(),
            "provider": provider,
        }

        # ----------------------------------------------------------------------
        # [6.6] CALL AI PROVIDER (no automatic fallback)
        # ----------------------------------------------------------------------
        ai_listing, was_json, raw_response, err_type, err_msg = generate_ai_listing(
            provider, system_prompt, opt_img, aspect, assigned_sku, feedback_text, verbose=verbose,
        )
        log_process_time("AI API Call", (_dt.datetime.now(_dt.timezone.utc) - start_ts).total_seconds(), image_path.name)

        # ----------------------------------------------------------------------
        # [6.7] ERROR HANDLING (LOGGING, FAIL EARLY)
        # ----------------------------------------------------------------------
        if not was_json:
            log_entry.update({"status": "fail", "error": err_msg, "error_type": err_type})
            end_ts = _dt.datetime.now(_dt.timezone.utc)
            log_entry.update({
                "time_responded": end_ts.isoformat(),
                "duration_sec": (end_ts - start_ts).total_seconds(),
            })
            safe_entry = sanitize_blob_data(log_entry)
            openai_logger.info(json.dumps(safe_entry))
            analysis_entry.update({
                "time_responded": end_ts.isoformat(),
                "duration_sec": (end_ts - start_ts).total_seconds(),
                "status": "fail",
                "api_response": f"{err_type}: {err_msg}",
            })
            status["error"] = f"{err_type}: {err_msg}"
            raise RuntimeError(err_msg)

        log_entry.update({"status": "success"})
        call_end_ts = _dt.datetime.now(_dt.timezone.utc)
        analysis_entry.update({
            "time_responded": call_end_ts.isoformat(),
            "duration_sec": (call_end_ts - start_ts).total_seconds(),
            "status": "success",
            "api_response": "ok",
        })

        # ----------------------------------------------------------------------
        # [6.8] PARSE AND SAVE FINAL OUTPUTS
        # ----------------------------------------------------------------------
        seo_name, used_fallback_naming, naming_method = extract_seo_filename(ai_listing, raw_response, fallback_base)
        log_entry.update({
            "used_fallback_naming": used_fallback_naming,
            "naming_method": naming_method,
        })
        analysis_entry.update({
            "used_fallback_naming": used_fallback_naming,
            "naming_method": naming_method,
        })

        if verbose:
            print("- Parsed JSON OK, writing outputs...")

        main_jpg, orig_jpg, thumb_jpg, folder_path = save_finalised_artwork(
            image_path, seo_name, PROCESSED_ROOT, verbose=verbose,
        )
        log_process_time("File Processing", (_dt.datetime.now(_dt.timezone.utc) - start_ts).total_seconds(), image_path.name)
        
        primary_colour, secondary_colour = get_dominant_colours(Path(main_jpg), 2)

        end_ts = _dt.datetime.now(_dt.timezone.utc)
        log_entry.update({
            "time_responded": end_ts.isoformat(),
            "duration_sec": (end_ts - start_ts).total_seconds(),
            "seo_filename": f"{seo_name}.jpg",
            "processed_folder": str(folder_path),
        })
        safe_entry = sanitize_blob_data(log_entry)
        openai_logger.info(json.dumps(safe_entry))

        # Description and tags/materials filling
        desc = ai_listing.get("description", "") if isinstance(ai_listing, dict) else ""
        if desc:
            if generic_text and not desc.endswith(generic_text.strip()):
                desc = desc.rstrip() + "\n\n" + generic_text.strip()
        else:
            desc = generic_text.strip()
            
        if isinstance(ai_listing, dict):
            ai_listing["description"] = desc

        tags = ai_listing.get("tags", []) if isinstance(ai_listing, dict) else []
        materials = ai_listing.get("materials", []) if isinstance(ai_listing, dict) else []
        if not tags:
            logger.warning(f"No tags extracted for {image_path.name}")
        if not materials:
            logger.warning(f"No materials extracted for {image_path.name}")

        # ----------------------------------------------------------------------
        # [6.9] ARTWORK ENTRY & HISTORY MANAGEMENT
        # ----------------------------------------------------------------------
        per_artwork_json = Path(folder_path) / f"{seo_name}-listing.json"
        existing_sku = None
        analysis_history = []
        if per_artwork_json.exists():
            try:
                with open(per_artwork_json, "r", encoding="utf-8") as pf:
                    prev = json.load(pf)
                existing_sku = prev.get("sku")
                if existing_sku:
                    logger.info(f"Preserving existing SKU {existing_sku} for {seo_name}")
                prev_ai = prev.get("openai_analysis")
                if isinstance(prev_ai, list):
                    analysis_history = prev_ai
                elif prev_ai:
                    analysis_history = [prev_ai]
            except Exception:
                logger.warning(f"Could not read existing SKU from {per_artwork_json}")

        if not existing_sku:
            existing_sku = assigned_sku
            logger.info(f"Using newly assigned SKU {existing_sku} for {seo_name}")

        if isinstance(ai_listing, dict):
            ai_listing["sku"] = existing_sku
            if ai_listing.get("seo_filename"):
                ai_listing["seo_filename"] = sync_filename_with_sku(str(ai_listing["seo_filename"]), existing_sku)

        artwork_entry = {
            "filename": image_path.name,
            "aspect_ratio": aspect,
            "mockups": mockups,
            "generic_text": generic_text,
            "ai_listing": ai_listing,
            "seo_name": seo_name,
            "used_fallback_naming": used_fallback_naming,
            "main_jpg_path": main_jpg,
            "orig_jpg_path": orig_jpg,
            "thumb_jpg_path": thumb_jpg,
            "processed_folder": str(folder_path),
            "primary_colour": primary_colour,
            "secondary_colour": secondary_colour,
            "tags": tags,
            "materials": materials,
            "sku": existing_sku,
        }
        analysis_history.insert(0, analysis_entry)
        artwork_entry["openai_analysis"] = (
            analysis_history if len(analysis_history) > 1 else analysis_history[0]
        )
        with open(per_artwork_json, "w", encoding="utf-8") as af:
            json.dump(artwork_entry, af, indent=2, ensure_ascii=False)
        logger.info(f"Wrote listing JSON to {per_artwork_json}")
        if verbose:
            print(f"- Main image: {main_jpg}")
            print(f"- Thumb: {thumb_jpg}")
            print(f"- Listing JSON: {per_artwork_json}")

        # Add to pending mockups queue
        queue_file = PROCESSED_ROOT / "pending_mockups.json"
        add_to_pending_mockups_queue(main_jpg, str(queue_file))

        status["success"] = True
        logger.info(f"Completed analysis for {image_path.name}")
        return artwork_entry

    except Exception as e:
        status["error"] = str(e)
        logger.error(f"Failed processing {image_path}: {e}")
        logger.error(traceback.format_exc())
        if verbose:
            print(f"- Error: {e}")
        raise

    finally:
        with contextlib.suppress(Exception):
            if 'opt_img' in locals() and Path(opt_img).exists():
                Path(opt_img).unlink()
        statuses.append(status)
        if verbose:
            print("[OK]" if status["success"] else "[FAIL]")


# ============================= [ 7. MAIN ENTRY ] ==============================

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze artwork(s) with AI providers")
    parser.add_argument("image", nargs="?", help="Single image path to process")
    parser.add_argument("--feedback", help="Optional feedback text file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose progress output")
    parser.add_argument(
        "--provider",
        choices=["openai"],
        default="openai",
        help="AI provider to use (only 'openai' is supported)",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit result JSON to stdout for subprocess integration",
    )
    return parser.parse_args()


def main() -> None:
    # --------------------------------------------------------------------------
    # [7.1] PARSE ARGS AND PREP TEMP DIR
    # --------------------------------------------------------------------------
    args = parse_args()
    provider = args.provider
    json_output = args.json_output
    
    if not json_output:
        _log_fp = open(LOG_FILE, "a", encoding="utf-8")
        sys.stdout = _Tee(sys.stdout, _log_fp)
        sys.stderr = _Tee(sys.stderr, _log_fp)
        logger.info("=== ART Narrator: OpenAI Analyzer Started (Interactive Mode) ===")
        print(f"\n===== DreamArtMachine Lite: {provider.capitalize()} Analyzer =====\n")
    else:
        logger.info("=== ART Narrator: OpenAI Analyzer Started (JSON Output Mode) ===")


    TEMP_DIR = UNANALYSED_ROOT / "temp"
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # [7.2] LOAD SYSTEM PROMPT
    # --------------------------------------------------------------------------
    try:
        system_prompt = read_onboarding_prompt()
    except Exception as e:
        logger.error(f"Could not read onboarding prompt: {e}")
        logger.error(traceback.format_exc())
        if not json_output:
            print(f"Error: Could not read onboarding prompt. See log at {LOG_FILE}")
        sys.exit(1)

    # --------------------------------------------------------------------------
    # [7.3] HANDLE VERBOSE/FEEDBACK
    # --------------------------------------------------------------------------
    env_verbose = os.getenv("VERBOSE") == "1"
    verbose = args.verbose or env_verbose
    if verbose and not json_output:
        print("Verbose mode enabled\n")
    feedback_text = None
    if args.feedback:
        try:
            feedback_text = Path(args.feedback).read_text(encoding="utf-8")
            logger.info(f"Loaded feedback from {args.feedback}")
        except Exception as e:
            logger.error(f"Failed to read feedback file {args.feedback}: {e}")
            logger.error(traceback.format_exc())

    single_path = Path(args.image) if args.image else None

    results = []
    statuses: list = []

    # --------------------------------------------------------------------------
    # [7.4] MAIN PROCESSING LOGIC (SINGLE OR BATCH)
    # --------------------------------------------------------------------------
    if single_path:
        logger.info(f"Single-image mode: {single_path}")
        try:
            entry = analyze_single(
                single_path,
                system_prompt,
                feedback_text,
                statuses,
                1,
                1,
                verbose,
                provider,
            )
            if json_output:
                original_stdout = sys.stdout._original if isinstance(sys.stdout, _Tee) else sys.stdout
                original_stdout.write(json.dumps(entry, indent=2))
                sys.exit(0)
            if entry:
                results.append(entry)
        except Exception as e:  # noqa: BLE001
            if json_output:
                error_payload = {"success": False, "error": str(e), "traceback": traceback.format_exc()}
                original_stderr = sys.stderr._original if isinstance(sys.stderr, _Tee) else sys.stderr
                original_stderr.write(json.dumps(error_payload, indent=2))
                sys.exit(1)
            raise
    else:
        all_images = [f for f in UNANALYSED_ROOT.rglob("*.jpg") if f.is_file()]
        total = len(all_images)
        logger.info(f"Batch mode: {total} images found")
        for idx, img_path in enumerate(sorted(all_images), 1):
            if verbose:
                print(f"[{idx}/{total}] Processing image with {provider}: {img_path.relative_to(UNANALYSED_ROOT)}")
            entry = analyze_single(img_path, system_prompt, feedback_text, statuses, idx, total, verbose, provider)
            if entry:
                results.append(entry)

    # --------------------------------------------------------------------------
    # [7.5] WRITE MASTER OUTPUT
    # --------------------------------------------------------------------------
    if results:
        # NOTE: This writes a master list for batch runs, may not be needed
        # for single-file runs via the web UI.
        OUTPUT_JSON.parent.mkdir(exist_ok=True)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as out_f:
            json.dump(results, out_f, indent=2, ensure_ascii=False)
        logger.info(f"Wrote master JSON to {OUTPUT_JSON}")

    # --------------------------------------------------------------------------
    # [7.6] SUMMARY OUTPUT
    # --------------------------------------------------------------------------
    success_count = len([s for s in statuses if s["success"]])
    fail_count = len(statuses) - success_count
    logger.info(f"Analysis complete. Success: {success_count}, Failures: {fail_count}")

    if not json_output:
        if verbose:
            print("\n=== SUMMARY ===")
            print(f"Success: {success_count}   Failed: {fail_count}")
            print(f"See logs at: {LOG_FILE}")
            print(f"Processed output folder: {PROCESSED_ROOT}\n")
        else:
            print(f"\nListings processed! See logs at: {LOG_FILE}")
            if fail_count:
                print(f"{fail_count} file(s) failed. Check the log for details.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        is_json_output = "--json-output" in sys.argv
        if is_json_output:
            error_payload = {"success": False, "error": str(e), "traceback": traceback.format_exc()}
            original_stderr = sys.stderr._original if isinstance(sys.stderr, _Tee) else sys.stderr
            original_stderr.write(json.dumps(error_payload, indent=2))
        else:
            print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        sys.exit(1)
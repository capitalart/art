#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DreamArtMachine Lite | analyze_artwork_google.py
===============================================================
Dedicated script for analyzing artworks with Google's Gemini Pro Vision.
This script is designed to be called via subprocess.

- Receives a single image path as a command-line argument.
- Prints the final JSON analysis to stdout on success.
- Prints a JSON error object to stderr on failure.
"""

# ============================== [ Imports ] ===============================
import argparse
import datetime as _dt
import json
import logging
import os
import re
import sys
import traceback
from pathlib import Path

# Ensure project root is on sys.path for `config` import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv

import config
from config import (
    LOGS_DIR,
    ONBOARDING_PATH,
    SKU_TRACKER,
    UNANALYSED_ROOT,
)
from utils.logger_utils import sanitize_blob_data
from utils.sku_assigner import peek_next_sku

Image.MAX_IMAGE_PIXELS = None
load_dotenv()

# ====================== [ 1. Configuration & Setup ] ========================

# Configure Google API
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY", ""))
except Exception as e:
    sys.stderr.write(json.dumps({"success": False, "error": f"Failed to configure Google API: {e}"}))
    sys.exit(1)

# Configure Logging
LOGS_DIR.mkdir(exist_ok=True)
google_log_path = LOGS_DIR / (
    "analyze-google-calls-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d") + ".log"
)
google_logger = logging.getLogger("google_analysis")
if not google_logger.handlers:
    handler = logging.FileHandler(google_log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    google_logger.addHandler(handler)
    google_logger.setLevel(logging.INFO)

# ======================== [ 2. Utility Functions ] ==========================

def get_aspect_ratio(image_path: Path) -> str:
    """Return closest aspect ratio label for a given image."""
    with Image.open(image_path) as img:
        w, h = img.size
    aspect_map = [
        ("1x1", 1/1), ("2x3", 2/3), ("3x2", 3/2), ("3x4", 3/4), ("4x3", 4/3),
        ("4x5", 4/5), ("5x4", 5/4), ("5x7", 5/7), ("7x5", 7/5), ("9x16", 9/16),
        ("16x9", 16/9), ("A-Series-Horizontal", 1.414/1), ("A-Series-Vertical", 1/1.414),
    ]
    ar = round(w / h, 4)
    best = min(aspect_map, key=lambda tup: abs(ar - tup[1]))
    return best[0]

def parse_text_fallback(text: str) -> dict:
    """Extract key fields from a non-JSON AI response."""
    data = {"fallback_text": text}
    title_match = re.search(r"(?:Title|Artwork Title)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if title_match:
        data["title"] = title_match.group(1).strip()
    tag_match = re.search(r"Tags:\s*(.*)", text, re.IGNORECASE)
    if tag_match:
        data["tags"] = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]
    return data

def make_optimized_image_for_ai(src_path: Path, out_dir: Path) -> Path:
    """Return path to an optimized JPEG, creating it if necessary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{src_path.stem}-GOOGLE-OPTIMIZED.jpg"
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        im.thumbnail((2048, 2048), Image.LANCZOS)
        im.save(out_path, "JPEG", quality=85, optimize=True)
    return out_path

# ========================= [ 3. Main Analysis Logic ] =========================

def analyze_with_google(image_path: Path):
    """Analyze an image using Google Gemini."""
    start_ts = _dt.datetime.now(_dt.timezone.utc)
    log_entry = {
        "file": str(image_path),
        "provider": "google",
        "time_sent": start_ts.isoformat(),
    }

    try:
        if not image_path.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        temp_dir = UNANALYSED_ROOT / "temp"
        opt_img_path = make_optimized_image_for_ai(image_path, temp_dir)
        aspect = get_aspect_ratio(opt_img_path)
        assigned_sku = peek_next_sku(SKU_TRACKER)
        system_prompt = Path(ONBOARDING_PATH).read_text(encoding="utf-8")

        with open(opt_img_path, "rb") as f:
            img_bytes = f.read()

        prompt = (
            system_prompt.strip()
            + f"\n\nThe SKU for this artwork is {assigned_sku}. "
            + "NEVER invent a SKU, ALWAYS use the provided assigned_sku for the 'sku' and filename fields."
        )

        model_name = config.GOOGLE_GEMINI_PRO_VISION_MODEL_NAME
        parts = [
            prompt,
            f"Artwork filename: {image_path.name}\nAspect ratio: {aspect}\n" "Describe and analyze the artwork visually, then generate the listing as per the instructions above.",
            img_bytes,
        ]

        response = genai.GenerativeModel(model_name).generate_content(
            parts,
            generation_config={"temperature": 0.92},
            stream=False,
        )
        content = response.text.strip()

        safe_parts_for_log = [p for p in parts if not isinstance(p, bytes)]
        log_entry["prompt"] = safe_parts_for_log
        log_entry["response_preview"] = content[:500]

        try:
            ai_listing = json.loads(content)
            was_json = True
            err_msg = ""
        except json.JSONDecodeError:
            ai_listing = parse_text_fallback(content)
            was_json = False
            err_msg = "Google response not valid JSON"

        log_entry.update({
            "status": "success" if was_json else "fallback",
            "error": err_msg,
            "duration_sec": (_dt.datetime.now(_dt.timezone.utc) - start_ts).total_seconds(),
        })
        google_logger.info(json.dumps(sanitize_blob_data(log_entry)))

        return {"ai_listing": ai_listing, "was_json": was_json, "raw_response": content, "error_type": "fallback" if not was_json else "ok", "error_message": err_msg}

    except Exception as e:
        tb = traceback.format_exc()
        log_entry.update({
            "status": "fail",
            "error": str(e),
            "traceback": tb,
            "duration_sec": (_dt.datetime.now(_dt.timezone.utc) - start_ts).total_seconds(),
        })
        google_logger.info(json.dumps(sanitize_blob_data(log_entry)))
        raise RuntimeError(f"Google analysis failed: {e}") from e
    finally:
        if 'opt_img_path' in locals() and opt_img_path.exists():
            opt_img_path.unlink()


# ============================= [ 4. Main Entry ] ==============================
def main():
    parser = argparse.ArgumentParser(description="Analyze a single artwork with Google Gemini.")
    parser.add_argument("image", help="Path to the image file to process.")
    args = parser.parse_args()

    try:
        image_path = Path(args.image).resolve()
        result = analyze_with_google(image_path)
        safe_result = sanitize_blob_data(result)
        sys.stdout.write(json.dumps(safe_result, indent=2))
        sys.exit(0)
    except Exception as e:
        error_payload = {"success": False, "error": str(e), "traceback": traceback.format_exc()}
        sys.stderr.write(json.dumps(error_payload, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)}))
        sys.exit(1)

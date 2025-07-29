#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtNarrator | analyze_artwork_google.py
===============================================================
Dedicated script for analyzing artworks with Google's Gemini Pro Vision.
This script is designed to be called via subprocess from the main application.

- Receives a single image path as a command-line argument.
- Prints the final JSON analysis to stdout on success.
- Prints a JSON error object to stderr on failure.

INDEX
-----
1.  Imports
2.  Configuration & Setup
3.  Utility Functions
4.  Main Analysis Logic
5.  Command-Line Interface (CLI)
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import argparse
import datetime as _dt
import json
import logging
import os
import re
import sys
import traceback
from pathlib import Path

# Third-party imports
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai

# Local application imports
# Ensure project root is on sys.path for `config` import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utils.logger_utils import sanitize_blob_data
from utils.sku_assigner import peek_next_sku

Image.MAX_IMAGE_PIXELS = None
load_dotenv()


# ===========================================================================
# 2. Configuration & Setup
# ===========================================================================

# --- [ 2.1: Configure Google API Client ] ---
try:
    genai.configure(api_key=config.GEMINI_API_KEY or config.GOOGLE_API_KEY)
except Exception as e:
    sys.stderr.write(json.dumps({"success": False, "error": f"Failed to configure Google API: {e}"}))
    sys.exit(1)

# --- [ 2.2: Configure Logging ] ---
config.LOGS_DIR.mkdir(exist_ok=True)
google_log_path = config.LOGS_DIR / f"analyse-google/google-api-calls-{_dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d')}.log"
google_log_path.parent.mkdir(exist_ok=True)

google_logger = logging.getLogger("google_analysis")
if not google_logger.handlers:
    handler = logging.FileHandler(google_log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    google_logger.addHandler(handler)
    google_logger.setLevel(logging.INFO)


# ===========================================================================
# 3. Utility Functions
# ===========================================================================

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
    """Extracts key fields from a non-JSON AI response."""
    data = {"fallback_text": text}
    # Simplified regex for demonstration; a production version could be more robust
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


# ===========================================================================
# 4. Main Analysis Logic
# ===========================================================================

def analyze_with_google(image_path: Path):
    """Analyzes an image using Google Gemini and returns a result dictionary."""
    start_ts = _dt.datetime.now(_dt.timezone.utc)
    log_entry = { "file": str(image_path), "provider": "google", "time_sent": start_ts.isoformat() }
    
    opt_img_path = None
    try:
        if not image_path.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        google_logger.info(f"Starting Google analysis for {image_path.name}")
        temp_dir = config.UNANALYSED_ROOT / "temp"
        opt_img_path = make_optimized_image_for_ai(image_path, temp_dir)
        
        system_prompt = Path(config.ONBOARDING_PATH).read_text(encoding="utf-8")
        assigned_sku = peek_next_sku(config.SKU_TRACKER)
        
        prompt = (
            system_prompt.strip() +
            f"\n\nThe assigned SKU for this artwork is {assigned_sku}. "
            "You MUST use this SKU in the 'sku' field and in the 'seo_filename'."
        )
        
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        
        response = model.generate_content([prompt, Image.open(opt_img_path)])
        content = response.text.strip()
        google_logger.info(f"Received response from Gemini API for {image_path.name}")

        # ADD THIS BLOCK to remove markdown fences from the API response
        if content.startswith("```"):
            content = re.sub(r"```(json)?\s*(.*)\s*```", r"\2", content, flags=re.DOTALL)

        try:
            ai_listing = json.loads(content)
            result = {"ai_listing": ai_listing, "was_json": True, "raw_response": content}
        except json.JSONDecodeError:
            google_logger.warning(f"Gemini response for {image_path.name} was not valid JSON. Using fallback.")
            ai_listing = parse_text_fallback(content)
            result = {"ai_listing": ai_listing, "was_json": False, "raw_response": content}

        log_entry.update({"status": "success", "duration_sec": (_dt.datetime.now(_dt.timezone.utc) - start_ts).total_seconds()})
        google_logger.info(json.dumps(sanitize_blob_data(log_entry)))
        
        return result

    except Exception as e:
        tb = traceback.format_exc()
        log_entry.update({
            "status": "fail", "error": str(e), "traceback": tb,
            "duration_sec": (_dt.datetime.now(_dt.timezone.utc) - start_ts).total_seconds(),
        })
        google_logger.error(json.dumps(sanitize_blob_data(log_entry)))
        raise RuntimeError(f"Google analysis failed: {e}") from e
    finally:
        if opt_img_path and opt_img_path.exists():
            opt_img_path.unlink()


# ===========================================================================
# 5. Command-Line Interface (CLI)
# ===========================================================================

def main():
    """Parses CLI arguments and runs the analysis."""
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
    main()
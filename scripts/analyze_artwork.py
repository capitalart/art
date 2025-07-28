#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtNarrator | analyze_artwork.py
===============================================================
Analyzes artworks using OpenAI. This script is the core engine that
generates listing data, processes files, and prepares artworks for the
next stage in the workflow.

INDEX
-----
1.  Imports
2.  Configuration & Constants
3.  Logging Setup
4.  Core Utility Functions
5.  Colour Detection & Mapping
6.  OpenAI API Handler
7.  Main Analysis Workflow
8.  Command-Line Interface (CLI)
"""

# ===========================================================================
# 1. Imports
# ===========================================================================

# --- [ 1.1: Standard Library Imports ] ---
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
import base64

# --- [ 1.2: Third-Party Imports ] ---
from dotenv import load_dotenv
from PIL import Image
from openai import OpenAI

# --- [ 1.3: Local Application Imports ] ---
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utils.logger_utils import sanitize_blob_data, setup_logger
from utils.sku_assigner import get_next_sku
from helpers.listing_utils import assemble_gdws_description

# ===========================================================================
# 2. Configuration & Constants
# ===========================================================================

load_dotenv()
Image.MAX_IMAGE_PIXELS = None

API_KEY = config.OPENAI_API_KEY
if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in environment/.env file")
client = OpenAI(api_key=API_KEY, project=config.OPENAI_PROJECT_ID)

MOCKUPS_PER_LISTING = config.MOCKUPS_PER_LISTING
ETSY_COLOURS = config.ETSY_COLOURS
USER_ID = os.getenv("USER_ID", "anonymous")


# ===========================================================================
# 3. Logging Setup
# ===========================================================================

# Use the new centralized logger setup from utils/logger_utils.py
# This automatically creates timestamped files in the 'analyse-openai' folder.
logger = setup_logger(__name__, "ANALYZE_OPENAI")


# ===========================================================================
# 4. Core Utility Functions
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
    logger.info(f"Determined aspect ratio for {image_path.name}: {best[0]}")
    return best[0]


def slugify(text: str) -> str:
    """Return a slug suitable for filenames."""
    text = re.sub(r"[^\w\- ]+", "", text).strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()


def sync_filename_with_sku(seo_filename: str, sku: str) -> str:
    """Update the SKU portion of an SEO filename."""
    if not seo_filename or not sku:
        return seo_filename
    return re.sub(r"RJC-[A-Za-z0-9-]+(?=\.jpg$)", sku, seo_filename)


def read_onboarding_prompt() -> str:
    """Reads the main system prompt from the file defined in config."""
    return Path(config.ONBOARDING_PATH).read_text(encoding="utf-8")


def make_optimized_image_for_ai(src_path: Path, out_dir: Path) -> Path:
    """Return path to an optimized JPEG for AI analysis, creating it if necessary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{src_path.stem}-OPTIMIZED.jpg"
    with Image.open(src_path) as im:
        w, h = im.size
        scale = config.ANALYSE_MAX_DIM / max(w, h)
        if scale < 1.0:
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        im = im.convert("RGB")
        q = 85
        while True:
            im.save(out_path, "JPEG", quality=q, optimize=True)
            if out_path.stat().st_size <= config.ANALYSE_MAX_MB * 1024 * 1024 or q <= 60:
                break
            q -= 5
    logger.info(f"Optimized image for AI: {out_path.name} ({out_path.stat().st_size / 1024:.1f} KB)")
    return out_path


def save_artwork_files(original_path: Path, seo_name: str) -> dict:
    """Move/copy artwork files to a new processed folder and return their paths."""
    target_folder = config.PROCESSED_ROOT / seo_name
    target_folder.mkdir(parents=True, exist_ok=True)
    
    main_jpg = target_folder / config.FILENAME_TEMPLATES["artwork"].format(seo_slug=seo_name)
    thumb_jpg = target_folder / config.FILENAME_TEMPLATES["thumbnail"].format(seo_slug=seo_name)
    
    shutil.copy2(original_path, main_jpg)
    
    with Image.open(main_jpg) as img:
        thumb = img.copy()
        thumb.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
        thumb.save(thumb_jpg, "JPEG", quality=85)
        
    logger.info(f"Saved artwork files to {target_folder}")
    return {
        "main_jpg_path": str(main_jpg),
        "thumb_jpg_path": str(thumb_jpg),
        "processed_folder": str(target_folder)
    }


# ===========================================================================
# 5. Colour Detection & Mapping
# ===========================================================================

def _closest_colour(rgb_tuple: tuple[int, int, int]) -> str:
    """Find the nearest Etsy color name for a given RGB tuple."""
    min_dist = float('inf')
    best_colour = "White" # Fallback color
    for name, rgb in ETSY_COLOURS.items():
        dist = sum((rgb[i] - rgb_tuple[i]) ** 2 for i in range(3))
        if dist < min_dist:
            min_dist = dist
            best_colour = name
    return best_colour


def get_dominant_colours(img_path: Path, n: int = 2) -> list[str]:
    """Get the N most dominant colors from an image, mapped to Etsy's palette."""
    try:
        from sklearn.cluster import KMeans
        import numpy as np
    except ImportError:
        logger.error("Scikit-learn is not installed. Cannot perform color detection. Please run 'pip install scikit-learn'.")
        return ["White", "Black"]

    try:
        with Image.open(img_path) as img:
            img = img.convert("RGB").resize((100, 100))
            arr = np.asarray(img).reshape(-1, 3)

        kmeans = KMeans(n_clusters=max(3, n + 1), n_init='auto', random_state=42)
        kmeans.fit(arr)
        
        counts = np.bincount(kmeans.labels_)
        sorted_idx = np.argsort(counts)[::-1]
        
        colours = []
        seen_colours = set()
        for i in sorted_idx:
            rgb_tuple = tuple(int(c) for c in kmeans.cluster_centers_[i])
            etsy_colour = _closest_colour(rgb_tuple)
            if etsy_colour not in seen_colours:
                seen_colours.add(etsy_colour)
                colours.append(etsy_colour)
            if len(colours) >= n:
                break
        
        logger.info(f"Detected dominant colours for {img_path.name}: {colours}")
        return (colours + ["White", "Black"])[:n]
    except Exception as e:
        logger.error(f"Color detection failed for {img_path.name}: {e}")
        return ["White", "Black"]


# ===========================================================================
# 6. OpenAI API Handler
# ===========================================================================

def generate_ai_listing(image_path: Path, aspect: str, assigned_sku: str) -> tuple[dict, str]:
    """Calls the OpenAI API and returns the parsed JSON and raw text."""
    logger.info(f"Preparing to call OpenAI API for {image_path.name} with SKU {assigned_sku}.")
    with open(image_path, "rb") as f:
        encoded_img = base64.b64encode(f.read()).decode("utf-8")
    
    system_prompt = Path(config.ONBOARDING_PATH).read_text(encoding="utf-8")
    prompt = (
        system_prompt.strip() +
        f"\n\nThe assigned SKU for this artwork is {assigned_sku}. "
        "You MUST use this SKU in the 'sku' field and in the 'seo_filename'."
    )
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": [
            {"type": "text", "text": f"Analyze this artwork (filename: {image_path.name}, aspect ratio: {aspect}) and generate the complete JSON listing."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_img}"}},
        ]}
    ]

    try:
        logger.info("Sending request to OpenAI ChatCompletion API...")
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            max_tokens=2100,
            temperature=0.92,
            timeout=60,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content.strip()
        logger.info(f"Received response from OpenAI. Raw text length: {len(raw_text)} chars.")
        logger.debug(f"OpenAI Raw Response Preview: {raw_text[:200]}")
        
        return json.loads(raw_text), raw_text
    except json.JSONDecodeError:
        logger.warning("OpenAI response was not valid JSON. Attempting fallback parsing.")
        return parse_text_fallback(raw_text), raw_text
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}", exc_info=True)
        raise


def parse_text_fallback(text: str) -> dict:
    """Extracts listing data from non-JSON text as a last resort."""
    data = {"fallback_text": text}
    # Simplified regex for demonstration
    title_match = re.search(r"\"title\":\s*\"(.*?)\"", text, re.IGNORECASE)
    if title_match: data["title"] = title_match.group(1)
    return data


# ===========================================================================
# 7. Main Analysis Workflow
# ===========================================================================

def analyze_single(image_path: Path):
    """
    Orchestrates the full analysis workflow for a single artwork image.

    Steps:
      1. Validate input and prepare environment
      2. Determine aspect ratio
      3. Assign next available SKU
      4. Optimize image for OpenAI (downscale + compress)
      5. Send to OpenAI and parse AI response
      6. Save main and thumbnail images
      7. Detect dominant colours
      8. Assemble full listing dictionary
      9. Write listing JSON
     10. Cleanup temporary optimized file

    Args:
        image_path (Path): The full path to the artwork image.

    Returns:
        dict: Final listing data ready for export or post-processing.
    """
    logger.info(f"--- Starting analysis for: {image_path.name} (User: {USER_ID}) ---")
    
    if not image_path.is_file():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    temp_dir = config.UNANALYSED_ROOT / "temp"
    optimized_img_path = None

    try:
        # Step 1: Determine image aspect ratio
        aspect = get_aspect_ratio(image_path)

        # Step 2: Get next available SKU
        assigned_sku = get_next_sku(config.SKU_TRACKER)

        # Step 3: Optimize image for AI analysis
        optimized_img_path = make_optimized_image_for_ai(image_path, temp_dir)

        # Step 4: Query OpenAI for listing metadata
        ai_listing, raw_response = generate_ai_listing(optimized_img_path, aspect, assigned_sku)

        # Step 5: Create SEO name from title or fallback to filename
        seo_name = slugify(ai_listing.get("title", image_path.stem))

        # Step 6: Save main and thumbnail artwork files
        file_paths = save_artwork_files(image_path, seo_name)

        # Step 7: Detect primary and secondary colours
        primary_colour, secondary_colour = get_dominant_colours(Path(file_paths["main_jpg_path"]), 2)

        # Step 8: Build listing data object
        final_description = ai_listing.get("description") or assemble_gdws_description(aspect)

        listing_data = {
            "filename": image_path.name,
            "aspect_ratio": aspect,
            "sku": assigned_sku,
            "title": ai_listing.get("title", "Untitled Artwork"),
            "description": final_description,
            "tags": ai_listing.get("tags", []),
            "materials": ai_listing.get("materials", []),
            "primary_colour": primary_colour,
            "secondary_colour": secondary_colour,
            "price": 18.27,
            "seo_filename": sync_filename_with_sku(ai_listing.get("seo_filename", f"{seo_name}.jpg"), assigned_sku),
            "processed_folder": file_paths["processed_folder"],
            "main_jpg_path": file_paths["main_jpg_path"],
            "thumb_jpg_path": file_paths["thumb_jpg_path"],
            "openai_analysis": {
                "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                "raw_response_preview": raw_response[:500]
            }
        }

        # Step 9: Save final JSON to processed folder
        listing_json_path = Path(file_paths["processed_folder"]) / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_name)
        listing_json_path.write_text(json.dumps(listing_data, indent=2), encoding="utf-8")
        logger.info(f"Wrote final listing JSON to {listing_json_path}")

        logger.info(f"--- Successfully completed analysis for: {image_path.name} ---")
        return listing_data

    finally:
        # Step 10: Clean up temporary optimized file
        if optimized_img_path and optimized_img_path.exists():
            optimized_img_path.unlink()
            logger.debug(f"Cleaned up temporary file: {optimized_img_path}")


# ===========================================================================
# 8. Command-Line Interface (CLI)
# ===========================================================================

def main():
    """Parses CLI arguments and runs the analysis."""
    parser = argparse.ArgumentParser(description="Analyze artwork(s) with OpenAI.")
    parser.add_argument("image", help="Path to a single image file to process.")
    parser.add_argument("--json-output", action="store_true", help="Emit result as JSON to stdout for subprocess integration.")
    # The --provider argument is kept for compatibility with the toolkit script
    parser.add_argument("--provider", help="Ignored, but kept for compatibility.")
    args = parser.parse_args()

    try:
        result = analyze_single(Path(args.image))
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n✅ Analysis complete for: {args.image}")
            print(f"   - Title: {result.get('title')}")
            print(f"   - SKU: {result.get('sku')}")
            print(f"   - Output Folder: {result.get('processed_folder')}")

    except Exception as e:
        logger.critical(f"A fatal error occurred during analysis: {e}\n{traceback.format_exc()}")
        if args.json_output:
            print(json.dumps({"success": False, "error": str(e)}), file=sys.stderr)
            sys.exit(1)
        else:
            print(f"\n❌ An error occurred: {e}")
            print(f"   Please check the latest log file for details.")


if __name__ == "__main__":
    main()
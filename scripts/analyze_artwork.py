#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtNarrator | analyze_artwork.py
===============================================================
Analyzes artworks using OpenAI. This script is the core engine that
generates listing data, processes files, and prepares artworks for the
next stage in the workflow.
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
import argparse, base64, json, logging, os, random, re, shutil, sys, traceback
from pathlib import Path
import datetime as _dt
from dotenv import load_dotenv
from PIL import Image
from openai import OpenAI
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utils.logger_utils import setup_logger
from utils.sku_assigner import get_next_sku
from helpers.listing_utils import assemble_gdws_description

# ===========================================================================
# 2. Configuration & Constants
# ===========================================================================
load_dotenv()
Image.MAX_IMAGE_PIXELS = None
API_KEY = config.OPENAI_API_KEY
if not API_KEY: raise RuntimeError("OPENAI_API_KEY not set in environment/.env file")
client = OpenAI(api_key=API_KEY, project=config.OPENAI_PROJECT_ID)
ETSY_COLOURS = config.ETSY_COLOURS
USER_ID = os.getenv("USER_ID", "anonymous")
logger = setup_logger(__name__, "ANALYZE_OPENAI")

# ===========================================================================
# 4. Core Utility Functions
# ===========================================================================

def _write_status(step: str, percent: int, filename: str):
    """Writes progress to the shared status file for the UI modal."""
    payload = {"step": step, "percent": percent, "file": filename, "status": "analyzing"}
    try:
        config.ANALYSIS_STATUS_FILE.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass # Fails silently to not interrupt the main analysis process

def get_aspect_ratio(image_path: Path) -> str:
    """Return closest aspect ratio label for a given image."""
    with Image.open(image_path) as img: w, h = img.size
    aspect_map = [("1x1", 1/1), ("2x3", 2/3), ("3x2", 3/2), ("3x4", 3/4), ("4x3", 4/3), ("4x5", 4/5), ("5x4", 5/4), ("5x7", 5/7), ("7x5", 7/5), ("9x16", 9/16), ("16x9", 16/9)]
    ar = round(w / h, 4)
    best = min(aspect_map, key=lambda tup: abs(ar - tup[1]))
    logger.info(f"Determined aspect ratio for {image_path.name}: {best[0]}")
    return best[0]

def slugify(text: str) -> str:
    """Return a slug suitable for filenames."""
    text = re.sub(r"[^\w\- ]+", "", text).strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()

def generate_seo_filename(ai_slug: str, assigned_sku: str) -> tuple[str, str]:
    """
    Constructs a final SEO filename guaranteed to be <= 70 characters.
    """
    # Define the fixed parts of the filename
    SUFFIX = "-by-robin-custance"
    EXTENSION = ".jpg"
    
    # Calculate the maximum possible length for the AI-generated slug
    # 70 (total) - length of suffix - 1 (hyphen) - length of SKU - length of extension
    max_slug_len = 70 - len(SUFFIX) - 1 - len(assigned_sku) - len(EXTENSION)
    
    # Clean, slugify, and truncate the AI-provided slug
    clean_slug = slugify(ai_slug)
    truncated_slug = clean_slug[:max_slug_len]
    
    # Ensure the slug doesn't end with a hyphen after truncation
    if truncated_slug.endswith('-'):
        truncated_slug = truncated_slug[:-1]
        
    # Assemble the final filename
    final_filename = f"{truncated_slug}{SUFFIX}-{assigned_sku}{EXTENSION}"
    
    # The folder name is the stem of the final filename
    seo_folder_name = Path(final_filename).stem
    
    return final_filename, seo_folder_name

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
        if scale < 1.0: im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        im = im.convert("RGB")
        q = 85
        while True:
            im.save(out_path, "JPEG", quality=q, optimize=True)
            if out_path.stat().st_size <= config.ANALYSE_MAX_MB * 1024 * 1024 or q <= 60: break
            q -= 5
    logger.info(f"Optimized image for AI: {out_path.name} ({out_path.stat().st_size / 1024:.1f} KB)")
    return out_path

def save_artwork_files(original_path: Path, final_filename: str, seo_folder_name: str) -> dict:
    """Saves artwork files to a new processed folder using the final SEO names."""
    target_folder = config.PROCESSED_ROOT / seo_folder_name
    target_folder.mkdir(parents=True, exist_ok=True)
    
    main_jpg = target_folder / final_filename
    
    stem = Path(final_filename).stem
    thumb_jpg = target_folder / f"{stem}-THUMB.jpg"
    analyse_jpg = target_folder / f"{stem}-ANALYSE.jpg"

    shutil.copy2(original_path, main_jpg)
    
    with Image.open(main_jpg) as img:
        source_analyse_file = original_path.parent / f"{original_path.stem}-analyse.jpg"
        if source_analyse_file.exists():
            shutil.copy2(source_analyse_file, analyse_jpg)
            logger.info(f"Copied analyse image to {analyse_jpg.name}")
        else: # Fallback: create from main image
             shutil.copy2(main_jpg, analyse_jpg)

        thumb = img.copy()
        thumb.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
        thumb.save(thumb_jpg, "JPEG", quality=85)
        
    logger.info(f"Saved artwork files to {target_folder}")
    return {
        "main_jpg_path": str(main_jpg),
        "thumb_jpg_path": str(thumb_jpg),
        "analyse_jpg_path": str(analyse_jpg),
        "processed_folder": str(target_folder)
    }

def add_to_mockup_queue(artwork_path: str):
    """Adds a processed artwork path to the pending mockups queue file."""
    queue_file = config.PENDING_MOCKUPS_QUEUE_FILE
    try:
        queue = json.loads(queue_file.read_text(encoding="utf-8")) if queue_file.exists() else []
        if artwork_path not in queue:
            queue.append(artwork_path)
        queue_file.write_text(json.dumps(queue, indent=2), encoding="utf-8")
        logger.info(f"Added {Path(artwork_path).name} to mockup queue.")
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to update mockup queue file at {queue_file}: {e}")

# ===========================================================================
# 5. Colour Detection & Mapping
# ===========================================================================

def _closest_colour(rgb_tuple: tuple[int, int, int]) -> str:
    min_dist = float('inf')
    best_colour = "White"
    for name, rgb in ETSY_COLOURS.items():
        dist = sum((rgb[i] - rgb_tuple[i]) ** 2 for i in range(3))
        if dist < min_dist: min_dist, best_colour = dist, name
    return best_colour

def get_dominant_colours(img_path: Path, n: int = 2) -> list[str]:
    try:
        from sklearn.cluster import KMeans
        import numpy as np
    except ImportError:
        logger.error("Scikit-learn not installed. Cannot perform color detection.")
        return ["White", "Black"]

    try:
        with Image.open(img_path) as img:
            img = img.convert("RGB").resize((100, 100))
            arr = np.asarray(img).reshape(-1, 3)
        kmeans = KMeans(n_clusters=max(3, n + 1), n_init='auto', random_state=42).fit(arr)
        counts = np.bincount(kmeans.labels_)
        sorted_idx = np.argsort(counts)[::-1]
        
        colours, seen_colours = [], set()
        for i in sorted_idx:
            rgb_tuple = tuple(int(c) for c in kmeans.cluster_centers_[i])
            etsy_colour = _closest_colour(rgb_tuple)
            if etsy_colour not in seen_colours:
                seen_colours.add(etsy_colour)
                colours.append(etsy_colour)
            if len(colours) >= n: break
        
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
    
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": [{"type": "text", "text": f"Analyze this artwork (filename: {image_path.name}, aspect ratio: {aspect}) and generate the complete JSON listing. The assigned SKU is {assigned_sku}."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_img}"}}]}]

    try:
        logger.info("Sending request to OpenAI ChatCompletion API...")
        response = client.chat.completions.create(model=config.OPENAI_MODEL, messages=messages, max_tokens=2100, temperature=0.92, timeout=60, response_format={"type": "json_object"})
        
        raw_text = response.choices[0].message.content
        if raw_text is None:
            logger.error("OpenAI API returned an empty response (content is None).")
            return {}, "OpenAI response was null."
            
        raw_text = raw_text.strip()
        logger.info(f"Received response from OpenAI. Raw text length: {len(raw_text)} chars.")
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
    title_match = re.search(r"\"title\":\s*\"(.*?)\"", text, re.IGNORECASE)
    if title_match: data["title"] = title_match.group(1)
    return data

# ===========================================================================
# 7. Main Analysis Workflow
# ===========================================================================

def analyze_single(image_path: Path):
    """
    Orchestrates the full analysis workflow for a single artwork image.
    """
    logger.info(f"--- Starting analysis for: {image_path.name} (User: {USER_ID}) ---")
    _write_status("Starting analysis...", 5, image_path.name)
    
    if not image_path.is_file(): 
        raise FileNotFoundError(f"Input image not found: {image_path}")

    temp_dir = config.UNANALYSED_ROOT / "temp"
    optimized_img_path = None
    start_time = _dt.datetime.now(_dt.timezone.utc)

    try:
        with Image.open(image_path) as img:
            original_dimensions = f"{img.width}x{img.height}"

        aspect = get_aspect_ratio(image_path)
        
        _write_status("Assigning SKU...", 15, image_path.name)
        assigned_sku = get_next_sku(config.SKU_TRACKER)

        _write_status("Optimizing image for AI...", 25, image_path.name)
        optimized_img_path = make_optimized_image_for_ai(image_path, temp_dir)

        _write_status("Calling OpenAI API...", 40, image_path.name)
        ai_listing, raw_response = generate_ai_listing(optimized_img_path, aspect, assigned_sku)
        
        _write_status("Generating filenames...", 75, image_path.name)
        ai_slug = ai_listing.get("seo_filename_slug", slugify(ai_listing.get("title", image_path.stem)))
        final_filename, seo_folder_name = generate_seo_filename(ai_slug, assigned_sku)
        
        _write_status("Saving artwork files...", 85, image_path.name)
        file_paths = save_artwork_files(image_path, final_filename, seo_folder_name)

        _write_status("Detecting colors...", 95, image_path.name)
        main_image_path = Path(file_paths["main_jpg_path"])
        primary_colour, secondary_colour = get_dominant_colours(main_image_path, 2)
        final_description = ai_listing.get("description") or assemble_gdws_description(aspect)

        end_time = _dt.datetime.now(_dt.timezone.utc)
        duration = round((end_time - start_time).total_seconds(), 2)
        
        listing_data = {
            "filename": image_path.name, "aspect_ratio": aspect, "sku": assigned_sku,
            "title": ai_listing.get("title", image_path.stem),
            "description": final_description,
            "tags": ai_listing.get("tags", []), "materials": ai_listing.get("materials", []),
            "primary_colour": primary_colour, "secondary_colour": secondary_colour,
            "price": ai_listing.get("price", 18.27),
            "seo_filename": final_filename, # Use the final, constructed filename
            "processed_folder": file_paths["processed_folder"],
            "main_jpg_path": file_paths["main_jpg_path"], "thumb_jpg_path": file_paths["thumb_jpg_path"],
            "openai_analysis": {
                "original_file": str(image_path), "optimized_file": str(optimized_img_path),
                "size_bytes": optimized_img_path.stat().st_size,
                "size_mb": round(optimized_img_path.stat().st_size / (1024 * 1024), 3),
                "dimensions": original_dimensions, "time_sent": start_time.isoformat(),
                "time_responded": end_time.isoformat(), "duration_sec": duration,
                "status": "success", "api_response": raw_response[:500] + "..." if raw_response else "N/A"
            }
        }

        listing_json_path = Path(file_paths["processed_folder"]) / f"{seo_folder_name}-listing.json"
        listing_json_path.write_text(json.dumps(listing_data, indent=2), encoding="utf-8")
        logger.info(f"Wrote final listing JSON to {listing_json_path}")
        
        add_to_mockup_queue(file_paths["main_jpg_path"])
        
        logger.info(f"--- Successfully completed analysis for: {image_path.name} ---")
        return listing_data

    finally:
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
    parser.add_argument("--json-output", action="store_true", help="Emit result as JSON for subprocess integration.")
    parser.add_argument("--provider", help="Ignored, for compatibility.")
    args = parser.parse_args()

    try:
        result = analyze_single(Path(args.image))
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n✅ Analysis complete for: {args.image}\n   - Title: {result.get('title')}\n   - SKU: {result.get('sku')}\n   - Output Folder: {result.get('processed_folder')}")

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
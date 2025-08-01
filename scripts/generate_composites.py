# scripts/generate_composites.py
"""
Generates composite mockup images for artworks in a pending queue.

This script reads a queue of processed artworks, selects a random set of
mockups for the correct aspect ratio, and then uses perspective transform
to overlay the artwork onto the mockups, creating the final preview images.

INDEX
-----
1.  Imports & Initialisation
2.  Image Processing Utilities
3.  Queue Management
4.  Main Workflow Logic
5.  Command-Line Interface (CLI)
"""

# ===========================================================================
# 1. Imports & Initialisation
# ===========================================================================
from __future__ import annotations
import os
import json
import random
import re
import argparse
import logging
import sys
from pathlib import Path

# Third-party imports
from PIL import Image
import cv2
import numpy as np

# Local application imports
# Ensure project root is on sys.path for `config` import when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

Image.MAX_IMAGE_PIXELS = None
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ===========================================================================
# 2. Image Processing Utilities
# ===========================================================================

def resize_image_for_long_edge(image: Image.Image, target_long_edge=2000) -> Image.Image:
    """Resizes an image to have its longest edge match the target size."""
    width, height = image.size
    scale = target_long_edge / max(width, height)
    if scale < 1.0:
        new_width = int(width * scale)
        new_height = int(height * scale)
        return image.resize((new_width, new_height), Image.LANCZOS)
    return image


def apply_perspective_transform(art_img: Image.Image, mockup_img: Image.Image, dst_coords: list) -> Image.Image:
    """
    Overlays artwork onto a mockup using perspective transform,
    handling RGBA transparency correctly.
    """
    w, h = art_img.size
    # Note: dst_coords must be in TL, TR, BL, BR order.
    src_points = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    dst_points = np.float32([[c['x'], c['y']] for c in dst_coords])
    
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    art_np = np.array(art_img.convert("RGBA"))
    
    warped = cv2.warpPerspective(art_np, matrix, (mockup_img.width, mockup_img.height))
    warped_pil = Image.fromarray(warped)
    
    # Composite the warped artwork over the mockup using alpha channels
    final_image = Image.alpha_composite(mockup_img.convert("RGBA"), warped_pil)
    return final_image


# ===========================================================================
# 3. Queue Management
# ===========================================================================

def remove_from_queue(processed_img_path: str, queue_file: Path):
    """Removes a processed image from the pending queue file."""
    if not queue_file.exists():
        return
    try:
        queue = json.loads(queue_file.read_text(encoding="utf-8"))
        if processed_img_path in queue:
            queue.remove(processed_img_path)
            queue_file.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error updating queue file {queue_file}: {e}")


# ===========================================================================
# 4. Main Workflow Logic
# ===========================================================================

def _process_queued_artwork(img_path_str: str, total_in_queue: int, current_index: int):
    """Processes a single artwork from the queue."""
    img_path = Path(img_path_str)
    if not img_path.exists():
        logger.warning(f"File not found in queue (skipped): {img_path}")
        return

    folder = img_path.parent
    seo_name = img_path.stem
    json_listing_path = folder / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_name)

    if not json_listing_path.exists():
        logger.warning(f"Listing JSON not found for {img_path.name}, skipping.")
        return
        
    try:
        entry = json.loads(json_listing_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON for {img_path.name}, skipping: {e}")
        return

    aspect = entry.get("aspect_ratio")
    logger.info(f"[{current_index}/{total_in_queue}] Processing: {img_path.name} [Aspect: {aspect}]")

    mockups_cat_dir = config.MOCKUPS_CATEGORISED_DIR / aspect
    coords_base_dir = config.COORDS_DIR / aspect
    
    if not mockups_cat_dir.exists() or not coords_base_dir.exists():
        logger.warning(f"Missing mockups or coordinates directory for aspect: {aspect}")
        return

    art_img = Image.open(img_path)
    mockup_entries = []
    
    categories = [d for d in mockups_cat_dir.iterdir() if d.is_dir()]
    if not categories:
        logger.warning(f"No mockup categories found for aspect {aspect}")
        return

    # Select a diverse set of mockups, up to the configured limit
    num_to_generate = config.MOCKUPS_PER_LISTING
    selections = []
    if len(categories) >= num_to_generate:
        chosen_categories = random.sample(categories, num_to_generate)
    else:
        # If not enough unique categories, allow duplicates
        chosen_categories = random.choices(categories, k=num_to_generate)
        logger.warning(f"Only {len(categories)} unique categories available; using duplicates to reach {num_to_generate}")

    for cat_dir in chosen_categories:
        pngs = list(cat_dir.glob("*.png"))
        if pngs:
            selections.append((cat_dir, random.choice(pngs)))

    if not selections:
        logger.warning(f"No .png mockup files found for aspect {aspect}")
        return

    # Use enumerate to get a sequential index for naming
    for i, (cat_dir, mockup_file) in enumerate(selections):
        coord_path = coords_base_dir / cat_dir.name / f"{mockup_file.stem}.json"
        if not coord_path.exists():
            logger.warning(f"--> Missing coordinates for {mockup_file.name}, skipping this mockup.")
            continue

        try:
            coords_data = json.loads(coord_path.read_text(encoding="utf-8"))
            mockup_img = Image.open(mockup_file)
            composite = apply_perspective_transform(art_img, mockup_img, coords_data["corners"])

            # Use the loop index 'i' for a clean, sequential number
            output_filename = config.FILENAME_TEMPLATES["mockup"].format(seo_slug=seo_name, num=i + 1)
            output_path = folder / output_filename
            composite.convert("RGB").save(output_path, "JPEG", quality=90)
            
            # --- CREATE THUMBNAIL LOGIC ---
            thumb_dir = folder / config.THUMB_SUBDIR
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb_name = f"{output_path.stem}-thumb.jpg"
            thumb_path = thumb_dir / thumb_name
            with composite.copy() as thumb_img:
                thumb_img.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
                thumb_img.convert("RGB").save(thumb_path, "JPEG", quality=85)
            # --- END THUMBNAIL LOGIC ---

            mockup_entries.append({
                "category": cat_dir.name,
                "source": str(mockup_file.relative_to(config.MOCKUPS_INPUT_DIR)),
                "composite": output_filename,
                "thumbnail": thumb_name, # Add the thumbnail name to the listing data
            })
            logger.info(f"   - Mockup created: {output_filename} (from category '{cat_dir.name}')")
        except Exception as e:
            logger.error(f"--> FAILED to generate composite for {mockup_file.name}: {e}", exc_info=True)

    # Update the main listing JSON with the new mockup data
    entry["mockups"] = mockup_entries
    json_listing_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")


def main_queue_processing():
    """Main function for processing artworks from the pending queue."""
    logger.info("===== ArtNarrator: Composite Generator (Queue Mode) =====")
    # Use the new config variable for the queue file path
    queue_file = config.PENDING_MOCKUPS_QUEUE_FILE

    if not queue_file.exists():
        logger.info("No pending mockups queue file found. Nothing to do.")
        return

    try:
        queue = json.loads(queue_file.read_text(encoding="utf-8"))
        if not queue:
            logger.info("✅ No pending artworks in queue. All done!")
            return
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Could not read or parse queue file {queue_file}: {e}")
        return

    logger.info(f"🎨 Found {len(queue)} artwork(s) in the pending queue.")
    
    processed_count = 0
    for i, img_path_str in enumerate(queue[:]): # Process a copy of the queue
        _process_queued_artwork(img_path_str, len(queue), i + 1)
        remove_from_queue(img_path_str, queue_file)
        processed_count += 1
        logger.info(f"🎯 Finished processing for {Path(img_path_str).name}.")

    logger.info(f"✅ Done. {processed_count} artwork(s) processed and removed from queue.")


# ===========================================================================
# 5. Command-Line Interface (CLI)
# ===========================================================================

def main():
    """Parses CLI arguments and runs the appropriate workflow."""
    parser = argparse.ArgumentParser(description="Generate mockup composites for artworks.")
    # Add arguments if a single-file mode is ever needed, otherwise default to queue.
    args = parser.parse_args()
    
    main_queue_processing()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# =============================================================================
# ArtNarrator: Automated Mockup Coordinate Generator
#
# PURPOSE:
#   Scans all PNG mockups in the 'categorised' directory, fixes any broken
#   sRGB profiles, automatically detects the transparent artwork zone using
#   OpenCV, and outputs a JSON coordinate file for each mockup.
#
# INDEX
# -----
# 1.  Imports
# 2.  Configuration & Logging
# 3.  Core Helper Functions
# 4.  Main Execution Logic
# 5.  Command-Line Interface (CLI)
# =============================================================================

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import json
import logging
import sys
from pathlib import Path

# Third-party imports
import cv2
from PIL import Image

# Local application imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utils.logger_utils import setup_logger

# ===========================================================================
# 2. Configuration & Logging
# ===========================================================================
# Use the centralized logger to create a timestamped log file for this script run
logger = setup_logger(__name__, "DEFAULT")


# ===========================================================================
# 3. Core Helper Functions
# ===========================================================================

def fix_srgb_profile(image_path: Path):
    """Strips potentially problematic ICC profiles from a PNG image."""
    try:
        with Image.open(image_path) as img:
            # Save the image without the ICC profile to prevent libpng warnings
            if "icc_profile" in img.info and img.format == 'PNG':
                img.save(image_path, format="PNG")
    except Exception as e:
        logger.warning(f"Could not clean sRGB profile for {image_path.name}: {e}")


def sort_corners(pts: list[dict]) -> list[dict]:
    """Sorts 4 corner points to a consistent order: Top-Left, Top-Right, Bottom-Left, Bottom-Right."""
    # Sort by y-coordinate first, then x-coordinate for ties
    pts.sort(key=lambda p: (p["y"], p["x"]))
    top = sorted(pts[:2], key=lambda p: p["x"])
    bottom = sorted(pts[2:], key=lambda p: p["x"])
    return [*top, *bottom]


def detect_corner_points(image_path: Path) -> list[dict] | None:
    """Detects 4 corner points of a transparent region in a PNG using OpenCV."""
    image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if image is None or image.shape[2] != 4:
        logger.warning(f"Image is not a valid RGBA PNG: {image_path.name}")
        return None

    # Use the alpha channel to find the non-transparent area
    alpha = image[:, :, 3]
    _, thresh = cv2.threshold(alpha, 1, 255, cv2.THRESH_BINARY)
    thresh_inv = cv2.bitwise_not(thresh) # Invert to find the black (transparent) area
    contours, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        logger.warning(f"No contours found in alpha channel for: {image_path.name}")
        return None

    # Find the largest contour, which should be the artwork area
    contour = max(contours, key=cv2.contourArea)
    epsilon = 0.02 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)

    if len(approx) != 4:
        logger.warning(f"Could not find a valid 4-corner polygon in: {image_path.name} (found {len(approx)} points)")
        return None

    corners = [{"x": int(pt[0][0]), "y": int(pt[0][1])} for pt in approx]
    return sort_corners(corners)


# ===========================================================================
# 4. Main Execution Logic
# ===========================================================================

def main():
    """Main execution function to scan all mockups and generate coordinates."""
    print("🚀 Starting Automated Coordinate Generation...", flush=True)
    logger.info("Starting Automated Coordinate Generation script.")
    
    processed_count = 0
    error_count = 0
    
    mockup_root = config.MOCKUPS_CATEGORISED_DIR
    coord_root = config.COORDS_DIR

    if not mockup_root.exists():
        msg = f"Mockup directory not found: {mockup_root}"
        print(f"❌ Error: {msg}", flush=True)
        logger.critical(msg)
        return

    for aspect_dir in sorted(mockup_root.iterdir()):
        if not aspect_dir.is_dir(): continue
        
        aspect_name = aspect_dir.name
        coord_aspect_dir = coord_root / aspect_name
        
        for category_dir in sorted(aspect_dir.iterdir()):
            if not category_dir.is_dir(): continue

            print(f"\n🔍 Processing Category: {aspect_dir.name}/{category_dir.name}", flush=True)
            logger.info(f"Processing Category: {aspect_dir.name}/{category_dir.name}")
            output_dir = coord_aspect_dir / category_dir.name
            output_dir.mkdir(parents=True, exist_ok=True)

            for mockup_file in sorted(category_dir.glob("*.png")):
                try:
                    output_path = output_dir / f"{mockup_file.stem}.json"
                    print(f"  -> Processing {mockup_file.name}...", flush=True)
                    
                    fix_srgb_profile(mockup_file)
                    corners = detect_corner_points(mockup_file)
                    
                    if corners:
                        data = {"template": mockup_file.name, "corners": corners}
                        output_path.write_text(json.dumps(data, indent=4), encoding='utf-8')
                        processed_count += 1
                        logger.info(f"Successfully generated coordinates for {mockup_file.name}")
                    else:
                        print(f"  ⚠️ Skipped (no valid 4-corner area found): {mockup_file.name}", flush=True)
                        error_count += 1
                except Exception as e:
                    print(f"  ❌ Error processing {mockup_file.name}: {e}", flush=True)
                    logger.error(f"Error processing {mockup_file.name}: {e}", exc_info=True)
                    error_count += 1

    print(f"\n🏁 Finished. Processed: {processed_count}, Errors/Skipped: {error_count}\n", flush=True)
    logger.info(f"Script finished. Processed: {processed_count}, Errors/Skipped: {error_count}")


# ===========================================================================
# 5. Command-Line Interface (CLI)
# ===========================================================================

if __name__ == "__main__":
    main()
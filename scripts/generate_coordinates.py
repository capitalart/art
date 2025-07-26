#!/usr/bin/env python3
# =============================================================================
# ArtNarrator: Automated Mockup Coordinate Generator
# Purpose:
#   Scans all PNG mockups, fixes any broken sRGB profiles to prevent warnings,
#   and automatically detects the transparent artwork zone, outputting a
#   JSON coordinate file for each.
# =============================================================================

import cv2
import json
import logging
import sys
from pathlib import Path
from PIL import Image

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def fix_srgb_profile(image_path: Path):
    """Strips broken ICC profiles from a PNG image to prevent libpng warnings."""
    try:
        with Image.open(image_path) as img:
            if "icc_profile" in img.info and img.format == 'PNG':
                img.save(image_path, format="PNG")
    except Exception as e:
        logger.warning(f"⚠️ Could not clean sRGB profile for {image_path.name}: {e}")

def sort_corners(pts):
    """Sorts 4 corner points to a consistent order: TL, TR, BL, BR."""
    pts = sorted(pts, key=lambda p: (p["y"], p["x"]))
    top = sorted(pts[:2], key=lambda p: p["x"])
    bottom = sorted(pts[2:], key=lambda p: p["x"])
    return [*top, *bottom]

def detect_corner_points(image_path: Path):
    """Detects 4 corner points of a transparent region in a PNG."""
    image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if image is None or image.shape[2] != 4: return None
    alpha = image[:, :, 3]
    _, thresh = cv2.threshold(alpha, 1, 255, cv2.THRESH_BINARY)
    thresh_inv = cv2.bitwise_not(thresh)
    contours, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    contour = max(contours, key=cv2.contourArea)
    epsilon = 0.02 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    if len(approx) != 4: return None
    corners = [{"x": int(pt[0][0]), "y": int(pt[0][1])} for pt in approx]
    return sort_corners(corners)

def main():
    """Main execution function."""
    print("🚀 Starting Automated Coordinate Generation...", flush=True)
    
    processed_count = 0
    error_count = 0
    
    mockup_root = config.MOCKUPS_CATEGORISED_DIR
    coord_root = config.COORDS_DIR

    if not mockup_root.exists():
        print(f"❌ Error: Mockup directory not found: {mockup_root}", flush=True)
        return

    for aspect_dir in sorted(mockup_root.iterdir()):
        if not aspect_dir.is_dir(): continue
        
        aspect_name = aspect_dir.name.replace("-categorised", "")
        coord_aspect_dir = coord_root / aspect_name
        
        for category_dir in sorted(aspect_dir.iterdir()):
            if not category_dir.is_dir(): continue

            print(f"\n🔍 Processing Category: {aspect_dir.name}/{category_dir.name}", flush=True)
            output_dir = coord_aspect_dir / category_dir.name
            output_dir.mkdir(parents=True, exist_ok=True)

            for mockup_file in sorted(category_dir.glob("*.png")):
                output_path = output_dir / f"{mockup_file.stem}.json"
                print(f"  -> Processing {mockup_file.name}...", flush=True)
                try:
                    fix_srgb_profile(mockup_file)
                    corners = detect_corner_points(mockup_file)
                    if corners:
                        data = {"template": mockup_file.name, "corners": corners}
                        with open(output_path, 'w') as f:
                            json.dump(data, f, indent=4)
                        processed_count += 1
                    else:
                        print(f"  ⚠️ Skipped (no valid 4-corner area found): {mockup_file.name}", flush=True)
                        error_count += 1
                except Exception as e:
                    print(f"  ❌ Error processing {mockup_file.name}: {e}", flush=True)
                    error_count += 1

    print(f"\n🏁 Finished. Processed: {processed_count}, Errors/Skipped: {error_count}\n", flush=True)

if __name__ == "__main__":
    main()
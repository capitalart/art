#!/usr/bin/env python3
# ==============================================================================
# Script: generate_coordinates_for_ratio.py
# Purpose: Scans all PNGs in a given categorized aspect ratio folder,
#          prompts the user to click 4 corners, and saves the coordinates.
# ==============================================================================

import argparse
import pathlib
import logging
import sys
import json
import cv2

# Ensure project root is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def get_args():
    parser = argparse.ArgumentParser(description="Generate coordinates for a single aspect ratio")
    parser.add_argument("--aspect_ratio_path", type=str, required=True, help="Path to an aspect ratio folder (e.g., .../4x5-categorised)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing coordinate files")
    return parser.parse_args()

def pick_points_gui(img_path):
    """Opens a GUI for the user to select 4 corner points."""
    img = cv2.imread(str(img_path))
    if img is None:
        raise IOError(f"Could not read image: {img_path}")
    points = []
    window_name = "Select Corners (TL, TR, BR, BL) - Press ESC to confirm"

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append((x, y))
            cv2.circle(img, (x, y), 7, (0, 255, 0), -1)
            cv2.imshow(window_name, img)

    cv2.imshow(window_name, img)
    cv2.setMouseCallback(window_name, mouse_callback)
    while len(points) < 4:
        key = cv2.waitKey(20) & 0xFF
        if key == 27: # ESC key
            break
    cv2.destroyAllWindows()
    if len(points) != 4:
        raise Exception("Did not select exactly 4 points. Aborted.")
    return points

def main():
    args = get_args()
    aspect_folder = pathlib.Path(args.aspect_ratio_path).resolve()
    aspect_name = aspect_folder.name.replace("-categorised", "")
    
    # Define the output directory based on the aspect name
    out_base = config.COORDS_DIR / aspect_name
    logger.info(f"Saving coordinates to: {out_base}")

    for category_dir in sorted(aspect_folder.iterdir()):
        if not category_dir.is_dir():
            continue
        
        logger.info(f"--- Processing Category: {category_dir.name} ---")
        out_cat_folder = out_base / category_dir.name
        out_cat_folder.mkdir(parents=True, exist_ok=True)
        
        for img in sorted(category_dir.glob("*.png")):
            coord_file = out_cat_folder / f"{img.stem}.json"
            if coord_file.exists() and not args.overwrite:
                logger.info(f"✅ Skipping, coordinates exist: {img.name}")
                continue
            
            logger.info(f"👉 Please select coordinates for: {img.name}")
            try:
                points = pick_points_gui(img)
                # Convert points to the required JSON structure
                corners = [
                    {"x": points[0][0], "y": points[0][1]}, # Top-Left
                    {"x": points[1][0], "y": points[1][1]}, # Top-Right
                    {"x": points[3][0], "y": points[3][1]}, # Bottom-Left (Note: CV2 order vs your format)
                    {"x": points[2][0], "y": points[2][1]}  # Bottom-Right
                ]
                data = {"filename": img.name, "corners": corners}
                with open(coord_file, "w") as f:
                    json.dump(data, f, indent=2)
                logger.info(f"✅ Saved coordinates for: {img.name}")
            except Exception as e:
                logger.error(f"❌ Failed to process {img}: {e}")

if __name__ == "__main__":
    main()
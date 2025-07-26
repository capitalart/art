import os
import json
import shutil
import random
from pathlib import Path
from PIL import Image, ImageDraw
import cv2
import numpy as np

# Ensure project root is on sys.path for ``config`` import when run directly
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# This file now references all path, directory, and filename variables strictly from config.py. No local or hardcoded path constants remain.
import config

Image.MAX_IMAGE_PIXELS = None
DEBUG_MODE = False

# ======================= [ 1. CONFIG & PATHS ] =======================
QUEUE_FILE = config.PROCESSED_ROOT / "pending_mockups.json"

# ======================= [ 2. UTILITIES ] =========================

def resize_image_for_long_edge(image: Image.Image, target_long_edge=2000) -> Image.Image:
    width, height = image.size
    scale = target_long_edge / max(width, height)
    if scale < 1.0:
        new_width = int(width * scale)
        new_height = int(height * scale)
        return image.resize((new_width, new_height), Image.LANCZOS)
    return image

def apply_perspective_transform(art_img, mockup_img, dst_coords):
    w, h = art_img.size
    src_points = np.float32([[0, 0], [w, 0], [0, h], [w, h]]) # Corrected order for sort_corners
    dst_points = np.float32([[c['x'], c['y']] for c in dst_coords])
    
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    art_np = np.array(art_img.convert("RGBA"))
    
    warped = cv2.warpPerspective(art_np, matrix, (mockup_img.width, mockup_img.height))
    
    mockup_rgba = mockup_img.convert("RGBA")
    warped_pil = Image.fromarray(warped)
    
    # Composite the warped image over the mockup
    final_image = Image.alpha_composite(mockup_rgba, warped_pil)
    return final_image

def remove_from_queue(processed_img_path, queue_file):
    """Remove the processed image from the pending queue."""
    if os.path.exists(queue_file):
        with open(queue_file, "r", encoding="utf-8") as f:
            queue = json.load(f)
        new_queue = [p for p in queue if p != processed_img_path]
        with open(queue_file, "w", encoding="utf-8") as f:
            json.dump(new_queue, f, indent=2)

# =============== [ 3. MAIN WORKFLOW: QUEUE-BASED PROCESSING ] ================
def main():
    print("\n===== ArtNarrator Lite: Composite Generator (Queue Mode) =====\n")

    if not QUEUE_FILE.exists():
        print(f"⚠️ No pending mockups queue found at {QUEUE_FILE}")
        return

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)
    if not queue:
        print(f"✅ No pending artworks in queue. All done!")
        return

    print(f"🎨 {len(queue)} artworks in the pending queue.\n")

    processed_count = 0
    for img_path_str in queue[:]:
        img_path = Path(img_path_str)
        if not img_path.exists():
            print(f"❌ File not found (skipped): {img_path}")
            remove_from_queue(str(img_path), QUEUE_FILE)
            continue

        folder = img_path.parent
        seo_name = img_path.stem
        
        json_listing = folder / f"{seo_name}-listing.json"
        if not json_listing.exists():
            print(f"⚠️ Listing JSON not found for {img_path.name}, skipping.")
            remove_from_queue(str(img_path), QUEUE_FILE)
            continue
            
        with open(json_listing, "r", encoding="utf-8") as jf:
            entry = json.load(jf)
        aspect = entry.get("aspect_ratio")
        
        print(f"\n[{processed_count+1}/{len(queue)}] Processing: {img_path.name} [{aspect}]")

        mockups_cat_dir = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised"
        coords_base_dir = config.COORDS_DIR / aspect
        
        if not mockups_cat_dir.exists() or not coords_base_dir.exists():
            print(f"⚠️ Missing mockups or coordinates for aspect: {aspect}")
            remove_from_queue(str(img_path), QUEUE_FILE)
            continue

        art_img = Image.open(img_path)
        mockup_entries = []
        
        categories = sorted([d for d in mockups_cat_dir.iterdir() if d.is_dir()])
        for category_dir in categories:
            png_mockups = list(category_dir.glob("*.png"))
            if not png_mockups: continue
            
            selected_mockup = random.choice(png_mockups)
            coord_path = coords_base_dir / category_dir.name / f"{selected_mockup.stem}.json"
            
            if not coord_path.exists():
                print(f"⚠️ Missing coordinates for {selected_mockup.name} ({aspect}/{category_dir.name})")
                continue

            with open(coord_path, "r", encoding="utf-8") as f:
                coords_data = json.load(f)

            mockup_img = Image.open(selected_mockup)
            composite = apply_perspective_transform(art_img, mockup_img, coords_data["corners"])

            output_filename = f"{seo_name}-{selected_mockup.stem}.jpg"
            output_path = folder / output_filename
            composite.convert("RGB").save(output_path, "JPEG", quality=90)
            
            mockup_entries.append({
                "category": category_dir.name,
                "source": str(selected_mockup.relative_to(config.MOCKUPS_INPUT_DIR)),
                "composite": output_filename,
            })
            print(f"   - Mockup created: {output_filename} ({category_dir.name})")

        listing_data = entry
        listing_data["mockups"] = mockup_entries
        with open(json_listing, "w", encoding="utf-8") as lf:
            json.dump(listing_data, lf, indent=2, ensure_ascii=False)

        print(f"🎯 Finished all mockups for {img_path.name}.")
        processed_count += 1
        remove_from_queue(str(img_path), QUEUE_FILE)

    print(f"\n✅ Done. {processed_count} artwork(s) processed and removed from queue.\n")

if __name__ == "__main__":
    main()
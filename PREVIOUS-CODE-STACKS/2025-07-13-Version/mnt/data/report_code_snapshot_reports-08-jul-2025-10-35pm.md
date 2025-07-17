# 🧠 CapitalArt Code Snapshot — REPORTS-08-JUL-2025-10-35PM


---
## 📄 capitalart.py

```py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =========================================================
# CapitalArt Main Flask App (All-in-One, Robbie Mode™)
# File: capitalart.py
# Maintainer: Robin Custance
# =========================================================

# ========== SECTION 0. IMPORTS & ENVIRONMENT SETUP ==========

import os
import sys
import json
import uuid
import subprocess
import random
import shutil
import logging
import re # Make sure 're' is imported here
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from PIL import Image, ImageDraw
import cv2
import numpy as np

# ========== SECTION 1. PATHS & CONSTANTS ==========

BASE_DIR = Path(__file__).parent.resolve()
MOCKUPS_DIR = BASE_DIR / "inputs" / "mockups" / "4x5-categorised"
ARTWORKS_DIR = BASE_DIR / "inputs" / "artworks"
ARTWORK_PROCESSED_DIR = BASE_DIR / "outputs" / "processed"
SELECTIONS_DIR = BASE_DIR / "outputs" / "selections"
LOGS_DIR = BASE_DIR / "logs"
COMPOSITES_DIR = BASE_DIR / "outputs" / "composites"
FINALISED_DIR = BASE_DIR / "outputs" / "finalised-artwork"
COORDS_ROOT = BASE_DIR / "inputs" / "Coordinates"
ANALYZE_SCRIPT_PATH = BASE_DIR / "scripts" / "analyze_artwork.py"
GENERATE_SCRIPT_PATH = BASE_DIR / "scripts" / "generate_composites.py"

from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # disables the warning (careful: disables protection)

# ========== SECTION 2. FLASK APP INITIALISATION ==========

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "mockup-secret-key")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOGS_DIR / "composites-workflow.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ========== SECTION 3. UTILITY FUNCTIONS ==========

# ======== 3a. [Global Template Context: Always provide latest_artwork to templates] ========
@app.context_processor
def inject_latest_artwork():
    latest = get_latest_processed_artwork()
    return dict(latest_artwork=latest)

def get_latest_processed_artwork():
    # Path to your processed artworks directory
    processed_dir = Path("outputs/processed")
    if not processed_dir.exists():
        return None
    # Find all artwork folders
    all_folders = [f for f in processed_dir.iterdir() if f.is_dir()]
    if not all_folders:
        return None
    # Sort folders by modified time, latest first
    all_folders.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    latest_folder = all_folders[0]
    # Try to find a listing json file in the latest folder
    for file in latest_folder.glob("*.json"):
        if "-listing.json" in file.name:
            # Extract aspect and filename for the nav link
            # You may want to parse this more precisely for your naming
            # Here we just return a dict with guessed values:
            aspect = "4x5" # or extract from your data!
            filename = file.name.replace("-listing.json", ".jpg")
            return {"aspect": aspect, "filename": filename}
    return None

## 3.1. Get sorted mockup categories
def get_categories():
    return sorted([folder.name for folder in MOCKUPS_DIR.iterdir() if folder.is_dir() and folder.name.lower() != "uncategorised"])

## 3.2. Get random image for a category
def random_image(category):
    cat_dir = MOCKUPS_DIR / category
    images = [f.name for f in cat_dir.glob("*.png")]
    return random.choice(images) if images else None

## 3.3. Initialise slots in session
def init_slots():
    cats = get_categories()
    session["slots"] = [{"category": c, "image": random_image(c)} for c in cats]

## 3.4. Compute options (categories) for mockup slots
def compute_options(slots):
    cats = get_categories()
    return [cats for _ in slots]

## 3.5. Resize image for preview or transformation
def resize_image_for_long_edge(image: Image.Image, target_long_edge: int = 2000) -> Image.Image:
    width, height = image.size
    if width > height:
        new_width = target_long_edge
        new_height = int(height * (target_long_edge / width))
    else:
        new_height = target_long_edge
        new_width = int(width * (target_long_edge / height))
    return image.resize((new_width, new_height), Image.LANCZOS)

## 3.6. Apply perspective transform (for composite generation)
def apply_perspective_transform(art_img: Image.Image, mockup_img: Image.Image, dst_coords: list) -> Image.Image:
    w, h = art_img.size
    src_points = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst_points = np.float32(dst_coords)
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    art_np = np.array(art_img)
    warped = cv2.warpPerspective(art_np, matrix, (mockup_img.width, mockup_img.height))
    mask = np.any(warped > 0, axis=-1).astype(np.uint8) * 255
    mask = Image.fromarray(mask).convert("L")
    composite = Image.composite(Image.fromarray(warped), mockup_img, mask)
    return composite

## 3.7. Find most recent composite output folder
def latest_composite_folder() -> str | None:
    latest_time = 0
    latest_folder = None
    for folder in ARTWORK_PROCESSED_DIR.iterdir():
        if not folder.is_dir():
            continue
        images = list(folder.glob("*-MU-*.jpg"))
        if not images:
            continue
        recent = max(images, key=lambda p: p.stat().st_mtime)
        if recent.stat().st_mtime > latest_time:
            latest_time = recent.stat().st_mtime
            latest_folder = folder.name
    return latest_folder

## 3.8. Find most recent analyzed artwork
def latest_analyzed_artwork() -> dict | None:
    latest_time = 0
    latest_info = None
    for folder in ARTWORK_PROCESSED_DIR.iterdir():
        if not folder.is_dir():
            continue
        listing = folder / f"{folder.name}-listing.json"
        if not listing.exists():
            continue
        t = listing.stat().st_mtime
        if t > latest_time:
            latest_time = t
            try:
                with open(listing, "r", encoding="utf-8") as f:
                    data = json.load(f)
                latest_info = {
                    "aspect": data.get("aspect_ratio"),
                    "filename": data.get("filename"),
                }
            except Exception:
                continue
    return latest_info

# =========================================================
# SECTION 3.9: Description Text Combining & Cleaning
# =========================================================

## 3.9.1. Clean Display Text (Collapse Excess Newlines)
def clean_display_text(text: str) -> str:
    """
    Cleans a string for display by:
    - Stripping leading/trailing whitespace.
    - Collapsing any sequence of two or more newlines down to exactly two.
      (So there is never more than a single blank line between paragraphs.)
    """
    if not text:
        return ""
    # Strip all leading/trailing whitespace, including spaces and newlines
    cleaned = text.strip()
    # Replace sequences of 2 or more newlines with exactly two newlines (one blank line)
    cleaned = re.sub(r'\n{2,}', '\n\n', cleaned)
    return cleaned

## 3.9.2. Combine All Listing Parts for Display
def build_full_listing_text(ai_desc: str, generic_text: str) -> str:
    """
    Combines all listing description components for clean display.
    - Cleans each part individually.
    - Joins them with a standard double newline (paragraph break).
    - Cleans the final result again, ensuring no excess blank lines.
    """
    # Clean individual parts (avoids inherited trailing newlines)
    parts = [clean_display_text(ai_desc), clean_display_text(generic_text)]
    # Filter out empty sections
    combined = "\n\n".join([p for p in parts if p])
    # FINAL CLEAN: Collapse any accidental extra lines introduced by join
    return clean_display_text(combined)

# ========== SECTION 4. MAIN ROUTES ==========

# --- 4.1. Home and Artwork Gallery ---

@app.route("/")
def home():
    latest = latest_analyzed_artwork()
    return render_template("index.html", menu=get_menu(), latest_artwork=latest)

@app.route("/artworks")
def artworks():
    """Gallery page showing ready and processed artworks."""
    processed, processed_names = list_processed_artworks()
    ready = list_ready_to_analyze(processed_names)
    return render_template(
        "artworks.html",
        ready_artworks=ready,
        processed_artworks=processed,
        menu=get_menu(),
    )

# --- 4.2. Mockup Selector UI ---

@app.route("/select", methods=["GET", "POST"])
def select():
    if "slots" not in session or request.args.get("reset") == "1":
        init_slots()
    slots = session["slots"]
    options = compute_options(slots)
    zipped = list(zip(slots, options))
    return render_template("mockup_selector.html", zipped=zipped, menu=get_menu())

@app.route("/regenerate", methods=["POST"])
def regenerate():
    slot_idx = int(request.form["slot"])
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        cat = slots[slot_idx]["category"]
        slots[slot_idx]["image"] = random_image(cat)
        session["slots"] = slots
    return redirect(url_for("select"))

@app.route("/swap", methods=["POST"])
def swap():
    slot_idx = int(request.form["slot"])
    new_cat = request.form["new_category"]
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        slots[slot_idx]["category"] = new_cat
        slots[slot_idx]["image"] = random_image(new_cat)
        session["slots"] = slots
    return redirect(url_for("select"))

@app.route("/proceed", methods=["POST"])
def proceed():
    slots = session.get("slots", [])
    if not slots:
        flash("No mockups selected!", "danger")
        return redirect(url_for("select"))
    SELECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    selection_id = str(uuid.uuid4())
    selection_file = SELECTIONS_DIR / f"{selection_id}.json"
    with open(selection_file, "w") as f:
        json.dump(slots, f, indent=2)
    log_file = LOGS_DIR / f"composites_{selection_id}.log"
    try:
        result = subprocess.run(
            ["python3", str(GENERATE_SCRIPT_PATH), str(selection_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=BASE_DIR,
        )
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode == 0:
            flash("Composites generated successfully!", "success")
        else:
            flash("Composite generation failed. See logs for details.", "danger")
    except Exception as e:
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash("Error running the composite generator.", "danger")

    latest = latest_composite_folder()
    if latest:
        session["latest_seo_folder"] = latest
        logging.info("Generated composites for %s", latest)
        return redirect(url_for("composites_specific", seo_folder=latest))
    return redirect(url_for("composites_preview"))

# --- 4.3. Analyze & Generate Composites (Combined) ---

@app.route("/analyze/<aspect>/<filename>", methods=["POST"])
def analyze_artwork(aspect, filename):
    """
    1. Run AI artwork analysis (analyze_artwork.py)
    2. Trigger generate_composites.py immediately after
    3. Redirect to review page with listing & preview mockups
    """
    # === Run Analysis ===
    artwork_path = ARTWORKS_DIR / aspect / filename
    log_id = str(uuid.uuid4())
    log_file = LOGS_DIR / f"analyze_{log_id}.log"
    try:
        cmd = ["python3", str(ANALYZE_SCRIPT_PATH), str(artwork_path)]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash(f"❌ Analysis failed for {filename}: {result.stderr}", "danger")
            return redirect(url_for("artworks"))
    except Exception as e:
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash(f"❌ Error running analysis: {str(e)}", "danger")
        return redirect(url_for("artworks"))

    # === Find SEO folder just generated ===
    # Look for the folder in outputs/processed/ that matches the new listing
    original_basename = Path(filename).stem
    processed_root = ARTWORK_PROCESSED_DIR
    seo_folder = None
    for folder in processed_root.iterdir():
        if folder.is_dir():
            possible_json = folder / f"{folder.name}-listing.json"
            if possible_json.exists():
                with open(possible_json, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        if Path(data.get("filename", "")).stem == original_basename:
                            seo_folder = folder.name
                            break
                    except Exception:
                        continue
    if not seo_folder:
        flash("Analysis complete, but no SEO folder/listing found.", "warning")
        return redirect(url_for("artworks"))

    # === Run Composite Generation ===
    try:
        cmd = ["python3", str(GENERATE_SCRIPT_PATH), seo_folder]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=BASE_DIR, timeout=600)
        composite_log_file = LOGS_DIR / f"composite_gen_{log_id}.log"
        with open(composite_log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash("Artwork analyzed, but mockup generation failed. See logs.", "danger")
    except Exception as e:
        flash(f"Composites generation error: {e}", "danger")

    # === Redirect to review page showing both listing and preview mockups ===
    return redirect(url_for("review_artwork", aspect=aspect, filename=filename))

# =============================================================
# 4.4. REVIEW ARTWORK, PREVIEW MOCKUPS & AI LISTING [REFACTORED]
# =============================================================

from flask import (
    render_template, request, redirect, url_for, flash
)
from werkzeug.exceptions import NotFound
from pathlib import Path
import json
import random

# Assumed imports from your project structure:
# from yourproject.app import app  # <- Ensure this import points to your Flask app instance
# from yourproject.utils.image_tools import resize_image_for_long_edge, apply_perspective_transform
# from yourproject.constants import ARTWORK_PROCESSED_DIR, MOCKUPS_DIR, COORDS_ROOT, get_menu, get_categories, clean_display_text

# --------------------- 4.4a. SEO Folder Helper ---------------------
def find_seo_folder_from_filename(aspect, filename):
    """
    Locate the SEO-named folder matching the original or processed filename.
    """
    basename = Path(filename).stem
    for folder in ARTWORK_PROCESSED_DIR.iterdir():
        if not folder.is_dir():
            continue
        listing_file = folder / f"{folder.name}-listing.json"
        if not listing_file.exists():
            continue
        try:
            with open(listing_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            json_filename_stem = Path(data.get("filename", "")).stem
            if json_filename_stem == basename or folder.name == basename:
                return folder.name
        except Exception:
            continue
    raise NotFound(f"SEO folder not found for {filename}")

# -------------------- 4.4. Review Artwork Route ---------------------
@app.route("/review/<aspect>/<filename>")
def review_artwork(aspect, filename):
    """
    Review analyzed artwork: show AI-generated listing and preview composite mockups
    (with per-mockup regenerate and category swap UI).
    Always resolves correct SEO folder for listing, even if accessed via original filename.
    """
    # --- 4.4.1. Locate SEO folder or handle not found ---
    try:
        seo_folder = find_seo_folder_from_filename(aspect, filename)
    except NotFound:
        flash(f"Artwork not found: Could not locate SEO folder for '{filename}'", "danger")
        return render_template(
            "review_artwork.html",
            artwork={
                "seo_name": Path(filename).stem,
                "title": Path(filename).stem.replace("-", " ").title(),
                "main_image": filename,
                "thumb": f"{Path(filename).stem}-THUMB.jpg",
                "aspect": aspect,
                "missing": True,
                "tags": [],
                "materials": [],
                "primary_colour": "",
                "secondary_colour": "",
                "full_listing_text": "(No AI listing description found. Try re-analyzing.)"
            },
            mockup_previews=[],
            categories=[],
            ai_listing=None,
            ai_description="(No AI listing description found)",
            fallback_text=None,
            used_fallback_naming=False,
            generic_text="",
            raw_ai_output="",
            menu=get_menu(),
        )

    # --- 4.4.2. Load and parse listing JSON ---
    listing_path = ARTWORK_PROCESSED_DIR / seo_folder / f"{seo_folder}-listing.json"
    try:
        with open(listing_path, "r", encoding="utf-8") as f:
            listing_json = json.load(f)
    except Exception as e:
        app.logger.error(f"Error loading artwork {filename}: {e}")
        flash(f"Error loading artwork: {e}", "danger")
        return redirect(url_for("artworks"))

    # --- 4.4.3. Extract all fields for display ---
    ai_listing = listing_json.get("ai_listing", {})
    desc = ai_listing.get("description") if isinstance(ai_listing, dict) else (ai_listing if isinstance(ai_listing, str) else None)
    ai_title = ai_listing.get("title") if isinstance(ai_listing, dict) else None
    fallback_text = ai_listing.get("fallback_text") if isinstance(ai_listing, dict) else None
    if not desc and isinstance(ai_listing, dict):
        desc = ai_listing.get("fallback_text")
        fallback_text = desc
    if not desc:
        desc = listing_json.get("generic_text", "(No AI listing description found)")
    tags = listing_json.get("tags") or (ai_listing.get("tags", []) if isinstance(ai_listing, dict) else [])
    materials = listing_json.get("materials") or (ai_listing.get("materials", []) if isinstance(ai_listing, dict) else [])
    generic_text = listing_json.get("generic_text", "")

    # --- 4.4.4. Combine & clean description blocks ---
    full_listing_text = "\n\n".join(filter(None, [
        clean_display_text(desc) if desc else "",
        clean_display_text(generic_text) if generic_text else ""
    ]))

    # --- 4.4.5. Extract mockup previews, categories, and meta ---
    primary_colour = listing_json.get("primary_colour", "")
    secondary_colour = listing_json.get("secondary_colour", "")
    used_fallback_naming = bool(listing_json.get("used_fallback_naming", False))
    raw_ai_output = (
        json.dumps(ai_listing, indent=2, ensure_ascii=False)[:800]
        if isinstance(ai_listing, (dict, list))
        else str(ai_listing)[:800]
    )
    folder = ARTWORK_PROCESSED_DIR / seo_folder
    images = sorted(folder.glob(f"{seo_folder}-MU-*.jpg"))
    mockups_from_json = listing_json.get("mockups", []) if listing_json else []
    mockup_previews = []
    for idx, img in enumerate(images):
        cat = ""
        if idx < len(mockups_from_json):
            try:
                cat = Path(mockups_from_json[idx]).parent.name
            except Exception:
                cat = ""
        mockup_previews.append({
            "filename": img.name,
            "category": cat,
            "index": idx,
        })
    categories = get_categories()

    # --- 4.4.6. Build artwork dict for template ---
    artwork = {
        "seo_name": seo_folder,
        "title": ai_title or listing_json.get("title") or seo_folder.replace("-", " ").title(),
        "main_image": f"outputs/processed/{seo_folder}/{seo_folder}.jpg",
        "thumb": f"outputs/processed/{seo_folder}/{seo_folder}-THUMB.jpg",
        "aspect": aspect,
        "tags": tags,
        "materials": materials,
        "has_tags": bool(tags),
        "has_materials": bool(materials),
        "primary_colour": primary_colour,
        "secondary_colour": secondary_colour,
        "full_listing_text": full_listing_text,
    }

    # --- 4.4.7. Render review_artwork.html with context ---
    return render_template(
        "review_artwork.html",
        artwork=artwork,
        ai_listing=ai_listing,
        ai_description=desc,
        fallback_text=fallback_text,
        tags=tags,
        materials=materials,
        used_fallback_naming=used_fallback_naming,
        generic_text=generic_text,
        raw_ai_output=raw_ai_output,
        mockup_previews=mockup_previews,
        categories=categories,
        menu=get_menu(),
    )

# =============================================================
# 4.4b. REVIEW PAGE: INDIVIDUAL MOCKUP REGENERATE/SWAP ACTIONS
# =============================================================

## 4.4b.1. Regenerate a single mockup (same category)
def regenerate_one_mockup(seo_folder, slot_idx):
    folder = ARTWORK_PROCESSED_DIR / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    if not listing_file.exists():
        return False
    with open(listing_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    mockups = data.get("mockups", [])
    if slot_idx < 0 or slot_idx >= len(mockups):
        return False
    mockup_path = Path(mockups[slot_idx])
    category = mockup_path.parent.name
    mockup_files = list((MOCKUPS_DIR / category).glob("*.png"))
    if not mockup_files:
        return False
    new_mockup = random.choice(mockup_files)
    aspect = data.get("aspect_ratio")
    coords_path = COORDS_ROOT / aspect / f"{new_mockup.stem}.json"
    art_path = folder / f"{seo_folder}.jpg"
    output_path = folder / f"{seo_folder}-MU-{slot_idx+1:02d}.jpg"
    try:
        with open(coords_path, "r", encoding="utf-8") as cf:
            c = json.load(cf)["corners"]
        dst = [[c[0]["x"], c[0]["y"]], [c[1]["x"], c[1]["y"]], [c[3]["x"], c[3]["y"]], [c[2]["x"], c[2]["y"]]]
        art_img = Image.open(art_path).convert("RGBA")
        art_img = resize_image_for_long_edge(art_img)
        mock_img = Image.open(new_mockup).convert("RGBA")
        composite = apply_perspective_transform(art_img, mock_img, dst)
        composite.convert("RGB").save(output_path, "JPEG", quality=85)
        data["mockups"][slot_idx] = str(new_mockup)
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Regenerate error: {e}")
        return False

## 4.4b.2. Swap mockup to a new category and regenerate
def swap_one_mockup(seo_folder, slot_idx, new_category):
    folder = ARTWORK_PROCESSED_DIR / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    if not listing_file.exists():
        return False
    with open(listing_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    mockups = data.get("mockups", [])
    if slot_idx < 0 or slot_idx >= len(mockups):
        return False
    mockup_files = list((MOCKUPS_DIR / new_category).glob("*.png"))
    if not mockup_files:
        return False
    new_mockup = random.choice(mockup_files)
    aspect = data.get("aspect_ratio")
    coords_path = COORDS_ROOT / aspect / f"{new_mockup.stem}.json"
    art_path = folder / f"{seo_folder}.jpg"
    output_path = folder / f"{seo_folder}-MU-{slot_idx+1:02d}.jpg"
    try:
        with open(coords_path, "r", encoding="utf-8") as cf:
            c = json.load(cf)["corners"]
        dst = [[c[0]["x"], c[0]["y"]], [c[1]["x"], c[1]["y"]], [c[3]["x"], c[3]["y"]], [c[2]["x"], c[2]["y"]]]
        art_img = Image.open(art_path).convert("RGBA")
        art_img = resize_image_for_long_edge(art_img)
        mock_img = Image.open(new_mockup).convert("RGBA")
        composite = apply_perspective_transform(art_img, mock_img, dst)
        composite.convert("RGB").save(output_path, "JPEG", quality=85)
        data["mockups"][slot_idx] = str(new_mockup)
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Swap error: {e}")
        return False

## 4.4b.3. POST routes for Regenerate/Swap on Review Page
@app.route("/review/<aspect>/<filename>/regenerate/<int:slot_idx>", methods=["POST"])
def review_regenerate_mockup(aspect, filename, slot_idx):
    seo_folder = find_seo_folder_from_filename(aspect, filename)
    regenerate_one_mockup(seo_folder, slot_idx)
    return redirect(url_for("review_artwork", aspect=aspect, filename=filename))

@app.route("/review/<seo_folder>/swap/<int:slot_idx>", methods=["POST"])
def review_swap_mockup(seo_folder, slot_idx):
    new_cat = request.form["new_category"]
    swap_one_mockup(seo_folder, slot_idx, new_cat)
    # Reload context for redirect:
    listing_file = ARTWORK_PROCESSED_DIR / seo_folder / f"{seo_folder}-listing.json"
    if listing_file.exists():
        with open(listing_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        aspect = data.get("aspect_ratio", "")
        filename = (
            data.get("seo_filename")
            or data.get("filename")
            or f"{seo_folder}.jpg"
        )
        if not filename.lower().endswith(".jpg"):
            filename = f"{Path(filename).stem}.jpg"
    else:
        aspect = ""
        filename = f"{seo_folder}.jpg"
    return redirect(url_for("review_artwork", aspect=aspect, filename=filename))

# =============================================================
# 4.4.x Edit listing route
# =============================================================

@app.route("/edit-listing/<aspect>/<filename>", methods=["GET", "POST"])
def edit_listing(aspect, filename):
    try:
        seo_folder = find_seo_folder_from_filename(aspect, filename)
    except NotFound:
        flash(f"Artwork not found: Could not locate SEO folder for '{filename}'", "danger")
        return render_template(
            "edit_listing.html",
            artwork=None,
            message=f"SEO folder not found for {filename}",
            menu=get_menu(),
        )
    listing_path = ARTWORK_PROCESSED_DIR / seo_folder / f"{seo_folder}-listing.json"
    if not listing_path.exists():
        flash("Listing JSON not found.", "danger")
        return render_template(
            "edit_listing.html",
            artwork=None,
            message="Listing JSON not found.",
            menu=get_menu(),
        )
    # --- Load listing JSON ---
    with open(listing_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # --- Extract fields, with fallback logic for ai_listing/fallback_text ---
    artwork = {
        "seo_name": seo_folder,
        "main_image": f"outputs/processed/{seo_folder}/{seo_folder}.jpg",
        "thumb": f"outputs/processed/{seo_folder}/{seo_folder}-THUMB.jpg",
        "aspect": aspect,
        "primary_colour": data.get("primary_colour", ""),
        "secondary_colour": data.get("secondary_colour", ""),
        "tags": data.get("tags", []),
        "materials": data.get("materials", []),
    }
    # --- Robustly extract title/description/etc from ai_listing or fallback_text ---
    ai_listing = data.get("ai_listing", {})
    def extract_from_fallback(ai_listing):
        """Handle case where OpenAI fallback returns stringified JSON block."""
        import re, json
        if isinstance(ai_listing, dict) and "fallback_text" in ai_listing:
            fallback_text = ai_listing["fallback_text"]
            match = re.search(r'```json\s*({.*?})\s*```', fallback_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    return {}
        return {}

    # Merge AI listing data
    fields = ["title", "description", "tags", "materials", "primary_colour", "secondary_colour"]
    ai_data = {}
    if isinstance(ai_listing, dict):
        ai_data = {k: ai_listing.get(k) for k in fields}
        # Fallback: If key values are still empty, try fallback_text JSON
        fallback_ai = extract_from_fallback(ai_listing)
        for k in fields:
            if not ai_data.get(k) and fallback_ai.get(k):
                ai_data[k] = fallback_ai[k]
    elif isinstance(ai_listing, str):
        ai_data = {"description": ai_listing}

    # Fill in missing artwork fields with ai_data or data
    for k in fields:
        if k not in artwork or not artwork[k]:
            artwork[k] = ai_data.get(k) or data.get(k, "")

    # Provide a user-friendly message if still missing
    if not artwork.get("title"):
        artwork["title"] = seo_folder.replace("-", " ").title()
    if not artwork.get("description"):
        artwork["description"] = "(No description found. Try re-analyzing or check AI output.)"

    # Add full listing text for reference
    artwork["full_listing_text"] = build_full_listing_text(
        artwork.get("description", ""), data.get("generic_text", "")
    )

    return render_template(
        "edit_listing.html",
        artwork=artwork,
        menu=get_menu(),
        message="",
    )


# =============================================================
# 4.5. STATIC & UTILITY ROUTES
# =============================================================

@app.route("/static/outputs/processed/<seo_folder>/<filename>")
def processed_image(seo_folder, filename):
    folder = ARTWORK_PROCESSED_DIR / seo_folder
    return send_from_directory(folder, filename)

@app.route("/artwork-img/<aspect>/<filename>")
def artwork_image(aspect, filename):
    folder = ARTWORKS_DIR / aspect
    return send_from_directory(str(folder.resolve()), filename)

@app.route("/mockup-img/<category>/<filename>")
def mockup_img(category, filename):
    return send_from_directory(MOCKUPS_DIR / category, filename)

@app.route("/composite-img/<folder>/<filename>")
def composite_img(folder, filename):
    return send_from_directory(COMPOSITES_DIR / folder, filename)

# =============================================================
# 5. MENU FUNCTION
# =============================================================

def get_menu():
    """
    SECTION 5: Returns a list of dicts for navigation.
    - Home: Always present
    - Artwork Gallery: Always present
    - Review Latest Listing: Only enabled if there is a latest artwork
    """
    menu = [
        {"name": "Home", "url": url_for("home")},
        {"name": "Artwork Gallery", "url": url_for("artworks")},
    ]
    latest = latest_analyzed_artwork()
    if latest:
        menu.append({
            "name": "Review Latest Listing",
            "url": url_for("review_artwork", aspect=latest["aspect"], filename=latest["filename"])
        })
    else:
        menu.append({
            "name": "Review Latest Listing",
            "url": None
        })
    return menu

# =============================================================
# SECTION X: Artwork Listing Helpers
# =============================================================

def prettify_slug(slug: str) -> str:
    """Return a human friendly title from a slug or filename."""
    name = os.path.splitext(slug)[0]
    name = name.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name)
    return name.title()


def list_processed_artworks() -> tuple[list[dict], set[str]]:
    """Collect processed artworks and a set of their original filenames."""
    items: list[dict] = []
    processed_names: set[str] = set()
    for folder in ARTWORK_PROCESSED_DIR.iterdir():
        if not folder.is_dir():
            continue
        listing_path = folder / f"{folder.name}-listing.json"
        if not listing_path.exists():
            continue
        try:
            with open(listing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        original_name = data.get("filename")
        if original_name:
            processed_names.add(original_name)
        items.append(
            {
                "seo_folder": folder.name,
                "filename": original_name or f"{folder.name}.jpg",
                "aspect": data.get("aspect_ratio", ""),
                "title": data.get("title") or prettify_slug(folder.name),
                "thumb": f"{folder.name}-THUMB.jpg",
            }
        )
    items.sort(key=lambda x: x["title"].lower())
    return items, processed_names


def list_ready_to_analyze(processed_names: set[str]) -> list[dict]:
    """Return artworks present in inputs/ that are not yet processed."""
    ready: list[dict] = []
    for aspect_dir in ARTWORKS_DIR.iterdir():
        if not aspect_dir.is_dir():
            continue
        aspect = aspect_dir.name
        for img_path in sorted(aspect_dir.glob("*.jpg")):
            if img_path.name in processed_names:
                continue
            try:
                with Image.open(img_path) as im:
                    im.verify()
            except Exception:
                # Corrupted or unreadable image; skip gracefully
                continue
            ready.append(
                {
                    "aspect": aspect,
                    "filename": img_path.name,
                    "title": prettify_slug(img_path.stem),
                    "thumb": img_path.name,
                }
            )
    ready.sort(key=lambda x: x["title"].lower())
    return ready

# =============================================================
# 6. APP RUNNER
# =============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "true").lower() == "true"
    print(f"\U0001f3a8 Starting CapitalArt UI at http://0.0.0.0:{port}/ ...")
    app.run(debug=debug, host="0.0.0.0", port=port)

@app.route("/healthz")
def healthz():
    return "OK"
```

---
## 📄 capitalart-total-rundown.py

```py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ===========================================
# 🔥 CapitalArt Total Nuclear Snapshot v2
# 🚀 Ultimate Dev Toolkit by Robbie Mode™
# All errors & output logged to DEV_LOGS_DIR/snapshot-YYYY-MM-DD-HHMMSS.log
#
# USAGE EXAMPLES:
#   python3 capitalart-total-rundown.py
#   python3 capitalart-total-rundown.py --no-zip
#   python3 capitalart-total-rundown.py --skip-git --skip-env
# ===========================================

import os
import sys
import datetime
import subprocess
import zipfile
import py_compile
from pathlib import Path
from typing import Generator
import argparse
import traceback

from config import DEV_LOGS_DIR

# -------------------------------------------
# Config
ALLOWED_EXTENSIONS = {".py", ".sh", ".jsx", ".txt", ".html", ".js", ".css"}
EXCLUDED_EXTENSIONS = {".json"}
EXCLUDED_FOLDERS = {
    "venv",
    ".venv",
    "__MACOSX",
    ".git",
    ".vscode",
    "reports",
    "backups",
    "node_modules",
    ".idea",
}
EXCLUDED_FILES = {".DS_Store"}
LOGS_DIR = DEV_LOGS_DIR
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOGS_DIR / f"snapshot-{datetime.datetime.now():%Y-%m-%d-%H%M%S}.log"


def log(msg):
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as logf:
        logf.write(f"{datetime.datetime.now():[%Y-%m-%d %H:%M:%S]} {msg}\n")


def log_error(msg):
    print(f"\033[91m{msg}\033[0m")  # Red in terminal
    with open(LOG_PATH, "a", encoding="utf-8") as logf:
        logf.write(f"{datetime.datetime.now():[%Y-%m-%d %H:%M:%S]} ERROR: {msg}\n")


# -------------------------------------------
def get_timestamp() -> str:
    return datetime.datetime.now().strftime("REPORTS-%d-%b-%Y-%I-%M%p").upper()


def create_reports_folder() -> Path:
    timestamp = get_timestamp()
    folder_path = Path("reports") / timestamp
    folder_path.mkdir(parents=True, exist_ok=True)
    log(f"📁 Created report folder: {folder_path}")
    return folder_path


def get_included_files() -> Generator[Path, None, None]:
    for path in Path(".").rglob("*"):
        if (
            path.is_file()
            and path.suffix in ALLOWED_EXTENSIONS
            and path.suffix not in EXCLUDED_EXTENSIONS
            and path.name not in EXCLUDED_FILES
            and not any(str(part).lower() in EXCLUDED_FOLDERS for part in path.parts)
        ):
            try:
                path.stat()  # skip broken symlink etc.
                yield path
            except Exception:
                continue


def gather_code_snapshot(folder: Path) -> Path:
    md_path = folder / f"report_code_snapshot_{folder.name.lower()}.md"
    with open(md_path, "w", encoding="utf-8") as md_file:
        md_file.write(f"# 🧠 CapitalArt Code Snapshot — {folder.name}\n\n")
        for file in get_included_files():
            rel_path = file.relative_to(Path("."))
            log(f"📄 Including file: {rel_path}")
            md_file.write(f"\n---\n## 📄 {rel_path}\n\n```{file.suffix[1:]}\n")
            try:
                with open(file, "r", encoding="utf-8") as f:
                    md_file.write(f.read())
            except Exception as e:
                md_file.write(f"[ERROR READING FILE: {e}]")
            md_file.write("\n```\n")
    log(f"✅ Code snapshot saved to: {md_path}")
    return md_path


def generate_file_summary(folder: Path) -> None:
    summary_path = folder / "file_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# 📊 File Summary\n\n")
        f.write("| File | Size (KB) | Last Modified |\n")
        f.write("|------|------------|----------------|\n")
        for file in get_included_files():
            try:
                size_kb = round(file.stat().st_size / 1024, 1)
                mtime = datetime.datetime.fromtimestamp(file.stat().st_mtime)
                rel = file.relative_to(Path("."))
                f.write(f"| `{rel}` | {size_kb} KB | {mtime:%Y-%m-%d %H:%M} |\n")
            except Exception:
                continue
    log(f"📋 File summary written to: {summary_path}")


def validate_python_files() -> None:
    log("\n🧪 Validating Python syntax...")
    for file in get_included_files():
        if file.suffix == ".py":
            try:
                py_compile.compile(file, doraise=True)
                log(f"✅ {file}")
            except py_compile.PyCompileError as e:
                log_error(f"❌ {file} → {e.msg}")


def log_git_status(folder: Path) -> None:
    git_path = folder / "git_snapshot.txt"
    try:
        with open(git_path, "w", encoding="utf-8") as f:
            f.write("🔧 Git Status:\n")
            subprocess.run(
                ["git", "status"], stdout=f, stderr=subprocess.STDOUT, check=False
            )
            f.write("\n🔁 Last Commit:\n")
            subprocess.run(
                ["git", "log", "-1"], stdout=f, stderr=subprocess.STDOUT, check=False
            )
            f.write("\n🧾 Diff Summary:\n")
            subprocess.run(
                ["git", "diff", "--stat"],
                stdout=f,
                stderr=subprocess.STDOUT,
                check=False,
            )
        log(f"📘 Git snapshot written to: {git_path}")
    except Exception as e:
        log_error(f"Could not write git snapshot: {e}")


def log_environment_details(folder: Path) -> None:
    env_path = folder / "env_metadata.txt"
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("🐍 Python Version:\n")
            subprocess.run(
                ["python3", "--version"],
                stdout=f,
                stderr=subprocess.STDOUT,
                check=False,
            )
            f.write("\n🖥️ Platform Info:\n")
            if sys.platform != "win32":
                subprocess.run(
                    ["uname", "-a"], stdout=f, stderr=subprocess.STDOUT, check=False
                )
            f.write("\n📦 Installed Packages:\n")
            subprocess.run(
                ["pip", "freeze"], stdout=f, stderr=subprocess.STDOUT, check=False
            )
        log(f"📚 Environment metadata saved to: {env_path}")
    except Exception as e:
        log_error(f"Failed environment details: {e}")


def show_dependency_issues() -> None:
    log("\n🔍 Running pip check...")
    try:
        subprocess.run(["pip", "check"])
        log("\n📦 Outdated packages:")
        subprocess.run(["pip", "list", "--outdated"])
    except Exception as e:
        log_error(f"pip not found or check failed: {e}")


def zip_report_folder(folder: Path) -> Path:
    zip_path = folder.with_suffix(".zip")
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in folder.rglob("*"):
                zipf.write(file, file.relative_to(folder.parent))
        log(f"📦 Report zipped to: {zip_path}")
        return zip_path
    except Exception as e:
        log_error(f"Zipping report failed: {e}")
        return zip_path


def parse_args():
    parser = argparse.ArgumentParser(description="CapitalArt Dev Snapshot Generator")
    parser.add_argument(
        "--no-zip", action="store_true", help="Skip ZIP archive creation"
    )
    parser.add_argument(
        "--skip-env", action="store_true", help="Skip environment metadata logging"
    )
    parser.add_argument(
        "--skip-validate", action="store_true", help="Skip Python syntax validation"
    )
    parser.add_argument(
        "--skip-git", action="store_true", help="Skip Git snapshot logging"
    )
    parser.add_argument(
        "--skip-pip-check", action="store_true", help="Skip pip dependency checks"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    log("🎨 Generating CapitalArt Total Nuclear Snapshot (v2.1)...")
    try:
        report_folder = create_reports_folder()
        try:
            gather_code_snapshot(report_folder)
        except Exception as e:
            log_error(f"Code snapshot failed: {traceback.format_exc()}")
        try:
            generate_file_summary(report_folder)
        except Exception as e:
            log_error(f"File summary failed: {traceback.format_exc()}")
        if not args.skip_validate:
            try:
                validate_python_files()
            except Exception as e:
                log_error(f"Python validation failed: {traceback.format_exc()}")
        if not args.skip_env:
            try:
                log_environment_details(report_folder)
            except Exception as e:
                log_error(f"Env details failed: {traceback.format_exc()}")
        if not args.skip_git:
            try:
                log_git_status(report_folder)
            except Exception as e:
                log_error(f"Git snapshot failed: {traceback.format_exc()}")
        if not args.skip_pip_check:
            try:
                show_dependency_issues()
            except Exception as e:
                log_error(f"Pip checks failed: {traceback.format_exc()}")
        if not args.no_zip:
            try:
                zip_report_folder(report_folder)
            except Exception as e:
                log_error(f"Zip step failed: {traceback.format_exc()}")
        log("✅ Snapshot complete. All systems green, Robbie! 💚")
    except Exception as e:
        log_error(f"Top-level script failure: {traceback.format_exc()}")


if __name__ == "__main__":
    main()

```

---
## 📄 config.py

```py
"""Central configuration for the CapitalArt project.

This module defines all folder paths, filename templates, allowed
extensions, image sizes and other parameters used across the codebase.
Values can be overridden using environment variables of the same name.

Update paths here rather than hard-coding them elsewhere. All modules
should import settings from ``config`` so behaviour automatically adapts
when directory names or limits change. Every value can be overridden by an
environment variable of the same name which allows for per-user or
deployment specific customisation via ``.env`` files.

Critical folders are created on import. If creation fails an explicit
``RuntimeError`` is raised. Edit this file or set env vars to tweak folder
names, extensions or limits rather than updating code elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Project Root -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CONFIG_VERSION = "1.2.0"

# --- Input/Output Folders ---------------------------------------------------
ARTWORKS_INPUT_DIR = Path(
    os.getenv("ARTWORKS_INPUT_DIR", BASE_DIR / "inputs" / "artworks")
)
MOCKUPS_INPUT_DIR = Path(
    os.getenv("MOCKUPS_INPUT_DIR", BASE_DIR / "inputs" / "mockups")
)
MOCKUPS_CATEGORISED_DIR = Path(
    os.getenv("MOCKUPS_CATEGORISED_DIR", MOCKUPS_INPUT_DIR / "4x5-categorised")
)
ARTWORKS_PROCESSED_DIR = Path(
    os.getenv("ARTWORKS_PROCESSED_DIR", BASE_DIR / "outputs" / "processed")
)
ARTWORKS_FINALISED_DIR = Path(
    os.getenv("ARTWORKS_FINALISED_DIR", BASE_DIR / "outputs" / "finalised-artwork")
)
COMPOSITES_DIR = Path(os.getenv("COMPOSITES_DIR", BASE_DIR / "outputs" / "composites"))
SELECTIONS_DIR = Path(os.getenv("SELECTIONS_DIR", BASE_DIR / "outputs" / "selections"))
THUMBNAILS_DIR = Path(os.getenv("THUMBNAILS_DIR", BASE_DIR / "outputs" / "thumbnails"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", BASE_DIR / "logs"))
DEV_LOGS_DIR = Path(os.getenv("DEV_LOGS_DIR", BASE_DIR / "dev-logs"))
PARSE_FAILURE_DIR = Path(os.getenv("PARSE_FAILURE_DIR", LOGS_DIR / "parse_failures"))
OPENAI_PROMPT_LOG_DIR = Path(
    os.getenv("OPENAI_PROMPT_LOG_DIR", LOGS_DIR / "openai_prompts")
)
OPENAI_RESPONSE_LOG_DIR = Path(
    os.getenv("OPENAI_RESPONSE_LOG_DIR", LOGS_DIR / "openai_responses")
)
GIT_LOG_DIR = Path(os.getenv("GIT_LOG_DIR", BASE_DIR / "git-update-push-logs"))
SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", BASE_DIR / "scripts"))
SIGNATURES_DIR = Path(os.getenv("SIGNATURES_DIR", BASE_DIR / "inputs" / "signatures"))
GENERIC_TEXTS_DIR = Path(os.getenv("GENERIC_TEXTS_DIR", BASE_DIR / "generic_texts"))
UPLOADS_TEMP_DIR = Path(os.getenv("UPLOADS_TEMP_DIR", BASE_DIR / "uploads_temp"))
COORDS_DIR = Path(os.getenv("COORDS_DIR", BASE_DIR / "inputs" / "Coordinates"))
TMP_DIR = Path(os.getenv("TMP_DIR", BASE_DIR / "tmp" / "ai_input_images"))
SELLBRITE_OUTPUT_DIR = Path(
    os.getenv("SELLBRITE_OUTPUT_DIR", BASE_DIR / "outputs" / "sellbrite")
)
SELLBRITE_TEMPLATE_CSV = Path(
    os.getenv("SELLBRITE_TEMPLATE_CSV", BASE_DIR / "csv_product_template.csv")
)

# Additional general file locations
ONBOARDING_PATH = Path(
    os.getenv(
        "ONBOARDING_PATH",
        BASE_DIR
        / "settings"
        / "Master-Etsy-Listing-Description-Writing-Onboarding.txt",
    )
)
OUTPUT_JSON = Path(
    os.getenv("OUTPUT_JSON", BASE_DIR / "outputs" / "artwork_listing_master.json")
)
OUTPUT_PROCESSED_ROOT = ARTWORKS_PROCESSED_DIR

# Paths to helper scripts used by various workflows
ANALYZE_SCRIPT_PATH = Path(
    os.getenv("ANALYZE_SCRIPT_PATH", SCRIPTS_DIR / "analyze_artwork.py")
)
GENERATE_SCRIPT_PATH = Path(
    os.getenv("GENERATE_SCRIPT_PATH", SCRIPTS_DIR / "generate_composites.py")
)

# --- Filename Templates -----------------------------------------------------
FILENAME_TEMPLATES = {
    "artwork": "{seo_slug}.jpg",
    "mockup": "{seo_slug}-MU-{num:02d}.jpg",
    "thumbnail": "{seo_slug}-THUMB.jpg",
    "analyse": "{seo_slug}-ANALYSE.jpg",
    "listing_json": "{seo_slug}-listing.json",
    "qc_json": "{seo_slug}.qc.json",
}

# --- Allowed Extensions & Sizes --------------------------------------------
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png").split(","))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "32"))
ANALYSE_MAX_DIM = int(os.getenv("ANALYSE_MAX_DIM", "2400"))
ANALYSE_MAX_MB = int(os.getenv("ANALYSE_MAX_MB", "1"))

# --- Image Dimensions -------------------------------------------------------
THUMB_WIDTH = int(os.getenv("THUMB_WIDTH", "400"))
THUMB_HEIGHT = int(os.getenv("THUMB_HEIGHT", "400"))


# --- Mockup Categories ------------------------------------------------------
def get_mockup_categories() -> list[str]:
    override = os.getenv("MOCKUP_CATEGORIES")
    if override:
        return [c.strip() for c in override.split(",") if c.strip()]
    if MOCKUPS_CATEGORISED_DIR.exists():
        return sorted(
            [
                f.name
                for f in MOCKUPS_CATEGORISED_DIR.iterdir()
                if f.is_dir() and f.name.lower() != "uncategorised"
            ]
        )
    return []


MOCKUP_CATEGORIES = get_mockup_categories()

# --- Signature Settings -----------------------------------------------------
SIGNATURE_SIZE_PERCENTAGE = float(os.getenv("SIGNATURE_SIZE_PERCENTAGE", "0.05"))
SIGNATURE_MARGIN_PERCENTAGE = float(os.getenv("SIGNATURE_MARGIN_PERCENTAGE", "0.03"))

# --- SKU Tracking -----------------------------------------------------------
SKU_TRACKER = Path(
    os.getenv("SKU_TRACKER_PATH", BASE_DIR / "settings" / "sku_tracker.json")
)

# File used by the web UI to report progress of analysis jobs
ANALYSIS_STATUS_FILE = Path(
    os.getenv("ANALYSIS_STATUS_FILE", LOGS_DIR / "analysis_status.json")
)

# --- API Keys ---------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Additional Script Paths and Outputs -----------------------------------
PATCHES_DIR = Path(os.getenv("PATCHES_DIR", BASE_DIR / "patches"))
PATCH_INPUT = Path(os.getenv("PATCH_INPUT", BASE_DIR / "copy-git-apply.txt"))
# Output location for signed artworks generated by utilities
SIGNED_OUTPUT_DIR = Path(
    os.getenv("SIGNED_OUTPUT_DIR", BASE_DIR / "outputs" / "signed")
)
# Log file for the mockup categoriser script
MOCKUP_CATEGORISATION_LOG = Path(
    os.getenv("MOCKUP_CATEGORISATION_LOG", BASE_DIR / "mockup_categorisation_log.txt")
)

# Midjourney sorting helper defaults
MIDJOURNEY_CSV_PATH = Path(
    os.getenv("MIDJOURNEY_CSV_PATH", BASE_DIR / "inputs" / "autojourney.csv")
)
MIDJOURNEY_INPUT_DIR = Path(
    os.getenv("MIDJOURNEY_INPUT_DIR", BASE_DIR / "inputs" / "midjourney")
)
MIDJOURNEY_OUTPUT_DIR = Path(
    os.getenv("MIDJOURNEY_OUTPUT_DIR", BASE_DIR / "outputs" / "midjourney_sorted")
)
MIDJOURNEY_METADATA_CSV = Path(
    os.getenv(
        "MIDJOURNEY_METADATA_CSV",
        MIDJOURNEY_OUTPUT_DIR / "capitalart_image_metadata.csv",
    )
)

# --- Ensure Critical Folders Exist -----------------------------------------
for folder in [
    ARTWORKS_INPUT_DIR,
    MOCKUPS_INPUT_DIR,
    ARTWORKS_PROCESSED_DIR,
    LOGS_DIR,
    DEV_LOGS_DIR,
    PARSE_FAILURE_DIR,
    OPENAI_PROMPT_LOG_DIR,
    OPENAI_RESPONSE_LOG_DIR,
    GIT_LOG_DIR,
    PATCHES_DIR,
    SIGNED_OUTPUT_DIR,
    SELLBRITE_OUTPUT_DIR,
    UPLOADS_TEMP_DIR,
]:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - simple safety
        raise RuntimeError(f"Could not create required folder {folder}: {exc}")

```

---
## 📄 requirements.txt

```txt
annotated-types==0.7.0
anyio==4.9.0
blinker==1.9.0
certifi==2025.6.15
charset-normalizer==3.4.2
click==8.2.1
distro==1.9.0
Flask==3.1.1
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.10
itsdangerous==2.2.0
Jinja2==3.1.6
jiter==0.10.0
joblib==1.5.1
markdown-it-py==3.0.0
MarkupSafe==3.0.2
mdurl==0.1.2
numpy==2.3.1
openai==1.93.0
opencv-python==4.11.0.86
pandas==2.3.0
pillow==11.2.1
pydantic==2.11.7
pydantic_core==2.33.2
Pygments==2.19.2
python-dateutil==2.9.0.post0
python-dotenv==1.1.1
pytz==2025.2
requests==2.32.4
rich==14.0.0
scikit-learn==1.7.0
scipy==1.16.0
six==1.17.0
sniffio==1.3.1
threadpoolctl==3.6.0
tqdm==4.67.1
typing-inspection==0.4.1
typing_extensions==4.14.0
tzdata==2025.2
urllib3==2.5.0
Werkzeug==3.1.3
gunicorn
```

---
## 📄 mockup_categoriser.py

```py
# ============================== [ mockup_categoriser.py ] ==============================
# Bulk AI-based mockup categorisation script for CapitalArt Mockup Generator
# --------------------------------------------------------------------------------------
# Uses OpenAI GPT-4.1 (fallback to GPT-4o / Turbo) via .env-configured key
# Categorises mockups from 4x5 folder into detected or predefined categories
# Moves files into categorised folders under `4x5-categorised/`
# Logs results to mockup_categorisation_log.txt
# ======================================================================================

import os
import shutil
import time
import base64
from dotenv import load_dotenv
from openai import OpenAI
from config import (
    OPENAI_API_KEY,
    MOCKUPS_INPUT_DIR,
    MOCKUPS_CATEGORISED_DIR,
    MOCKUP_CATEGORISATION_LOG,
)

# ============================== [ 1. CONFIG & CONSTANTS ] ==============================

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-4.1")
FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4-turbo")

client = OpenAI(api_key=OPENAI_API_KEY)

MOCKUP_INPUT_FOLDER = MOCKUPS_INPUT_DIR / "4x5"
MOCKUP_OUTPUT_BASE = MOCKUPS_CATEGORISED_DIR
LOG_FILE = str(MOCKUP_CATEGORISATION_LOG)

# Dynamically detect valid category folders (ignoring 'Uncategorised')
def detect_valid_categories():
    if not os.path.exists(MOCKUP_OUTPUT_BASE):
        return []
    return [
        folder for folder in os.listdir(MOCKUP_OUTPUT_BASE)
        if os.path.isdir(os.path.join(MOCKUP_OUTPUT_BASE, folder)) and folder.lower() != "uncategorised"
    ]

# ============================== [ 2. HELPER FUNCTIONS ] ==============================

def create_category_folders(categories):
    for category in categories:
        folder_path = os.path.join(MOCKUP_OUTPUT_BASE, category)
        os.makedirs(folder_path, exist_ok=True)

def log_result(filename: str, category: str):
    with open(LOG_FILE, "a") as f:
        f.write(f"{filename} -> {category}\n")

def move_file_to_category(file_path: str, category: str):
    dest_folder = os.path.join(MOCKUP_OUTPUT_BASE, category)
    os.makedirs(dest_folder, exist_ok=True)
    shutil.move(file_path, os.path.join(dest_folder, os.path.basename(file_path)))

def is_image(filename: str) -> bool:
    return filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))

def encode_image_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# ============================== [ 3. OPENAI ANALYSIS ] ==============================

def analyse_mockup(file_path: str, valid_categories: list) -> str:
    try:
        encoded_image = encode_image_to_base64(file_path)

        system_prompt = (
            "You are an expert AI assistant helping a professional digital artist organise mockup preview images. "
            "You will receive one image at a time, and your job is to classify it into one of the following categories:\n\n"
            f"{', '.join(valid_categories)}\n\n"
            "These images depict digital artworks displayed in styled rooms. Only respond with the *exact* category name. "
            "If unsure, choose the closest appropriate category based on furniture, lighting, layout or wall style. "
            "No explanations, just return the category string."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encoded_image}"
                        }
                    }
                ]
            }
        ]

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=20,
            temperature=0
        )

        category = response.choices[0].message.content.strip()
        if category not in valid_categories:
            raise ValueError(f"Returned category '{category}' is not valid.")
        return category

    except Exception as e:
        print(f"[ERROR] {os.path.basename(file_path)}: {e}")
        return "Uncategorised"

# ============================== [ 4. MAIN EXECUTION ] ==============================

def main():
    print("🔍 Starting mockup categorisation...")

    valid_categories = detect_valid_categories()
    if not valid_categories:
        print("⚠️ No valid category folders found. Please create them first.")
        return

    create_category_folders(valid_categories)

    images = [f for f in os.listdir(MOCKUP_INPUT_FOLDER) if is_image(f)]

    for image_name in images:
        image_path = os.path.join(MOCKUP_INPUT_FOLDER, image_name)
        print(f"→ Analysing {image_name}...")
        category = analyse_mockup(image_path, valid_categories)
        move_file_to_category(image_path, category)
        log_result(image_name, category)
        time.sleep(1.5)

    print("✅ All mockups categorised and moved successfully.")

# ============================== [ 5. ENTRY POINT ] ==============================

if __name__ == "__main__":
    main()

```

---
## 📄 run_codex_patch.py

```py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Run: python3 run_codex_patch.py

"""
run_codex_patch.py
---------------------------------------------------
Apply Codex-generated patch stored in copy-git-apply.txt
and log all activity. Handles patch file generation, logs,
and cleanup. No prompts.
"""

import os
import subprocess
from datetime import datetime
import shutil
import sys

from config import BASE_DIR, PATCHES_DIR, LOGS_DIR, PATCH_INPUT

# === [1. PATHS & SETUP] ===

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
patch_file = PATCHES_DIR / f"codex_patch_{timestamp}.patch"
log_file = LOGS_DIR / f"patch-log-{timestamp}.txt"

# === [2. CLEAN PATCH TEXT] ===

def extract_clean_patch(text: str) -> str:
    """Extract valid patch lines from heredoc if present."""
    if "<<'EOF'" in text:
        text = text.split("<<'EOF'")[-1].split("EOF")[0]
    lines = text.strip().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("diff --git"):
            return "\n".join(lines[i:]).strip()
    return ""

# === [3. READ PATCH FILE] ===

if not PATCH_INPUT.exists():
    print(f"❌ Error: Patch file not found: {PATCH_INPUT}")
    sys.exit(1)

with PATCH_INPUT.open("r", encoding="utf-8") as f:
    raw_patch = f.read()

clean_patch = extract_clean_patch(raw_patch)

if not clean_patch:
    print("❌ Error: No valid patch content found.")
    with log_file.open("w", encoding="utf-8") as log:
        log.write("❌ No valid patch content found.\n")
        log.write("=== Raw Input ===\n")
        log.write(raw_patch)
    sys.exit(1)

patch_file.write_text(clean_patch, encoding="utf-8")

# === [4. APPLY PATCH] ===

try:
    print("📦 Stashing current changes...")
    subprocess.run(["git", "stash", "push", "-m", "pre Codex task updates"], cwd=BASE_DIR, check=True)

    print(f"🧩 Applying patch: {patch_file.name}")
    result = subprocess.run(
        ["git", "apply", "--3way", str(patch_file)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )

    with log_file.open("w", encoding="utf-8") as log:
        log.write("=== GIT PATCH APPLY LOG ===\n")
        log.write(f"Patch file: {patch_file}\n")
        log.write(f"Return Code: {result.returncode}\n\n")
        log.write("=== STDOUT ===\n")
        log.write(result.stdout or "(no output)\n")
        log.write("\n=== STDERR ===\n")
        log.write(result.stderr or "(no errors)\n")

        if result.returncode != 0:
            log.write("\n=== GIT STATUS ===\n")
            status = subprocess.run(["git", "status"], cwd=BASE_DIR, capture_output=True, text=True)
            log.write(status.stdout)

    if result.returncode == 0:
        print(f"✅ Patch applied successfully.")
    else:
        print(f"❌ Patch failed! See log: {log_file}")

except Exception as e:
    print(f"💥 Unexpected error: {e}")
    with log_file.open("a", encoding="utf-8") as log:
        log.write(f"\n\n=== Exception ===\n{str(e)}")

```

---
## 📄 smart_sign_artwork.py

```py
"""Batch-sign artworks with colour-contrasting signatures."""

import os
from pathlib import Path
import random
import math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
from sklearn.cluster import KMeans
from config import (
    SIGNATURES_DIR,
    ARTWORKS_INPUT_DIR,
    SIGNATURE_SIZE_PERCENTAGE,
    SIGNATURE_MARGIN_PERCENTAGE,
    SIGNED_OUTPUT_DIR,
)

# === [ CapitalArt Lite: CONFIGURATION ] ===
# Paths can be set via environment variables for portability.

# The directory where sorted artworks are located.
INPUT_IMAGE_DIR = ARTWORKS_INPUT_DIR
OUTPUT_SIGNED_DIR = SIGNED_OUTPUT_DIR
SIGNATURE_DIR = SIGNATURES_DIR

# Ensure required directories exist
Path(OUTPUT_SIGNED_DIR).mkdir(parents=True, exist_ok=True)

# Dictionary mapping logical color names to the full path of each signature PNG.
# Ensure these paths exactly match your file system.
SIGNATURE_PNGS = {
    "beige": Path(SIGNATURE_DIR) / "beige.png",
    "black": Path(SIGNATURE_DIR) / "black.png",
    "blue": Path(SIGNATURE_DIR) / "blue.png",
    "brown": Path(SIGNATURE_DIR) / "brown.png",
    "gold": Path(SIGNATURE_DIR) / "gold.png",
    "green": Path(SIGNATURE_DIR) / "green.png",
    "grey": Path(SIGNATURE_DIR) / "grey.png",
    "odd": Path(SIGNATURE_DIR) / "odd.png", # Placeholder, adjust RGB if needed
    "red": Path(SIGNATURE_DIR) / "red.png",
    "skyblue": Path(SIGNATURE_DIR) / "skyblue.png",
    "white": Path(SIGNATURE_DIR) / "white.png",
    "yellow": Path(SIGNATURE_DIR) / "yellow.png"
}

# Representative RGB values for each signature color for contrast calculation.
# These are approximations. You might adjust them for more accuracy if needed.
SIGNATURE_COLORS_RGB = {
    "beige": (245, 245, 220),
    "black": (0, 0, 0),
    "blue": (0, 0, 255),
    "brown": (139, 69, 19),
    "gold": (255, 215, 0),
    "green": (0, 255, 0),
    "grey": (128, 128, 128),
    "odd": (128, 128, 128), # Treat as a mid-grey for contrast if actual color is unknown/variable
    "red": (255, 0, 0),
    "skyblue": (135, 206, 235),
    "white": (210, 210, 210),
    "yellow": (255, 255, 0)
}

SMOOTHING_BUFFER_PIXELS = 3 # Extra pixels around the signature shape for smoothing
BLUR_RADIUS = 25 # Adjust for desired blur intensity of the smoothed patch (increased for more blend)
NUM_COLORS_FOR_ZONE_ANALYSIS = 2 # How many dominant colors to find in the signature zone for smoothing

# === [ CapitalArt Lite: UTILITY FUNCTIONS ] ===

def get_relative_luminance(rgb):
    """Calculates the relative luminance of an RGB color, per WCAG 2.0."""
    r, g, b = [x / 255.0 for x in rgb]
    
    # Apply gamma correction
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def get_contrast_ratio(rgb1, rgb2):
    """Calculates the WCAG contrast ratio between two RGB colors."""
    L1 = get_relative_luminance(rgb1)
    L2 = get_relative_luminance(rgb2)
    
    if L1 > L2:
        return (L1 + 0.05) / (L2 + 0.05)
    else:
        return (L2 + 0.05) / (L1 + 0.05)

def get_dominant_color_in_masked_zone(image_data_pixels, mask_pixels, num_colors=1):
    """
    Finds the most dominant color(s) within the part of the image
    that corresponds to the opaque areas of the mask.
    `image_data_pixels` should be a flat list of (R,G,B) tuples.
    `mask_pixels` should be a flat list of alpha values (0-255).
    """
    
    # Filter pixels from the image that are within the opaque part of the mask
    # We assume mask_pixels and image_data_pixels are aligned
    masked_pixels = []
    for i in range(len(mask_pixels)):
        if mask_pixels[i] > 0: # Check if the mask pixel is not fully transparent
            masked_pixels.append(image_data_pixels[i])
            
    if not masked_pixels:
        print("  Warning: No non-transparent pixels in mask for color analysis. Defaulting to black.")
        return (0, 0, 0) # Fallback if mask is entirely transparent
            
    pixels_array = np.array(masked_pixels).reshape(-1, 3)
    
    if pixels_array.shape[0] < num_colors:
        # Fallback to mean color if not enough pixels for clustering
        return tuple(map(int, np.mean(pixels_array, axis=0)))

    kmeans = KMeans(n_clusters=num_colors, random_state=0, n_init='auto').fit(pixels_array)
    return tuple(map(int, kmeans.cluster_centers_[0]))

def get_contrasting_signature_path(background_rgb, signature_colors_map, signature_paths_map):
    """
    Chooses the signature PNG path that provides the best contrast
    against the given background color.
    """
    best_signature_name = None
    max_contrast = -1.0
    
    for sig_name, sig_rgb in signature_colors_map.items():
        # Skip if the signature file doesn't exist
        if not signature_paths_map.get(sig_name, '').is_file():
            continue

        contrast = get_contrast_ratio(background_rgb, sig_rgb)
        if contrast > max_contrast:
            max_contrast = contrast
            best_signature_name = sig_name
            
    if best_signature_name and best_signature_name in signature_paths_map:
        print(f"  Selected '{best_signature_name}' signature for contrast (Contrast: {max_contrast:.2f}).")
        return signature_paths_map[best_signature_name]
    
    # Fallback to black if no suitable signature found or an issue
    print(f"  Fallback: No best contrasting signature found. Using black.png.")
    return signature_paths_map.get("black", None)

# --- MAIN PROCESSING FUNCTION ---

def add_smart_signature(image_path):
    try:
        with Image.open(image_path).convert("RGB") as img:
            width, height = img.size

            # 1. Determine Signature Placement (bottom-left or bottom-right)
            choose_right = random.choice([True, False])

            # Calculate signature size based on long edge
            long_edge = max(width, height)
            signature_target_size = int(long_edge * SIGNATURE_SIZE_PERCENTAGE)
            
            # Calculate final position of the signature
            # This is where the signature will ultimately be pasted.
            # We need these coordinates to build the mask for smoothing.
            
            # Use a dummy signature image to get its aspect ratio for calculating paste size
            # (assuming all signatures have similar aspect ratio)
            dummy_sig_path = list(SIGNATURE_PNGS.values())[0] # Pick any signature to get initial aspect ratio
            with Image.open(dummy_sig_path).convert("RGBA") as dummy_sig:
                dummy_sig_width, dummy_sig_height = dummy_sig.size
                if dummy_sig_width > dummy_sig_height:
                    scaled_sig_width = signature_target_size
                    scaled_sig_height = int(dummy_sig_height * (scaled_sig_width / dummy_sig_width))
                else:
                    scaled_sig_height = signature_target_size
                    scaled_sig_width = int(dummy_sig_width * (scaled_sig_height / dummy_sig_height))
            
            margin_x = int(width * SIGNATURE_MARGIN_PERCENTAGE)
            margin_y = int(height * SIGNATURE_MARGIN_PERCENTAGE)

            if choose_right:
                sig_paste_x = width - scaled_sig_width - margin_x
            else:
                sig_paste_x = margin_x
            sig_paste_y = height - scaled_sig_height - margin_y


            # 2. Generate the Expanded Smoothing Mask based on Signature Shape
            signature_png_path_for_mask = list(SIGNATURE_PNGS.values())[0] # Use any signature to generate the base mask shape
            if not signature_png_path_for_mask or not Path(signature_png_path_for_mask).is_file():
                print(f"  ❌ Skipping {os.path.basename(image_path)}: Base signature for mask not found.")
                return

            with Image.open(signature_png_path_for_mask).convert("RGBA") as base_signature_img:
                # Resize the base signature to its target paste size
                base_signature_img_resized = base_signature_img.resize(
                    (scaled_sig_width, scaled_sig_height), Image.Resampling.LANCZOS
                )
                
                # Create a blank mask canvas (full image size)
                mask_canvas = Image.new("L", img.size, 0) # 'L' mode for grayscale (alpha)
                
                # Paste the resized signature's alpha channel onto the mask canvas
                # at the exact final paste position
                mask_alpha = base_signature_img_resized.split()[-1] # Get alpha channel
                mask_canvas.paste(mask_alpha, (sig_paste_x, sig_paste_y))
                
                # Expand the mask by blurring and re-thresholding (simulates dilation)
                # Apply blur to expand the shape
                expanded_mask = mask_canvas.filter(ImageFilter.GaussianBlur(SMOOTHING_BUFFER_PIXELS))
                # Re-threshold to make it solid again (optional, for crisp expanded edge)
                # If you want a softer halo, you can skip this step and use `expanded_mask` directly as alpha
                expanded_mask = expanded_mask.point(lambda x: 255 if x > 10 else 0)


            # 3. Analyze Artwork Pixels within the Expanded Mask for Dominant Color
            # Get all RGB pixels from the original image
            original_image_rgb_data = list(img.getdata())
            # Get all alpha pixels from the expanded mask
            expanded_mask_alpha_data = list(expanded_mask.getdata())

            dominant_zone_color = get_dominant_color_in_masked_zone(
                original_image_rgb_data, expanded_mask_alpha_data, NUM_COLORS_FOR_ZONE_ANALYSIS
            )
            print(f"  Dominant background color for zone: {dominant_zone_color}")


            # 4. Create and Apply the Smoothed Patch
            # Create a new RGB image filled with the dominant color
            smoothed_patch_base = Image.new("RGB", img.size, dominant_zone_color)
            
            # Apply blur to this color patch. The `expanded_mask` will control its visibility.
            # This blur will extend outwards from the shape
            smoothed_patch_blurred = smoothed_patch_base.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
            
            # Combine the blurred color patch with the expanded mask
            # This creates the final smoothed layer in the shape of the expanded signature
            # We need to make it RGBA for alpha_composite
            smoothed_patch_rgba = smoothed_patch_blurred.copy().convert("RGBA")
            smoothed_patch_rgba.putalpha(expanded_mask) # Use the expanded mask as its alpha channel

            # Composite the smoothed patch onto the original image
            img = Image.alpha_composite(img.convert("RGBA"), smoothed_patch_rgba).convert("RGB") # Convert back to RGB if desired


            # 5. Determine Complimentary Signature Color (and path to PNG)
            signature_png_path = get_contrasting_signature_path(
                dominant_zone_color, SIGNATURE_COLORS_RGB, SIGNATURE_PNGS
            )
            
            if not signature_png_path or not Path(signature_png_path).is_file():
                print(f"  ❌ Skipping {os.path.basename(image_path)}: Could not find a valid signature PNG at path: {signature_png_path}")
                return

            # 6. Place the Actual Signature
            with Image.open(signature_png_path).convert("RGBA") as signature_img:
                # Resize to the previously calculated scaled_sig_width/height
                signature_img = signature_img.resize(
                    (scaled_sig_width, scaled_sig_height), Image.Resampling.LANCZOS
                )
                
                # Paste signature onto the modified image
                img.paste(signature_img, (sig_paste_x, sig_paste_y), signature_img)

            # Save the signed image
            output_path = Path(OUTPUT_SIGNED_DIR) / os.path.basename(image_path)
            img.save(output_path)
            print(f"✅ Signed: {os.path.basename(image_path)}")

    except Exception as e:
        print(f"❌ Error signing {os.path.basename(image_path)}: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging

# --- EXECUTION ---
if __name__ == "__main__":
    # Ensure output directory exists
    Path(OUTPUT_SIGNED_DIR).mkdir(parents=True, exist_ok=True)

    print("\n--- Starting Smart Signature Batch Processing (Shape-Based Smoothing) ---")
    print(f"Reading artworks from: {INPUT_IMAGE_DIR}")
    print(f"Saving signed artworks to: {OUTPUT_SIGNED_DIR}")
    print(f"Using signatures from: {SIGNATURE_DIR}")
    
    processed_files = 0
    for root, _, files in os.walk(INPUT_IMAGE_DIR):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp', '.gif')):
                image_path = Path(root) / file
                print(f"\nProcessing {file}...")
                add_smart_signature(image_path)
                processed_files += 1

    print(f"\n--- Smart Signature Batch Processing Complete ---")
    print(f"Total files processed: {processed_files}")
    print(f"Check '{OUTPUT_SIGNED_DIR}' for your signed artworks.")
```

---
## 📄 app.py

```py
"""CapitalArt application entrypoint."""

from __future__ import annotations

import logging
import os
import json
from pathlib import Path

from flask import Flask
from flask import render_template
from werkzeug.routing import BuildError
from dotenv import load_dotenv

# ---- Modular Imports ----
from config import LOGS_DIR
from routes.artwork_routes import bp as artwork_bp
from routes.sellbrite_service import bp as sellbrite_bp
from routes.export_routes import bp as exports_bp
from routes.admin_debug import bp as admin_bp
from routes.gdws_admin_routes import bp as gdws_admin_bp # <-- Ensure this import is present

# ---- Versioning ----
APP_VERSION = "2.5.1"

# ---- Load .env Configuration ----
load_dotenv()

# ---- Initialize Flask App ----
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "mockup-secret-key")


def check_versions() -> None:
    """Checks config and environment versions against a master version file."""
    print("--- Running System Version Check ---")
    version_file = Path(__file__).parent / "version.json"
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            expected = json.load(f)
    except FileNotFoundError:
        print("\u26A0\uFE0F WARNING: version.json not found. Skipping version check.")
        return

    # Dynamically import config to get the latest version variable
    import config
    
    loaded = {
        "app_version": APP_VERSION,
        "config_version": getattr(config, "CONFIG_VERSION", "Not Set"),
        "env_version": os.getenv("ENV_VERSION", "Not Set"),
        "openai_primary_model": os.getenv("OPENAI_PRIMARY_MODEL", "Not Set"),
        "openai_fallback_model": os.getenv("OPENAI_FALLBACK_MODEL", "Not Set"),
        "gemini_primary_model": os.getenv("GEMINI_PRIMARY_MODEL", "Not Set"),
    }

    for key, expected_val in expected.items():
        loaded_val = loaded.get(key, "Not Set")
        if str(loaded_val) != str(expected_val):
            print(f"\u274C MISMATCH: {key} - Expected '{expected_val}', but found '{loaded_val}'")
        else:
            print(f"\u2705 MATCH: {key} - Version '{loaded_val}'")
    print("--- Version Check Complete ---")

check_versions()

# ---- Logging ----
logging.basicConfig(
    filename=LOGS_DIR / "composites-workflow.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---- Register Blueprints ----
app.register_blueprint(artwork_bp)
app.register_blueprint(sellbrite_bp)
app.register_blueprint(exports_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(gdws_admin_bp) # <-- This line registers the new routes


# ---- Error Handling ----
@app.errorhandler(BuildError)
def handle_build_error(err):
    app.logger.error("BuildError: %s", err)
    return render_template("missing_endpoint.html", error=err), 500


# ---- Healthcheck ----
@app.route("/healthz")
def healthz():
    return "OK"


# ---- Factory for WSGI ----
def create_app() -> Flask:
    return app


# ---- Main Entrypoint ----
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "true").lower() == "true"
    print(f"\U0001f3a8 Starting CapitalArt UI at http://0.0.0.0:{port}/ ...")
    app.run(debug=debug, host="0.0.0.0", port=port)
```

---
## 📄 smart_sign_test01.py

```py
# === [ SmartArt Sign System: CapitalArt Lite | by Robin Custance | Robbiefied Edition 2025 ] ===
# Batch signature overlay for digital artworks with smart colour/contrast detection and smoothing

# --- [ 1. Standard Imports | SS-1.0 ] ---
"""Experimental batch signing script with automatic colour contrast."""

import os
from pathlib import Path
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from sklearn.cluster import KMeans
from config import (
    SIGNATURES_DIR,
    ARTWORKS_INPUT_DIR,
    SIGNATURE_SIZE_PERCENTAGE,
    SIGNATURE_MARGIN_PERCENTAGE,
    SIGNED_OUTPUT_DIR,
)

# --- [ 2. CONFIGURATION | SS-2.0 ] ---
# [EDIT HERE for file paths, signature PNGs, main parameters]

# [2.1] Input/output folders can be overridden via environment variables
INPUT_IMAGE_DIR = ARTWORKS_INPUT_DIR
OUTPUT_SIGNED_DIR = SIGNED_OUTPUT_DIR
SIGNATURE_DIR = SIGNATURES_DIR

# Ensure output directory exists
Path(OUTPUT_SIGNED_DIR).mkdir(parents=True, exist_ok=True)

# [2.2] Map colour names to PNG paths (just add new ones here!)
SIGNATURE_PNGS = {
    "beige": Path(SIGNATURE_DIR) / "beige.png",
    "black": Path(SIGNATURE_DIR) / "black.png",
    "blue": Path(SIGNATURE_DIR) / "blue.png",
    "brown": Path(SIGNATURE_DIR) / "brown.png",
    "gold": Path(SIGNATURE_DIR) / "gold.png",
    "green": Path(SIGNATURE_DIR) / "green.png",
    "grey": Path(SIGNATURE_DIR) / "grey.png",
    "odd": Path(SIGNATURE_DIR) / "odd.png",
    "red": Path(SIGNATURE_DIR) / "red.png",
    "skyblue": Path(SIGNATURE_DIR) / "skyblue.png",
    "white": Path(SIGNATURE_DIR) / "white.png",
    "yellow": Path(SIGNATURE_DIR) / "yellow.png"
}

# [2.3] RGB for contrast calc (update for any new sigs)
SIGNATURE_COLORS_RGB = {
    "beige": (245, 245, 220),
    "black": (0, 0, 0),
    "blue": (0, 0, 255),
    "brown": (139, 69, 19),
    "gold": (255, 215, 0),
    "green": (0, 255, 0),
    "grey": (128, 128, 128),
    "odd": (128, 128, 128),
    "red": (255, 0, 0),
    "skyblue": (135, 206, 235),
    "white": (210, 210, 210),
    "yellow": (255, 255, 0)
}

# [2.4] Signature sizing, margins, and smoothing params
SMOOTHING_BUFFER_PIXELS = 3         # Blur zone around signature
BLUR_RADIUS = 25                    # Big blur for smoothing
NUM_COLORS_FOR_ZONE_ANALYSIS = 2    # KMeans clusters for color

# --- [ 3. UTILITY FUNCTIONS | SS-3.0 ] ---

# [3.1] Luminance for contrast calculation (WCAG method)
def get_relative_luminance(rgb):
    r, g, b = [x / 255.0 for x in rgb]
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

# [3.2] Contrast ratio between two colours
def get_contrast_ratio(rgb1, rgb2):
    L1 = get_relative_luminance(rgb1)
    L2 = get_relative_luminance(rgb2)
    return (L1 + 0.05) / (L2 + 0.05) if L1 > L2 else (L2 + 0.05) / (L1 + 0.05)

# [3.3] Find dominant color(s) in a mask zone
def get_dominant_color_in_masked_zone(image_data_pixels, mask_pixels, num_colors=1):
    masked_pixels = [image_data_pixels[i] for i in range(len(mask_pixels)) if mask_pixels[i] > 0]
    if not masked_pixels:
        print("  [SS-3.3] No mask zone pixels—using black.")
        return (0, 0, 0)
    pixels_array = np.array(masked_pixels).reshape(-1, 3)
    if pixels_array.shape[0] < num_colors:
        return tuple(map(int, np.mean(pixels_array, axis=0)))
    kmeans = KMeans(n_clusters=num_colors, random_state=0, n_init='auto').fit(pixels_array)
    return tuple(map(int, kmeans.cluster_centers_[0]))

# [3.4] Choose signature colour for best contrast
def get_contrasting_signature_path(background_rgb, signature_colors_map, signature_paths_map):
    best_signature_name, max_contrast = None, -1.0
    for sig_name, sig_rgb in signature_colors_map.items():
        if not signature_paths_map.get(sig_name, '').is_file():
            continue
        contrast = get_contrast_ratio(background_rgb, sig_rgb)
        if contrast > max_contrast:
            max_contrast = contrast
            best_signature_name = sig_name
    if best_signature_name and best_signature_name in signature_paths_map:
        print(f"  [SS-3.4] '{best_signature_name}' signature wins (Contrast: {max_contrast:.2f})")
        return signature_paths_map[best_signature_name]
    print("  [SS-3.4] Fallback: using black.png")
    return signature_paths_map.get("black", None)

# --- [ 4. MAIN SIGNATURE FUNCTION | SS-4.0 ] ---

def add_smart_signature(image_path):
    try:
        # [4.1] Open image and prep variables
        with Image.open(image_path).convert("RGB") as img:
            width, height = img.size
            choose_right = random.choice([True, False])  # Randomise L/R
            long_edge = max(width, height)
            sig_target_size = int(long_edge * SIGNATURE_SIZE_PERCENTAGE)

            # [4.2] Dummy signature to get aspect ratio
            dummy_sig_path = list(SIGNATURE_PNGS.values())[0]
            with Image.open(dummy_sig_path).convert("RGBA") as dummy_sig:
                dsw, dsh = dummy_sig.size
                if dsw > dsh:
                    sig_w = sig_target_size
                    sig_h = int(dsh * (sig_w / dsw))
                else:
                    sig_h = sig_target_size
                    sig_w = int(dsw * (sig_h / dsh))
            margin_x = int(width * SIGNATURE_MARGIN_PERCENTAGE)
            margin_y = int(height * SIGNATURE_MARGIN_PERCENTAGE)
            sig_x = width - sig_w - margin_x if choose_right else margin_x
            sig_y = height - sig_h - margin_y

            # [4.3] Build shape mask for zone analysis & smoothing
            with Image.open(dummy_sig_path).convert("RGBA") as base_sig:
                base_sig_rs = base_sig.resize((sig_w, sig_h), Image.Resampling.LANCZOS)
                mask_canvas = Image.new("L", img.size, 0)
                mask_alpha = base_sig_rs.split()[-1]
                mask_canvas.paste(mask_alpha, (sig_x, sig_y))
                expanded_mask = mask_canvas.filter(ImageFilter.GaussianBlur(SMOOTHING_BUFFER_PIXELS))
                expanded_mask = expanded_mask.point(lambda x: 255 if x > 10 else 0)

            # [4.4] Analyse zone colour under mask
            img_rgb_data = list(img.getdata())
            mask_alpha_data = list(expanded_mask.getdata())
            dom_zone_color = get_dominant_color_in_masked_zone(img_rgb_data, mask_alpha_data, NUM_COLORS_FOR_ZONE_ANALYSIS)
            print(f"  [SS-4.4] Dominant colour: {dom_zone_color}")

            # [4.5] Make blurred zone for smooth signature blending
            patch_base = Image.new("RGB", img.size, dom_zone_color)
            patch_blur = patch_base.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
            patch_rgba = patch_blur.copy().convert("RGBA")
            patch_rgba.putalpha(expanded_mask)
            img = Image.alpha_composite(img.convert("RGBA"), patch_rgba).convert("RGB")

            # [4.6] Pick and overlay signature (best contrast)
            sig_path = get_contrasting_signature_path(dom_zone_color, SIGNATURE_COLORS_RGB, SIGNATURE_PNGS)
            if not sig_path or not Path(sig_path).is_file():
                print(f"  [SS-4.6] No valid sig PNG: {sig_path}")
                return
            with Image.open(sig_path).convert("RGBA") as sig_img:
                sig_img = sig_img.resize((sig_w, sig_h), Image.Resampling.LANCZOS)
                img.paste(sig_img, (sig_x, sig_y), sig_img)

            # [4.7] Save output
            out_path = Path(OUTPUT_SIGNED_DIR) / os.path.basename(image_path)
            img.save(out_path)
            print(f"✅ [SS-4.7] Signed: {os.path.basename(image_path)}")

    except Exception as e:
        print(f"❌ [SS-4.ERR] {os.path.basename(image_path)}: {e}")
        import traceback
        traceback.print_exc()

# --- [ 5. BATCH EXECUTION | SS-5.0 ] ---
if __name__ == "__main__":
    Path(OUTPUT_SIGNED_DIR).mkdir(parents=True, exist_ok=True)
    print("\n--- [SS-5.0] Smart Signature Batch Processing ---")
    print(f"Input : {INPUT_IMAGE_DIR}")
    print(f"Output: {OUTPUT_SIGNED_DIR}")
    print(f"Sigs  : {SIGNATURE_DIR}")
    processed = 0
    for root, _, files in os.walk(INPUT_IMAGE_DIR):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp', '.gif')):
                img_path = Path(root) / file
                print(f"\nProcessing {file} ...")
                add_smart_signature(img_path)
                processed += 1
    print(f"\n--- [SS-5.DONE] Batch complete: {processed} files signed! ---")
    print(f"Check your output folder: {OUTPUT_SIGNED_DIR}")


```

---
## 📄 git-update-push.sh

```sh
#!/bin/bash

# ==============================================
# 🔁 CapitalArt Git Update + Commit + Push
# 💥 Robbie Mode™ Gitflow Commander 
# (LOGS TO git-update-push-logs)
# Run:              ./git-update-push.sh
# Run Auto Mode:    ./git-update-push.sh --auto
# ==============================================

set -euo pipefail

LOG_DIR="git-update-push-logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/git-update-push-$(date '+%Y-%m-%d').log"

function log() {
  local msg="$1"
  local ts
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[$ts] $msg" | tee -a "$LOG_FILE"
}

log "=== Git Update Push Script Started ==="

# 1. Show current status
log "📂 Checking git status..."
if ! git status | tee -a "$LOG_FILE"; then
  log "❌ Failed to get git status!"
fi

# 2. Stage everything
log "➕ Adding all changes..."
if ! git add . 2>>"$LOG_FILE"; then
  log "❌ git add failed. Please resolve manually."
  exit 1
fi

# 3. Commit message
if [[ "${1:-}" == "--auto" ]]; then
  commit_msg="Push a few files before Codex does it's thing"
  log "📝 Using auto commit message: $commit_msg"
else
  read -rp "📝 Enter commit message: " commit_msg
fi

# 4. Commit
log "✅ Committing changes..."
if ! git commit -m "$commit_msg" 2>>"$LOG_FILE"; then
  log "⚠️ Nothing to commit or commit failed."
fi

# 5. Pull latest from origin/main
log "🔄 Pulling latest from origin/main..."
if ! git pull origin main --rebase 2>>"$LOG_FILE"; then
  log "❌ git pull --rebase failed. Please resolve merge/rebase conflicts!"
  exit 2
fi

# 6. Push to main
log "🚀 Pushing to origin/main..."
if ! git push origin main 2>>"$LOG_FILE"; then
  log "❌ git push failed. Please check your network or remote."
  exit 3
fi

log "✅ All done, Robbie! Git repo is updated and synced. 💚"

```

---
## 📄 sort_and_prepare_midjourney_images.py

```py
import os
import csv
import math
import shutil
import re
from PIL import Image, ImageFilter
from collections import Counter
from pathlib import Path
import numpy as np
from config import (
    MIDJOURNEY_CSV_PATH,
    MIDJOURNEY_INPUT_DIR,
    MIDJOURNEY_OUTPUT_DIR,
    MIDJOURNEY_METADATA_CSV,
)

# === [ CapitalArt Lite: CONFIGURATION ] ===
# Paths are defined here for easy modification.
# Ensure these directories exist or will be created when run locally.

# The CSV file exported from Autojourney.
CSV_PATH = MIDJOURNEY_CSV_PATH

# The local directory where raw, untransformed Midjourney images are initially downloaded.
INPUT_DIR = MIDJOURNEY_INPUT_DIR

# The base local directory where sorted images (within aspect ratio subfolders)
# and the new enriched metadata CSV will be stored.
OUTPUT_DIR = MIDJOURNEY_OUTPUT_DIR

# The full path and filename for the newly generated CSV file containing enriched image metadata.
GENERATED_CSV = MIDJOURNEY_METADATA_CSV

# Predefined aspect ratio categories (Width / Height) for sorting images.
ASPECT_CATEGORIES = {
    "1x1": 1.0, "2x3": 2 / 3, "3x2": 3 / 2, "3x4": 3 / 4,
    "4x3": 4 / 3, "4x5": 4 / 5, "5x4": 5 / 4, "5x7": 5 / 7,
    "7x5": 7 / 5, "9x16": 9 / 16, "16x9": 16 / 9,
    "A-Series-Vertical": 11 / 14, "A-Series-Horizontal": 14 / 11,
}
# Tolerance (as a decimal) for aspect ratio matching. Allows for slight variations.
ASPECT_TOLERANCE = 0.02

# Curated palette of RGB colors and their friendly names for dominant color detection (ETSY LIST).
PALETTE_RGB = {
    "Beige": (245, 245, 220),
    "Black": (0, 0, 0),
    "Blue": (0, 0, 255),
    "Bronze": (205, 127, 50),
    "Brown": (139, 69, 19),
    "Clear": (255, 255, 255), # Often represented as white/transparent in palettes
    "Copper": (184, 115, 51),
    "Gold": (255, 215, 0),
    "Grey": (128, 128, 128),
    "Green": (0, 255, 0),
    "Orange": (255, 165, 0),
    "Pink": (255, 192, 203),
    "Purple": (128, 0, 128),
    "Rainbow": (127, 127, 255), # Placeholder/fallback for multi-color or unmatchable
    "Red": (255, 0, 0),
    "Rose gold": (183, 110, 121),
    "Silver": (192, 192, 192),
    "White": (255, 255, 255),
    "Yellow": (255, 255, 0)
}
# Maximum Euclidean distance threshold for mapping an image pixel's RGB to a palette color.
MAX_DISTANCE_THRESHOLD = 100

# Number of dominant colors to extract and include in metadata.
NUM_DOMINANT_COLORS_TO_EXTRACT = 2 # <-- CHANGED TO 2

# === [ CapitalArt Lite: UTILITY FUNCTIONS ] ===

def euclidean_dist(c1, c2):
    """Calculates the Euclidean distance between two RGB color tuples."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

def closest_palette_color(rgb):
    """
    Returns the name of the closest colour from the PALETTE_RGB based on Euclidean distance.
    Returns 'Unknown' if no close match is found within MAX_DISTANCE_THRESHOLD.
    """
    closest_name = "Unknown"
    min_dist = float('inf')
    for name, palette_rgb in PALETTE_RGB.items():
        d = euclidean_dist(rgb, palette_rgb)
        if d < min_dist:
            min_dist = d
            closest_name = name
    return closest_name if min_dist < MAX_DISTANCE_THRESHOLD else "Unknown"

def get_dominant_colours(img_path, num_colours=NUM_DOMINANT_COLORS_TO_EXTRACT):
    """
    Analyzes an image to find its top `num_colours` most prominent named colours,
    mapped to the predefined PALETTE_RGB. Returns a list of color names.
    """
    try:
        with Image.open(img_path) as img:
            img = img.convert("RGB").resize((100, 100)) # Resize for faster analysis
            pixels = list(img.getdata())
            counts = Counter(pixels)
            top_rgb = [rgb for rgb, _ in counts.most_common(num_colours)]
            
            # Map to palette colors and ensure only unique colors are returned,
            # taking the first N unique ones.
            found_colors = []
            for rgb_color in top_rgb:
                mapped_color = closest_palette_color(rgb_color)
                if mapped_color != "Unknown" and mapped_color not in found_colors:
                    found_colors.append(mapped_color)
                if len(found_colors) == num_colours: # Stop once we have enough unique colors
                    break
            
            # Fill remaining spots with "Unknown" if not enough unique colors were found
            while len(found_colors) < num_colours:
                found_colors.append("Unknown")
            
            return found_colors

    except Exception as e:
        print(f"⚠️ Error reading image for dominant colors {img_path}: {e}")
        return ["Unknown"] * num_colours # Return "Unknown" for all requested colors if error occurs

def calculate_sharpness(img_path):
    """
    Calculates a sharpness score for an image using the variance of the Laplacian.
    A higher value generally indicates a sharper image.
    Returns -1.0 on error.
    """
    try:
        with Image.open(img_path) as img:
            # Convert to grayscale for Laplacian calculation
            gray_img = img.convert("L")
            # Apply Laplacian filter and convert to numpy array to use .var()
            laplacian_var = np.var(np.array(gray_img.filter(ImageFilter.FIND_EDGES)))
            return laplacian_var
    except Exception as e:
        print(f"⚠️ Error calculating sharpness for {img_path}: {e}")
        return -1.0 # Indicate error

def classify_aspect(width, height):
    """
    Classifies an image's aspect ratio (width/height) into one of the
    predefined ASPECT_CATEGORIES, allowing for a specified tolerance.
    """
    if height == 0:
        return "Unclassified"
    actual_ratio = width / height
    for label, expected in ASPECT_CATEGORIES.items():
        if abs(actual_ratio - expected) <= ASPECT_TOLERANCE:
            return label
    return "Unclassified"

def clean_prompt(prompt):
    """
    Cleans and formats a Midjourney prompt string for use as a SEO-friendly filename.
    """
    prompt = re.sub(r"[^\w\s-]", "", prompt)
    prompt = re.sub(r"[_]+", "-", prompt)
    prompt = re.sub(r"\s+", "-", prompt.strip())
    cleaned = prompt[:100].strip("-").lower()
    return cleaned if cleaned else "untitled-artwork"

# === [ CapitalArt Lite: MAIN PROCESS ] ===

def process_images():
    """
    Main function to execute the image sorting, renaming, and metadata generation workflow.
    This function handles CSV loading, image processing (locally), file operations,
    and the final CSV generation, including enhanced metadata.
    """
    print("🧠 Starting CapitalArt Lite: Image Sort, Rename, and Metadata Generation...")
    print(f"Loading CSV from: {CSV_PATH}")
    print(f"Processing images from: {INPUT_DIR}")
    print(f"Outputting to: {OUTPUT_DIR}")

    # Load Autojourney CSV from local file system
    rows = []
    try:
        with open(CSV_PATH, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"Successfully loaded {len(rows)} entries from CSV.")
    except FileNotFoundError:
        print(f"❌ Error: Autojourney CSV file not found at {CSV_PATH}. Please check the path in CONFIGURATION.")
        return
    except Exception as e:
        print(f"❌ Error loading Autojourney CSV: {e}")
        return

    # Ensure the base output directory exists locally
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Prepare CSV headers for the new metadata file, including new fields
    headers = [
        "Filename", "New Name", "Prompt", "Aspect Ratio", "Width", "Height",
        "Sharpness Score",
        "Primary Colour", # <-- CHANGED
        "Secondary Colour" # <-- CHANGED
    ]
    headers.extend(["Image URL", "Grid Image"]) # Add original URLs

    metadata_rows = [headers]

    processed_count = 0
    
    for row in rows:
        original_name = row.get("Filename", "").strip()
        prompt = row.get("Prompt", "").strip()
        image_url = row.get("Image url", "")
        grid_url = row.get("Grid image", "")

        if not original_name:
            print(f"⚠️ Skipping row due to missing 'Filename' in CSV: {row}")
            continue

        input_path = Path(INPUT_DIR) / original_name

        # Initialize placeholders
        width, height = "Unknown", "Unknown"
        aspect = "Unclassified"
        colors = ["Unknown"] * NUM_DOMINANT_COLORS_TO_EXTRACT
        sharpness_score = "Unknown"

        # --- LOCAL FILE PROCESSING ---
        if input_path.is_file():
            try:
                with Image.open(input_path) as img:
                    width, height = img.size
                    aspect = classify_aspect(width, height)
                    colors = get_dominant_colours(input_path, NUM_DOMINANT_COLORS_TO_EXTRACT)
                    sharpness_score = calculate_sharpness(input_path)
            except Exception as e:
                print(f"⚠️ Error processing image {original_name} (dimensions/colors/sharpness): {e}")
        else:
            print(f"❌ Missing image file: {original_name} (Expected at {input_path}). Skipping image processing.")
            # If the file is missing, we still want to add metadata to CSV if possible
            # but with 'Unknown' values for image-derived fields.

        original_ext = Path(original_name).suffix.lower() if Path(original_name).suffix else ".png"
        safe_name = clean_prompt(prompt)
        new_filename_base = f"{safe_name}{original_ext}"
        
        output_folder_path = Path(OUTPUT_DIR) / aspect
        output_folder_path.mkdir(parents=True, exist_ok=True) # Ensure aspect ratio folder exists

        final_new_filename = new_filename_base
        new_path = output_folder_path / new_filename_base
        counter = 1
        while new_path.exists(): # Check for existing file to avoid overwrites
            final_new_filename = f"{safe_name}-{counter}{original_ext}"
            new_path = output_folder_path / final_new_filename
            counter += 1

        # --- LOCAL FILE COPYING ---
        if input_path.is_file(): # Only copy if the source file exists
            try:
                shutil.copy2(input_path, new_path) # Copy the file, preserving metadata
                processed_count += 1
                print(f"✅ Processed & Copied: '{original_name}' -> '{aspect}/{final_new_filename}'")
            except Exception as e:
                print(f"❌ Error copying {original_name} to {new_path}: {e}")
                continue # Skip to the next image if copy fails
        else:
            print(f"✅ Processed metadata only for: '{original_name}' (Image file not found for copying)")
            # If image file not found, we still count it as processed metadata-wise
            processed_count += 1

        # Prepare the data row for CSV
        data_row = [
            original_name, final_new_filename, prompt, aspect, width, height,
            sharpness_score
        ]
        data_row.extend(colors) # Add the two extracted dominant colors
        data_row.extend([image_url, grid_url]) # Add original URLs

        metadata_rows.append(data_row)

    # Write the enriched metadata to the new CSV file
    try:
        with open(GENERATED_CSV, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(metadata_rows)
        print(f"\n📦 CapitalArt Lite process complete!")
        print(f"Successfully processed {processed_count} images/entries.")
        print(f"Enriched metadata written to: {GENERATED_CSV}")
    except Exception as e:
        print(f"❌ Error writing generated metadata CSV: {e}")

# === [ CapitalArt Lite: ENTRY POINT ] ===

if __name__ == "__main__":
    process_images()
```

---
## 📄 generate_folder_tree.py

```py
import os

from config import BASE_DIR

# ============================== [ CONFIGURATION ] ==============================

ROOT_DIR = BASE_DIR
OUTPUT_FILE = "folder_structure.txt"

# Folders or files to ignore (case insensitive)
IGNORE_NAMES = {
    ".git", "__pycache__", ".venv", "venv", "env", ".idea", ".DS_Store",
    "node_modules", ".nojekyll", ".pytest_cache", ".mypy_cache"
}

# File extensions to ignore (add as needed, e.g., '.log', '.tmp')
IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".swp"
}

# ============================== [ HELPER FUNCTION ] ==============================

def should_ignore(entry):
    # Ignore by exact name
    if entry in IGNORE_NAMES:
        return True
    # Ignore by extension
    _, ext = os.path.splitext(entry)
    if ext in IGNORE_EXTENSIONS:
        return True
    return False

def generate_tree(start_path: str, prefix: str = "") -> str:
    tree_str = ""
    try:
        entries = sorted(os.listdir(start_path))
    except PermissionError:
        # Just in case you hit a protected dir (unlikely in your use)
        return tree_str
    entries = [e for e in entries if not should_ignore(e)]

    for idx, entry in enumerate(entries):
        full_path = os.path.join(start_path, entry)
        connector = "└── " if idx == len(entries) - 1 else "├── "
        tree_str += f"{prefix}{connector}{entry}\n"

        if os.path.isdir(full_path) and not should_ignore(entry):
            extension = "    " if idx == len(entries) - 1 else "│   "
            tree_str += generate_tree(full_path, prefix + extension)
    return tree_str

# ============================== [ MAIN EXECUTION ] ==============================

if __name__ == "__main__":
    print(f"📂 Generating folder structure starting at: {os.path.abspath(ROOT_DIR)}")
    tree_output = f"{os.path.basename(os.path.abspath(ROOT_DIR))}\n"
    tree_output += generate_tree(ROOT_DIR)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(tree_output)

    print(f"✅ Folder structure written to: {OUTPUT_FILE}")

```

---
## 📄 settings/Master-Etsy-Listing-Description-Writing-Onboarding.txt

```txt
🥇 Robin Custance Etsy Listing Writing – Master Instructions (2025)

PURPOSE:
Generate unique, professional, search-optimised artwork listings for Aboriginal and Australian digital art, to be sold as high-resolution digital downloads on Etsy and other platforms. YOUR OUTPUT WILL BE AUTOMATICALLY PROCESSED BY ROBOTIC SYSTEMS—STRICTLY FOLLOW THE STRUCTURE AND INSTRUCTIONS BELOW.

1. OVERVIEW
- You are acting as a renowned art curator and professional art writer.
- You will write artwork listings (description, tags, materials, SEO filename, price, sku, etc.) for digital Aboriginal/Australian art by Robin Custance (Robbie) for use on Etsy and Sellbrite.
- Each listing must be unique, Pulitzer-quality, SEO-rich, and tailored to the specific artwork—never formulaic, never generic.

2. INPUTS
- The original filename is provided for reference only (for admin/tracking). NEVER use the filename for any creative or descriptive content.
- Artwork visual and cues will be provided; describe only what is seen, felt, and artistically relevant.

3. FINAL OUTPUT FORMAT (REQUIRED FIELDS & ORDER)
Output MUST be a single, valid JSON object with these EXACT keys and no others:
- seo_filename
- title
- description
- tags
- materials
- primary_colour
- secondary_colour
- price
- sku

**IMPORTANT: Every key MUST be present in every output. Even if you must estimate, guess, or repeat, NEVER omit a field. Output ONLY the JSON object—NO markdown, HTML, headings, or extra text.**

—Field details—

- **seo_filename**:  
  - Max 70 characters, ends with: "Artwork-by-Robin-Custance-RJC-XXXX.jpg" (replace XXXX with SKU or sequential number)
  - Begins with 2–3 hyphenated words from the artwork’s title (subject or style), never blindly copied from the original file name and never padded or generic
  - No fluff, no filler

- **title**:  
  - Max 140 characters
  - Must strongly reflect: "High Resolution", "Digital", "Download", "Artwork by Robin Custance"
  - Include powerful buyer search terms: "Dot Art", "Aboriginal Print", "Australian Wall Art", "Instant Download", "Printable", etc.
  - First 20 words MUST be strong search terms and clearly describe subject—**no poetic intros, no “Immerse,” “Step into,” “Discover” etc.**

- **description**:  
  - At least 400 words, or at lease 2,600 characters, Pulitzer Prize winning quality, visually and artistically accurate
  - Paragraphs must be no more than 70 words or 400 characters for readability.
  - **First 20 words MUST ONLY contain actual search terms and keyword phrases buyers use for art like this.** Write these as a smooth, natural sentence, not a list or poetic intro. Examples: “Australian outback wall art, Aboriginal dot painting print, digital download, Robin Custance artwork” etc.
  - Must deeply analyse the artwork’s style, method, colours, textures, and inspiration. Include cultural context when appropriate.
  - Always append the generic context/technique block from this onboarding file, separated by two newlines for clear paragraph breaks.
  - NO padding, no shop info, no printing instructions, no artist bio—these are handled elsewhere.

- **tags**:  
  - Array of up to 13 targeted, comma-free tags (max 20 chars/tag), highly relevant to the artwork. Rotate and tailor for each listing.
  - Mix art technique, subject, Australian/Aboriginal terms, branding, and digital wall art keywords.
  - No hyphens, no duplicates, no generic filler.

- **materials**:  
  - Array of up to 13 phrases (max 45 chars/phrase) specific to this artwork’s technique and file type.
  - Never repeat, pad, or use generic phrases unless accurate. Rotate for every artwork.

- **primary_colour, secondary_colour**:  
  - Single-word, plain English colour names matching the two most visually dominant colours in the artwork. Must be accurate. Use image analysis or artist input if unsure.

- **price**:  
  - Must be set to **18.27** exactly (as a float or numeric string with no currency symbols).

- **sku**:
- The SKU is always assigned by the system and provided as assigned_sku for this artwork.
- You must use this exact value for the "sku" field and as the suffix in the "seo_filename" (e.g. "Artwork-by-Robin-Custance-RJC-XXXX.jpg").
- Never invent, guess, or modify the SKU—always use assigned_sku exactly as given.
- This value comes from the project's central SKU tracker and is injected automatically.
- Maximum 32 characters, only letters, numbers, and hyphens allowed.

4. STRICT OUTPUT RULES
- Output a single JSON object, in the order above.
- NO markdown, headings, notes, HTML, or extra text—**just the JSON**.
- If you are unsure about any field, estimate or generate a plausible value (never leave blank or omit).
- If you fail to include all fields or add extra text, your output will break an automated system.
- No description, title, or filename may be repeated between listings.

5. EXAMPLE OUTPUT (SHOW THIS FORMAT)
{
  "seo_filename": "Night-Seeds-Rebirth-Artwork-by-Robin-Custance-RJC-XXXX.jpg",
  "title": "High Resolution Digital Dot Art Print – Aboriginal Night Seeds Rebirth | Robin Custance Download",
  "description": "Australian dot art print, Aboriginal night sky wall decor, digital download, Robin Custance, swirling galaxy artwork... [first 20 words as real search terms] ...[minimum 400 words, then append generic context/technique block]\n\n[Generic block here]",
  "tags": [
    "dot art",
    "night sky",
    "aboriginal",
    "robin custance",
    "australian art",
    "digital print",
    "swirling stars",
    "dreamtime",
    "galaxy decor",
    "modern dot",
    "outback art",
    "starry night",
    "printable"
  ],
  "materials": [
    "High resolution JPEG",
    "Digital painting",
    "Original dot technique",
    "Layered composition",
    "Contemporary wall art file",
    "Professional digital art",
    "Printable file",
    "Precision digital artwork",
    "Gallery-quality image",
    "Modern aboriginal design",
    "Colour-rich JPEG",
    "Instant download",
    "Australian art download"
  ],
  "primary_colour": "Black",
  "secondary_colour": "Brown",
  "price": 18.27,
  "sku": "RJC-XXXX"
}

6. VALIDATION RULES (CHECK ALL BEFORE FINALISING)
- Tags: max 13, max 20 chars each, no hyphens/commas, no duplicates.
- Title: max 140 characters.
- Seo_filename: max 70 chars, correct suffix, no spaces, valid chars only.
- Materials: max 13, max 45 chars/phrase.
- Price: float 18.27, no currency symbol.
- SKU: max 32 chars, unique, matches seo_filename.
- Colours: visually accurate, one-word, plain English.
- Description: min 400 words, starts with search terms, generic block appended using two newlines.

End of Instructions

```

---
## 📄 notes-and-instructions/Full-Rundown-V02.txt

```txt
DreamArtMachine: Full Project System Overview
(Table of Contents Draft)
Project Vision & Scope
1.1 Purpose and End Game
1.2 Key Features & Differentiators
1.3 Target Users (for personal and future member use)

Core Architecture & Tech Stack
2.1 High-Level Architecture Diagram
2.2 Core Directories & File Layout
2.3 Main Tech & Tools Used (Python, FastAPI, OpenAI, etc.)
2.4 Key Integration Points (OpenAI, Gelato, Etsy, Nembol, Gemini, etc.)

Artwork Processing Workflow
3.1 Artwork Upload
3.2 Temp Processing & Analysis
3.3 AI Vision Analysis & Description
3.4 Listing Generation (Etsy, CSV, etc.)
3.5 Mockup Generation & Management
3.6 Finalization, Renaming, and File Organization
3.7 Export & Publishing
3.8 Quality Control, Audit, and Verification

Data & File Management
4.1 Database (Schema & Key Tables)
4.2 Artwork File Storage Structure
4.3 Naming Conventions & Standards
4.4 Versioning & Backups

AI & Content Generation
5.1 AI Analysis Profiles & Prompt Templates
5.2 Vision and Text Model Integration (OpenAI/Gemini)
5.3 Content Blocks & SEO Strategy
5.4 EEAT, Curation, and Cultural Guidance
5.5 Member/Custom Profiles

User Interface & Experience
6.1 Web App Navigation & UX Principles
6.2 Security & Permissions
6.3 Admin/Member Modes
6.4 Customization & Themes

Workflow Automation & DevOps
7.1 Automated Scripts (Reporting, Audit, Maintenance)
7.2 Codex AI Assistance (Testing, Refactoring, QA)
7.3 GitOps/Deployment Best Practices
7.4 System Health, Logging & Monitoring

External Service Integrations
8.1 Print-On-Demand (Gelato, etc.)
8.2 Marketplace Exports (Etsy, Nembol)
8.3 AI Services (OpenAI, Gemini, Google, etc.)
8.4 Third-Party Libraries & APIs

Quality Control & Testing
9.1 Manual QA
9.2 Automated Testing
9.3 Reporting & Auditing
9.4 Failure Handling & Error Reporting

Future Enhancements & Roadmap
10.1 Features in Progress
10.2 Wishlist & Stretch Goals
10.3 Known Limitations
10.4 Member/Community Expansion Plan

Appendix
11.1 File/Folder Tree (Current Snapshot)
11.2 Key Settings/Config Reference
11.3 Troubleshooting
11.4 Useful Scripts, Aliases, and Helper Tools




1. Project Vision & Scope
1.1 Purpose and End Game
DreamArtMachine is a robust, production-grade, AI-driven platform designed by and for Australian artists and makers—originally for personal use but extensible to a membership-based model. Its purpose is to radically streamline and automate the journey from digital artwork creation to high-quality print-ready listings across print-on-demand (POD) and e-commerce marketplaces (e.g., Etsy, Nembol, Gelato), while preserving full control, quality, and integrity at every stage.

The end goal is to provide a turnkey system for managing thousands of artwork files, auto-generating professional mockups, AI-powered art descriptions, and export-ready listings, with zero manual CSV wrangling or tedious admin. Quality control, copyright, and curation standards are baked in, as is deep flexibility for Aboriginal, Australian, and contemporary art needs. The system also automates final listing QA and can be adapted to new platforms as needed.

1.2 Key Features & Differentiators
Self-hosted, Modular, Secure: Built on FastAPI/Python, designed for easy deployment, with a structure ready for both solo and future multi-user expansion.

Artwork-Centric Workflow: Every part of the system revolves around the lifecycle of a single artwork file, from upload to multi-platform listing.

Full AI/ML Pipeline: Uses OpenAI Vision (and optionally Gemini) for image analysis, and GPT-powered prompt templates for world-class, SEO-rich, culturally respectful listings.

Mockup Automation: Batch generates and manages professional wall-art mockups, enforcing strict naming and organizational rules.

Zero CSV Headaches: Handles all listing and export formatting in the backend—producing CSVs compatible with Nembol, Etsy, and future platforms.

Deep Quality Control: Integrates system-level checks for missing, duplicate, or misnamed files, image quality, and listing consistency.

Cultural Sensitivity: Aboriginal and Australian art profiles ensure all content generation respects cultural protocols, with option for exclusive art packages for partners.

Automation Scripts: Built-in scripts for system health checks, full project snapshots, and ongoing audits.

Production-Grade Standards: All code, configs, and templates are fully documented, version-controlled, and structured for ongoing improvement (Robbie Mode™).

1.3 Target Users (Now & Future)
Personal/Professional Use: Australian artists, art entrepreneurs, and digital creators who want to take control of their print-on-demand art business with pro-level tools.

Membership Mode (Future): Expandable to a private, invite-only club of trusted artists/creators, with member-specific settings, listing profiles, and user management.

Integration Partners: Print-on-demand businesses seeking access to exclusive, high-quality Australian artwork libraries (with package or non-exclusive options).

2. Core Architecture & Tech Stack
2.1 High-Level System Structure
DreamArtMachine is engineered for robustness, modularity, and extensibility. The platform is structured around a core FastAPI backend, using Python for all business logic and orchestration. The application is strictly organized into functional domains (routes, services, utils, etc.), and follows modern Python best practices—favoring clarity, maintainability, and explicitness.

Major Directories & Files:

routes/ — All FastAPI route definitions (upload, analyze, mockup, export, etc.)

services/ — Business logic, AI integration, content generation, etc.

utils/ — Reusable helpers for file management, templates, security, image processing, etc.

core/ — Configuration, settings, constants, and environment handling.

templates/ — Jinja2 templates for HTML rendering.

data/ — Artwork database (artworks.db), user data, settings, etc.

static/ — Static files (CSS, images, icons, etc.)

mockup-generator/ — All mockup processing scripts, coordinates, and templates.

Application Entry Point
main.py — Sets up FastAPI app, includes all routers, configures Jinja2, error handlers, and other startup logic.

2.2 Primary Technology Choices
Layer	Technology / Tool	Purpose
Web Framework	FastAPI	Modern, async-ready Python web API framework
Templating	Jinja2	HTML rendering, template composition
ORM/Database	SQLAlchemy + SQLite	Relational DB, scalable to PostgreSQL if needed
AI/ML Integration	OpenAI API (GPT, Vision)	Image & text analysis, listing generation
File Ops/Imaging	Pillow (PIL), pathlib	Image processing, resizing, sRGB management
CSV/Export	csv, pandas (optional)	Exporting listings for Nembol, Etsy, etc.
Auth/Security	passlib, itsdangerous	Password hashing, session/token security
Frontend	Minimal JS/HTML/CSS	No complex SPA—focus on efficient, minimal UI
Automation/Scripts	Custom Python scripts	System health, QA, code snapshots, audits
Version Control	Git	Full versioning, commit history, code reviews

2.3 System Components & Responsibilities
A. FastAPI Backend
Handles:

User authentication (with roles for future expansion)

Artwork upload, metadata extraction, file validation

Routing for all business actions (analyze, mockup, export, etc.)

Error handling, logging, and custom endpoints (health checks, reports)

B. Artwork Analysis & Listing Generator
Handles:

Automated image analysis via OpenAI Vision (or Gemini if enabled)

Generation of detailed, SEO-optimized, culturally aware art listings using custom AI prompt templates

Profile-based configuration for different art styles (Aboriginal, Australian, etc.)

All AI and logic is server-side—no browser-based AI calls

C. Mockup Generator System
Handles:

Batch and single mockup creation from base templates

Strict naming and output folder conventions (all automated)

Management of mockup variants, thumbnails, AI-optimized images

D. File & Data Management
Handles:

Structured file/folder handling for uploads, processing, and finalized artwork

Reliable storage and referencing of all files, using absolute and relative paths

Automated migration of files during workflow (e.g., temp → finalized)

E. CSV Export & Integration
Handles:

Generating platform-ready CSV files for Nembol, Etsy, and future POD integrations

Full control over output fields, formatting, and data consistency

Sidecar JSON or other formats supported for future integrations

F. Quality Assurance (QA) & System Scripts
Handles:

Automated health checks, system reports, code snapshots, and audits

File/folder integrity checks (naming, existence, duplicates, etc.)

Can be run as scheduled jobs or on demand

G. Security & User Management
Handles:

Secure authentication for solo and future member use

Full password management, session security, and permissions logic

Ready for expansion to support invited artists/curators in the future

2.4 Extensibility & DevOps
Modular by design: New routes, services, or integrations can be added with minimal risk of breaking existing workflows.

Automated reports: Project includes scripts for generating full codebase snapshots, folder trees, config dumps, and database schema exports—ideal for debugging, onboarding, or audits.

Config-driven: All critical paths, credentials, and platform settings are centralized in config files (with safe defaults and .env overrides).

Portable & VM-friendly: Designed for easy deployment in VM/cloud environments (Linux first, but portable to Docker or cloud PaaS if needed).

Pro-grade Git discipline: All files and changes are version-controlled with strict commit protocols (no “it works on my machine” disasters).

3. Detailed Workflow Stages & Data Flow
3.1 Overview of Workflow Stages
The DreamArtMachine system is designed around a linear, trackable workflow that takes artwork from initial upload through to final CSV export, ready for marketplaces and print-on-demand partners. Every step is auditable, and all data transitions (file moves, DB updates, AI actions) are explicitly managed for traceability.

Key Workflow Stages:

Artwork Upload & Ingestion

Artwork Analysis (AI Visual & Text)

Mockup Generation

Mockup Review & Finalization

Artwork & Mockup Finalization

Export Preparation (CSV/JSON)

Quality Assurance & Reporting

3.2 Stage-by-Stage Breakdown
A. Artwork Upload & Ingestion
Entry Point:
upload_routes.py (route: /upload)

Process:

User selects and uploads one or more art files (all common formats supported).

Each upload is assigned a unique processing subfolder within art-uploads/temp-processing/.

Metadata is extracted: original filename, timestamp, user ID (if logged in), preliminary SEO filename (if available).

Database entry is created in the artworks table, including file paths, status (uploaded), and any attached notes.

Data Flow:
User → FastAPI route → disk (temp-processing) → database

B. Artwork Analysis (AI Visual & Text)
Entry Point:
analyze_routes.py (route: /analyze/{artwork_id})

Process:

The system retrieves the artwork from its recorded file path.

Visual Analysis:

Sends the image to OpenAI Vision (or Gemini, if enabled) for a rich, structured description—colour, subject, composition, textures, etc.

Description is validated for completeness.

Textual Listing Generation:

Constructs an AI prompt using a master template (from master_listing_templates/etsy_master_template.txt), populated with the visual analysis and profile-based settings (e.g., Aboriginal or Aussie landscape, etc.).

The result is a long-form, SEO-friendly listing, reviewed for formatting and content guidelines (e.g., minimum word count, cultural sensitivity).

Database is updated with generated title, description, and analysis metadata.

Data Flow:
DB/artwork file → AI model(s) → DB update (analysis, title, description)

C. Mockup Generation
Entry Point:
mockup_routes.py and supporting scripts

Process:

After successful analysis, users can generate mockups (in batch or single mode).

The mockup generator uses pre-defined templates (frames, walls, objects) to composite the artwork onto a range of realistic settings.

All mockup files are stored with strict naming conventions (e.g., SEO-FILENAME-MU-01.jpg) in the designated temp folder for that artwork.

Each mockup’s path and metadata is tracked in the database.

Data Flow:
Artwork (temp folder) → Mockup scripts → new image files → DB mockup records

D. Mockup Review & Finalization
Entry Point:
mockup_management_routes.py + frontend (review screens)

Process:

The user reviews all generated mockups in a sortable gallery.

Selection: User can “accept” or “reject” each mockup (only accepted are finalized).

Finalization: Accepted mockups are moved to the analysed-artwork/{seo-folder}/ directory, renamed per convention, and non-selected variants are archived or discarded.

Database status for each mockup and artwork is updated to reflect finalization.

Data Flow:
Mockup images (temp) → user review → finalized folder/archive → DB update

E. Artwork & Mockup Finalization
Entry Point:
analyze_routes.py (/accept-finalize/{artwork_id} route)

Process:

Once all reviews are done, artwork and its mockups are “locked in” and marked as finalized.

The system:

Moves all files (main, thumb, openai-variant, and mockups) into their permanent, SEO-named directory under analysed-artwork/.

Updates all DB references with new paths.

Changes artwork status to finalized and records the finalized timestamp.

Data Flow:
Temp processing folders → permanent location → DB path/status updates

F. Export Preparation (CSV/JSON)
Entry Point:
export_routes.py (routes: /export/csv, /export/json, etc.)

Process:

Users can export finalized artwork (and all attached mockups) in formats ready for Nembol, Etsy, or other partners.

The export generator compiles all required fields—title, description, paths/URLs for all images, pricing, tags, etc.—and ensures CSV-safety (no rogue line breaks, no HTML).

Optionally generates JSON “sidecars” for additional integrations.

All exports are logged for auditability.

Data Flow:
Finalized artwork/mockups + DB → CSV/JSON writer → export files

G. Quality Assurance & Reporting
Entry Point:
System scripts (e.g., a-total-nuclear.py report), QA endpoints, admin screens.

Process:

Automated scripts scan the system regularly:

Integrity checks: File/directory existence, naming conformity, orphaned records.

DB checks: Invalid data, missing references, status mismatches.

AI health checks: OpenAI API connectivity, API key validity, model status.

Full codebase and folder tree snapshots for backup or review.

QA results are written to timestamped reports, available in /reports/.

Data Flow:
Full system → reporting/QA script → Markdown/txt/CSV reports

3.3 Data Integrity, Statuses, and Auditing
Every artwork and mockup has status fields (e.g., uploaded, analyzed, mockups, finalized, exported, error) to track its lifecycle.

All file moves and renames are explicitly recorded in the database, and old paths are never re-used.

QA scripts and admin actions can reconcile DB and file system, flagging any inconsistencies for manual review.

All critical actions (uploads, AI runs, file moves, exports) are timestamped and attributed (user, script, or system).

3.4 Visual Summary
Here’s the overall flow in simple steps:

Upload → Analyze → Generate Mockups → Review/Accept → Finalize → Export → QA/Report

Each step is self-contained, but the DB always tracks current status and file paths, and the system is built to be resumable and fault-tolerant (crashes or errors can be retried from last good state).


4. AI Integration & Prompt Engineering
4.1 AI Services Overview
DreamArtMachine deeply integrates with modern AI models for both visual and textual analysis. The primary provider is OpenAI (Vision & Text), with infrastructure in place to support future additions like Gemini (Google) or other model APIs.

AI is leveraged for:

Visual description and style breakdown (OpenAI Vision)

SEO-rich, long-form listing descriptions (GPT-4+)

Title, tags, and attribute suggestions

Optional: future quality checks, mockup suggestions, auto-tagging

4.2 Model Access, API Key Handling & Versioning
API keys are stored securely via .env or system secrets and loaded by the FastAPI app on boot.

Model version is fully configurable: e.g., OPENAI_MODEL=gpt-4.1 in .env or via UI.

Fallback logic is built in: if the preferred model fails, the app will attempt the previous stable or supported version automatically (e.g., gpt-4-turbo).

4.3 AI Workflow in Practice
A. Visual Analysis (Vision API)
When a new artwork is uploaded, its file path is passed to the vision analysis function.

The image is submitted to OpenAI Vision, which returns a rich description: subject, colours, composition, techniques, even "vibe."

Output is validated—missing fields or "null" responses are flagged for manual review.

B. Prompt Engineering for Listing Generation
The result from vision analysis is plugged into a master prompt template (etsy_master_template.txt) which also incorporates:

AI profile settings (e.g., Aboriginal art, Aussie nature, etc. as per settings.json)

Required tone (Aussie humour, professional curation language, etc.)

Minimum word count, CTA phrases, and cultural notes as needed

This prompt is dynamically constructed by artwork_analysis_service.py, using reusable content blocks for things like aspect ratio, dot art history, etc.

C. OpenAI Chat/Completion Call
The prompt is sent to the OpenAI API (GPT-4.1 or latest), with all required parameters set.

Results are checked for format (no HTML, CSV-safe, proper paragraphing, no forbidden phrases).

If the AI output fails any checks, the process is repeated or manual review is flagged.

D. Output Handling
The generated title, description, tags, and analysis metadata are saved to the artwork record.

If mockup suggestions or image-specific tags are generated, these are attached to the artwork or added as structured fields.

4.4 Reusable Content Blocks & Prompt Structure
Content blocks for listing prompts (e.g., “Dot Painting History,” “Aspect Ratio Explainer,” “Aussie Wildlife References”) are kept modular in /utils/content_blocks.py for easy update or reuse.

The master prompt template is centralized in master_listing_templates/etsy_master_template.txt and never includes HTML (critical for CSV export).

Prompts can be extended with context or user overrides at runtime (e.g., user-specific art themes or special campaign instructions).

4.5 Quality & Ethics
Aboriginal and Indigenous content: AI is prompted to follow cultural sensitivity, never overstep, and always preference user-supplied stories if available.

All outputs are required to follow platform and business rules: word count, tone, no banned phrases, and full attribution.

Future versions will integrate AI-driven quality checks (e.g., does the generated description match the visual? Are there inconsistencies between title and tags?).

4.6 AI Audit & Logging
Every AI call (input prompt, output, model, duration, success/failure) is logged to the database or a log file.

Logs include:

Timestamp

User/requestor

Model version

Prompt content (scrubbed for secrets)

Output snippet or error message

This enables full traceability for debugging, improvement, or regulatory review.

4.7 Extensibility
The AI layer is abstracted—new providers (e.g., Gemini, local models, third-party APIs) can be slotted in with minimal refactor.

Prompt logic and templates are versioned and tracked for A/B testing or continuous improvement.

All user and AI-generated content is saved separately for transparency and easy override/rollback.


5. Image and File Management
5.1 Overview of File Flow
DreamArtMachine implements a robust, multi-stage file handling workflow to support image integrity, traceability, and automated processing:

Upload Stage

Images are first placed in /art-uploads/temp-processing/[unique-id]/.

Original filenames are preserved on disk for traceability, with the upload timestamp and user tracked in the database.

Temporary directories are uniquely generated for each artwork to prevent conflicts and enable parallel processing.

Processing Stage

Images undergo validation (file type, size, corruption check) and then are queued for AI vision analysis and preview generation.

Any mockups, thumbs, or OpenAI variant images are generated in this temp folder and linked to the main artwork record.

Finalization Stage

Once analysis is complete and the artwork is accepted/finalized, all related files are moved to their permanent location under /analysed-artwork/[seo_folder]/.

Strict naming conventions are enforced:

Main artwork: {seo_filename}.jpg

Thumbnails: {seo_filename}-thumb.jpg

OpenAI variant: {seo_filename}-openai.jpg

Mockups: {seo_filename}-MU-01.jpg … -MU-10.jpg

5.2 Directory Structure
Uploads:
/home/dream/dreamartmachine/art-uploads/temp-processing/[unique-id]/

Finalized Artworks:
/home/dream/dreamartmachine/analysed-artwork/[seo_folder]/

Mockups (input/output):
/home/dream/dreamartmachine/mockup-generator/Input/Mockups/

Exports & CSVs:
/home/dream/exports/Composites/
(Or user-specified location for final exports/Nembol/Etsy CSVs.)

5.3 Naming & Metadata Rules
SEO Filename is the single source of truth for all finalized files (created automatically or supplied by user).

All generated files reference the artwork’s unique database ID, original filename, and final SEO filename for full traceability.

Any manual renames or corrections are reflected in both disk structure and DB fields.

5.4 URL Generation & Serving
Static URLs for finalized artwork are mapped to /static/analysed-artwork/ (served by FastAPI or Nginx).

Temp file URLs are mapped to /static-temp-uploads/ and include cache-busting query params based on the file’s last-modified timestamp.

Functions for URL generation (get_artwork_display_url, etc.) always prefer the latest, valid, on-disk file, falling back to placeholders if not found.

5.5 Thumbnail & OpenAI Variant Generation
Thumbnails are auto-generated via Pillow or AI-driven resizing and stored alongside the main image.

OpenAI variant is optionally generated if requested or required for AI comparison/optimisation.

All variants follow strict naming:
{seo_filename}-thumb.jpg, {seo_filename}-openai.jpg.

5.6 File Move & Cleanup Logic
When an artwork is finalized, all files are atomically moved to their target folders—failure in any part triggers rollback or admin alert.

Temporary upload directories are purged after successful finalization or at scheduled intervals, keeping disk usage lean.

Old, orphaned, or abandoned uploads are regularly scanned and removed by automated scripts.

5.7 Error Handling, Logging & Recovery
Every file move, rename, or deletion is logged (with user, time, and file paths).

If a file move fails, the user is alerted via the UI and given clear next steps (retry, admin contact).

Corrupt or unreadable images are flagged immediately for admin attention and cannot proceed to mockup/finalization.

5.8 Extensibility & Best Practices
Folder and filename rules are future-proofed—new variants or mockup types can be added without breaking existing logic.

Cloud storage or CDN integration (e.g., S3, Azure Blob) is supported via settings—switchable with minimal code changes.

Image metadata (EXIF, ICC profiles, etc.) is preserved where possible and can be surfaced in admin or export views.


6. Database, Models & State Management
6.1 Overview
DreamArtMachine uses a structured, normalized database—currently SQLite for local/test use, but ready for Postgres or MySQL in production. SQLAlchemy is the ORM of choice, with Pydantic models for FastAPI data validation and API responses.

6.2 Key Database Tables
artworks

Primary record for all uploaded and processed artwork.

Fields include:
id, original_filename, seo_filename, sku, user_id,
artwork_base_folder_path, original_file_storage_path,
renamed_artwork_path, thumb_path, openai_image_path,
status, created_at, finalized_at, updated_at,
generated_title, ai_analysis_profile_key, listing_profile_key,
mockup_selection, etc.

users

All user logins with secure password hashes.

Fields: id, username, email, hashed_password, is_active, is_superuser, created_at, updated_at, ai_analysis_profile_key, etc.

mockup_template_metadata

Stores info about available mockup templates (style, type, enabled/disabled).

Includes template file references, tags, and preview image paths.

(Planned/Optional)

exports: Tracks exported CSVs or listings for auditing.

activity_log: All key actions for traceability (uploads, edits, AI calls, file moves).

6.3 ORM & Models
SQLAlchemy ORM provides Python classes for each table—relationships (e.g., user → artworks) are mapped with foreign keys.

Pydantic schemas wrap the models for validation of input/output in API routes (robust and type-safe).

Database migrations (e.g., Alembic) ensure schema evolves smoothly without breaking data.

6.4 State Transitions & Artwork Status
Every artwork record maintains a clear status:

uploaded, processing, analyzed, finalized, ready_for_export, exported, error_*

Status transitions are atomic—changes to both the DB and file system happen together.

If any step fails (file move, AI call, export), the status is set to error_* with details for debugging and user notification.

6.5 Data Consistency & Recovery
Artwork records always track their current file paths; any file move triggers a DB update.

Orphaned DB records (e.g., if files are lost) are flagged and shown in admin.

Manual admin tools/scripts exist for fixing broken state, retrying failed steps, or purging abandoned records.

6.6 Extensibility & Future-Proofing
Table and field structure is designed for painless extension (e.g., more AI analysis fields, additional mockup types, versioned exports).

Supports multi-user, multi-role workflows (artist, reviewer, admin, exporter).

Ready for migration to managed DBs (RDS, Cloud SQL) and scaling up to millions of records.

6.7 Data Export & Integration
Database fields are mapped for seamless export to CSV for Nembol/Etsy—field mapping is centralized and configurable.

Every exported listing is traceable back to its original artwork record.

Planned: export logs and rollback support for compliance or bulk editing.


7. AI & Content Generation Pipeline
7.1 Overview
DreamArtMachine’s heart is its AI-driven pipeline, which handles everything from image analysis to Pulitzer-worthy Etsy listing copy. The system leverages OpenAI’s GPT-4 Vision (and ready for Gemini and others), running each artwork through a multi-stage process—analyzing visuals, extracting attributes, and generating high-converting product listings with a uniquely Aussie and Aboriginal-flavoured tone.

7.2 Analysis & Listing Workflow
Artwork Uploaded

Triggers automatic queuing for analysis.

Visual Analysis

AI (OpenAI Vision) interprets the artwork’s image file directly from disk.

Outputs detailed natural-language descriptions, colors, style, composition, and more.

For dot paintings, it prompts for Aboriginal art history/context (if appropriate).

Metadata Extraction

AI generates suggested SEO title, tags, colour palette, and identifies textures/styles for the artwork.

Also produces technical data (dimensions, aspect ratio) and content for mockup captions.

Etsy Listing Generation

AI composes a 400+ word, CSV-safe, text-only (no HTML) description.

Description adheres to the “Robbie Mode™” prompt:

No generic “realistic”/“immerse yourself” phrases

Fun, warm, Aussie humour and heartfelt tone

Deep art curation language (methods, texture, palette)

Aboriginal stories if appropriate

“Add to ya shopping basket” style CTAs

EEAT (Expertise, Experience, Authority, Trustworthiness) principles baked in

Each listing profile (Aboriginal Dot Art, Flora Art, Wildlife Art, etc.) has a corresponding AI prompt block (centralized in settings.json and template files).

Listing Review & Export

Generated text is reviewed (manual or AI bot) for tone, formatting, and compliance.

On approval, all listing data and images are bundled for CSV/Nembol/Etsy export.

7.3 Prompt Engineering & Content Blocks
Centralized Prompt Management

etsy_master_template.txt serves as the master prompt for all Etsy copywriting.

Profile-specific prompts are stored in settings.json for quick swaps between art styles and platforms.

Reusable Content Blocks

Modular “blocks” for dot painting history, aspect ratio, palette analysis—plugged in or left out by profile.

Ensures each artwork’s listing is unique, richly detailed, and culturally sensitive.

7.4 API Integration & Model Selection
OpenAI API (default)

Model: gpt-4.1 (configurable, with fallback to gpt-4-turbo etc.)

Uses both text and vision endpoints as needed.

Future Expansion

Gemini, Claude, Mistral, or custom AI endpoints can be added via the backend dispatcher.

Multi-provider logic built in for instant failover if an API is unreachable or hits quota.

7.5 Content Quality & Review System
Manual & Automated Review

Listings can be flagged for review if tone, length, or structure don’t meet standards.

AI “listing QA” bot (planned) can spot-check and auto-suggest edits or highlight cultural compliance risks.

Audit Log

All AI calls, prompt texts, and outputs are logged with timestamp and artwork ID for full traceability.

7.6 Future-Proofing AI
All prompt templates, profiles, and model parameters are versioned.

Easily add new profiles (e.g., “Contemporary Aboriginal”, “Aussie Surrealism”) without breaking existing workflow.

Automated test suite covers listing generation, ensuring output matches all current prompt logic and compliance rules.


8. Mockup Generation, Review & Finalization
8.1 Overview
Mockups are critical to DreamArtMachine’s “gallery feel” and conversion rate. The system automates high-quality wall art previews for each artwork—generating, organizing, and managing mockups so you (or your partners) always have stunning, ready-to-export assets.

8.2 Mockup Generation Workflow
Artwork Submission

When new artwork is uploaded and analyzed, it is instantly queued for mockup generation.

Template Selection

System supports a growing library of mockup templates (living room, nursery, modern apartment, rustic, etc.).

Templates can be classified by room type, orientation, and style—each tagged and previewed in the UI for easy selection.

Automated Mockup Creation

AI or script-driven image compositing overlays each artwork onto selected backgrounds.

Output files named using strict SEO conventions (seo-name-MU-01.jpg, etc.), all auto-stored in a temp-processing folder.

Thumbnails and AI-optimized variants are generated for each mockup batch.

Batch Review UI

All mockups in the batch appear in an easy-to-use “review” screen, showing full-size previews, filenames, and variant tags.

Each can be accepted, rejected, renamed, or edited in-batch.

Batch metadata, including aspect ratio, template used, and colour theme, is logged with the artwork in the database.

8.3 Finalization & Storage
Finalizing Mockups

Once the best mockups are selected, the “finalize” process:

Moves files from temp to permanent /finalised-artwork/{seo_folder}/ folder

Applies enforced filename and folder naming rules

Deletes unselected variants and old temp files

Updates database records with final paths, thumbnail, and mockup metadata

Export-Ready Structure

Every finalized artwork now lives in its own SEO-friendly subfolder:


/finalised-artwork/{seo-folder}/
   {seo_filename}.jpg
   {seo_filename}-MU-01.jpg
   {seo_filename}-MU-02.jpg
   ...
   {seo_filename}-thumb.jpg
   {seo_filename}-openai.jpg
Ensures direct compatibility for Etsy CSV export, Nembol batch uploads, and other marketplaces.

Quality Checks

Finalization logic checks for missing or duplicate files, validates image sizes, and logs any issues.

QA bot (planned) will automatically spot-check batches for consistency or watermark issues.

8.4 Mockup Template Management
Central Template Repository

Templates are managed as image assets in /mockup-generator/Input/Mockups.

Each template has metadata (orientation, style, tags) and preview image.

Adding/Editing Templates

Admin UI supports drag-n-drop for new templates, with instant preview.

Template metadata is stored in the DB for filtering and fast searching.

Versioning

Template updates don’t overwrite live templates—instead, new versions are added, with full audit history.

8.5 Future Improvements
AI-Driven Template Matching

Future: Automatically suggest best mockup backgrounds based on artwork style, colour palette, and market trends.

Bulk/Partner Mode

Designed to handle entire batches (e.g., 100+ artworks) with a single click—partners can get exclusive preview sets with their branding.

Auto-Export

Finalized mockups can be zipped and batch-exported directly for partner libraries or API handoff (coming soon).


9. CSV Export, Etsy/Nembol/Partner Integration
9.1 Overview
DreamArtMachine is engineered to make exporting, listing, and syndicating artwork across multiple marketplaces (Etsy, Nembol, and B2B partner shops) completely painless and error-free. Everything from SKU to mockup image URLs, SEO titles, and ready-to-go descriptions is built into the workflow.

9.2 Etsy CSV Export
CSV File Generation

System automatically builds Etsy-compliant CSV files for bulk upload.

All listing fields (title, description, price, tags, mockup image URLs, etc.) are generated or filled from the database.

Only finalized, “ready for export” artworks are included.

SEO & Compliance

Titles, descriptions, and tags are AI-generated using your Pulitzer-worthy, culturally aware templates.

No HTML; clean, CSV-safe text only.

Strict adherence to Etsy’s field limits and requirements (e.g., no duplicate images, correct ordering, 13 tags, no forbidden words).

Image Linking

Image columns auto-fill with URLs that map to your finalized mockups and main artwork, formatted for direct Etsy use.

Thumbnails, AI variants, and OpenAI-enhanced previews are included where relevant.

9.3 Nembol Export
Direct Nembol Integration

CSVs or JSON files can be exported in Nembol format, including all mockup images, metadata, and category mappings.

Supports partner-specific pricing, SKU prefixes, or “exclusive” tags as needed.

Automation-Ready

Batch process: select a group of artworks, click “Export for Nembol,” and get a validated file in seconds.

Future: API sync direct to Nembol or via webhooks for fully automated product sync.

9.4 B2B & POD Partner Library Export
Custom Packages

Partners can receive exclusive, non-exclusive, or white-label art packs in their chosen format (CSV, JSON, ZIP).

Licensing, usage, and exclusivity status is tracked in the DB and exported alongside image and metadata files.

Flexible Structure

Export logic adapts fields and templates to partner requirements (e.g., Shopify, WooCommerce, Gelato.com, or unique in-house formats).

Bulk Export

Any set of artworks (filtered by profile, collection, partner, etc.) can be instantly exported with all image assets bundled and correctly mapped.

9.5 Quality Assurance for Exports
Pre-Export Checks

Built-in verification before export: checks for missing images, title/description length, tag count, empty fields, and CSV/JSON validity.

Any detected issues are flagged for easy fix in the admin UI.

Human-Readable Reports

Every export generates a summary report (CSV row counts, missing fields, warnings), archived for future reference.

9.6 Automation and Integration Roadmap
Scheduled Exports

Future: System will auto-schedule daily/weekly partner exports for your top resellers and update feeds as new artwork goes live.

API Integration

Partner integration roadmap includes push-to-marketplace and webhook triggers for new drops, instant inventory updates, and custom partner dashboards.

Export Templates

Export template system allows custom mapping and logic per partner—no more “one-size-fits-none” headaches.



10. Quality Assurance, AI Checks & Automation
10.1 Automated Quality Control (QC) at Every Stage
Image & Data Integrity

As each artwork moves through the pipeline (upload, analysis, mockup, export), DreamArtMachine performs automated checks:

Ensures original, thumbnail, mockup, and AI-variant images exist and are valid images (not corrupted, not 0 bytes, right aspect ratio).

Checks for duplicate or missing files.

Validates that each record in the database has a matching file on disk (bi-directional integrity).

Filename & Path Validation

Every image is checked to conform with strict naming conventions (e.g., seo-filename-MU-01.jpg).

Storage paths are validated—no images left stranded in temp folders or missing from finalized folders.

10.2 AI-Driven Listing & Metadata QA
Automated Listing Review

AI bots re-read generated Etsy/Nembol/Partner descriptions, titles, tags, and SEO metadata for:

Keyword density.

No forbidden phrases or formatting (e.g., “realistic”, “immerse yourself”).

Proper use of Aboriginal story elements, colour and texture analysis, and professional curation language.

CTAs and style checks (e.g., always “add to ya shopping basket” or equivalent).

Cultural & Legal Checks

Ensures all Aboriginal content is culturally appropriate and non-offensive.

Flags any potential copyright or licensing conflicts before export.

10.3 Workflow “Traffic Lights” & Error Highlighting
Visual Indicators

Each artwork gets a status (“ready for mockup”, “QC fail”, “finalized”, “exported”, etc.) visible in the admin dashboard.

Failed QC steps are highlighted with reasons (e.g., “thumbnail missing”, “mockup count low”, “SEO tags missing”).

Batch Actions

Bulk-fix tools allow you to re-run QA or AI checks for whole folders or batches of artworks with one click.

10.4 Export Pre-Check & Final Audit
Before Export:

The system runs a final pre-export audit:

Verifies all mandatory images and metadata exist and are accessible.

Runs AI re-check of titles/descriptions/tags for format and policy compliance.

Generates a “pre-flight” report listing any items needing manual attention.

Export Blockers

Listings with fatal errors (e.g., missing artwork file, description too short) are blocked from export, with error explanations and quick links to fix.

10.5 Human & AI Feedback Loops
Human Verification

You (or trusted staff) can manually approve, override, or flag any artwork or listing if the bot gets it wrong.

AI Suggestions

The AI proposes improvements for flagged issues (e.g., alternative CTAs, stronger tags, summary rewordings) and can auto-fix routine errors if enabled.

Change Log & Rollback

Every automated and manual QC action is logged, so you can review, audit, and roll back changes as needed.

10.6 Continuous Self-Improvement
Analytics Dashboard

System tracks QC failures, common errors, and recurring issues, letting you fine-tune your workflow or prompt templates.

Learning Loops

As you correct or approve AI suggestions, the system can learn from your feedback and improve over time—getting closer to “set-and-forget” reliability.


11. Security, Permissions & User Management
11.1 Authentication & Access Control
User Accounts

DreamArtMachine supports named user accounts for all system access.

Admin/root user (that’s you) has full privileges, including configuration, workflow overrides, and export authority.

Additional users can be granted limited or specific roles (e.g., “mockup team”, “curator”, “listing reviewer”).

Login Security

All logins require strong passwords; password hashes are stored securely (never plaintext).

Optional: Enforce 2-factor authentication (2FA) for admin or sensitive actions.

Session Management

Session cookies use secure, HTTP-only flags and can be set to expire automatically after inactivity.

Forced logout and session expiry available in case of suspected breach.

11.2 Permissions & Role-based Workflow
Granular Role Assignment

Each route/function can be restricted by user role. For example:

Only admins can finalize artwork or export listings.

Curators can approve or reject art but not change database records.

Mockup team can only access mockup-related screens and actions.

Audit Logs

Every login, edit, finalization, export, or admin action is logged with username, time, and action type.

Tamper-evident logs—admins can’t erase their own tracks.

Approval Workflows

Optional: Listings or image sets can require two-stage approval (e.g., AI pre-check then human sign-off).

11.3 Data Security & Privacy
Sensitive Data Handling

User passwords and session tokens are encrypted at rest.

API keys (OpenAI, partner integrations) are stored in environment variables or a secured config file, never hardcoded.

Exported CSVs and metadata do not contain any private user information—only what’s required for listings.

GDPR & Privacy Compliance

User data is never shared with third parties unless required for external integrations (e.g., Etsy API, Nembol).

Optional: Account deletion tools and data access/export requests if you onboard additional team members.

File Security

Uploaded images and files are stored in directories that are not directly web-accessible—served only via secure, permission-checked routes.

Temporary uploads are routinely purged.

11.4 System Security Practices
Regular Dependency Checks

Automated tools check for vulnerabilities in your Python/JS dependencies (e.g., pip-audit, safety, npm audit).

Warnings surface in the admin dashboard when updates are required.

Backup & Disaster Recovery

Nightly automated backups of the database and all image assets.

Restore tools included: Roll back to previous backups in case of data loss or system failure.

Server Security

VM-level firewalls block non-essential ports and restrict SSH to whitelisted IPs (optional).

Environment variables and credentials are not exposed to public logs or front-end code.

11.5 User Onboarding & Management
Admin Interface for User Management

Easily add, remove, or update users from the admin panel.

Set or reset passwords, assign roles, and review activity logs.

Notification & Alerts

Users get instant feedback on failed logins, access denied, or session expiry.

Admins are alerted to failed logins, permission escalations, or suspicious activity.

Help & Support

Built-in help/documentation for system users, including workflow overviews and troubleshooting guides.



12. Extensibility, Maintenance & Future-Proofing
12.1 Modularity & Extensible Design
Component-based Structure

DreamArtMachine is built around clear separation of concerns: routes, services, models, and utilities are in their own modules.

New features—such as additional export formats, print partners, or AI services—can be integrated with minimal disruption to existing workflows.

Plug-and-play Integrations

Art marketplace integrations (e.g., Gelato, Nembol, Printful) can be swapped or extended via well-documented interface points.

New AI models (e.g., Google Gemini, open-source vision models) can be dropped in as additional analysis providers without codebase rewrites.

Flexible Settings

Key options (like art styles, listing templates, export fields) are stored in JSON or config files rather than being hardcoded.

System can adapt to new business requirements by updating settings files, not Python code.

12.2 Maintenance & Upgrade Strategy
Routine Updates

System dependencies are reviewed regularly for security and performance updates.

Docker/venv setups ensure consistent environments and easy upgrades.

Code Health & Refactoring

All code follows strict section numbering, professional comments, and clear docstrings so future contributors (or AI code bots) can jump in quickly.

Outdated code and deprecated APIs are reviewed and replaced as needed, following a “no scaffolding, no dead code” rule.

Automated Testing

Key workflows (upload, analyze, finalize, export) are covered by automated tests (pytest).

Before each major release, run:

pytest -q
and check that all tests pass.

12.3 Backup, Recovery & Data Integrity
Regular Backups

Automated daily (or more frequent) backups for both database and media assets.

Backups are stored offsite or on separate storage, with easy tools to restore from any point.

Disaster Recovery

If the worst happens (hardware failure, data corruption), you can quickly restore from backups with minimal downtime.

Recovery steps are documented in your admin notes and help files.

12.4 Future-Proofing
API Versioning & Upgrade Path

All external integrations (OpenAI, Etsy, Gelato) use versioned API endpoints, so changes upstream won’t instantly break your system.

System designed to tolerate service failures gracefully and provide meaningful error messages.

Scalable Foundations

Runs on a VM today, but can move to containers, cloud infrastructure, or even managed PaaS if traffic or user base grows.

Minimal stateful dependencies—stateless code can be deployed or scaled as microservices if required.

Documentation & Onboarding

Every major component and workflow is documented in your project README and internal docs.

New contributors (human or AI) can follow clear TOCs and code comments to get started without lengthy hand-holding.

12.5 Vision for Long-term Success
Evolves with the Business

As your art business grows, DreamArtMachine grows with you: new workflows, new partners, more automation, or even a membership SaaS offering.

Community & Support

Designed to be maintainable by you or any future developer, with no “black box” code or vendor lock-in.

Support for adding new team members, contractors, or collaborators as needed, with permission controls and audit logs.



13. Known Limitations, To-Do List & Open Questions
13.1 Current Known Limitations
Manual Steps Remain

Some workflows (e.g., CSV review, artwork approval, certain mockup selections) still require human intervention and aren’t yet fully automated.

UI/UX Limitations

Admin interface is functional but very plain—minimalist by design, but may confuse non-technical users.

No “mobile first” responsive version; experience is best on desktop.

Bulk Operations

Batch uploads, bulk listing edits, or multi-artwork exports are possible but not yet fully optimized for huge libraries (e.g., 10,000+ artworks).

AI Model Selection

Current OpenAI integration is best-in-class for art analysis, but the system doesn’t yet auto-select models based on image content or fallback gracefully if API limits are hit.

Print Partner API Changes

Integrations like Gelato, Nembol, or Printful are subject to third-party API changes that could require code updates.

Security and Permissions

User authentication works, but fine-grained permission levels (e.g., admin vs staff vs guest) are basic and could be expanded.

Limited Multi-language Support

System is built for English; adding internationalization/multi-language workflows would require additional development.

Testing Coverage

Test coverage is solid for the “happy path” but edge cases, error handling, and rare race conditions may be under-tested.

13.2 To-Do List (Short & Medium Term)
Automate More Steps

Integrate AI or smart workflows for:

Automated approval of low-risk artworks

Automated CSV preview/validation

Automated duplicate detection (for artwork uploads)

Improve Mockup Generation

Support more complex, layered mockup templates

Enable preview/export of multiple mockup styles per artwork in one click

UI/UX Improvements

Add clear, persistent admin menu

Build a true mobile/tablet-friendly version

Integrate drag-and-drop file uploads

Advanced Export Workflows

Add batch export for Nembol/Etsy

Export directly to additional POD/marketplace partners

Notification & Status Tracking

Email or in-app notifications for key workflow events (analysis complete, export ready, errors)

Artwork status change logs and “activity feed”

Security Hardening

Add 2FA/multi-factor support for admin users

Refine user roles and permissions

Code & Docs

Expand and refine auto-generated docs

Regularly refactor and add/expand tests for edge cases

13.3 Open Questions & Future Ideas
AI Curation & Recommendations

Should the system recommend “next best” artworks for mockup generation or export, based on sales data or style analysis?

Explore integration with sales/analytics APIs (Etsy, Shopify) for smarter automation.

User Roles & Collaboration

Should the system support multiple artists or “guest contributors,” with artwork ownership and approval workflows?

Marketplace Expansion

What other platforms (Redbubble, Saatchi Art, Society6) should be added for direct listing/export?

Scaling for Volume

What are the next steps if artwork count grows by 10x or 100x? Consider cloud storage, CDN for images, etc.

AI Model Choice & Competition

How to best evaluate emerging AI image analysis/generation models and switch between them (or blend outputs)?

Full API-First Design

Should the system expose a public API (for partners, automation, etc.) or stay as an internal tool?

Licensing & Membership

If offering the platform as a SaaS to other artists, what features or controls are required for multi-tenant, membership-based usage?



14. Integrating Latest Reports, Snapshots & System Checks
14.1. Purpose and Overview
Regular reporting, code snapshotting, and automated system checks are key for maintaining confidence in project health, diagnosing problems, and supporting efficient development—especially when working with a fast-evolving or AI-assisted codebase.

This system incorporates a custom reporting script (a-total-nuclear.py report) that outputs a set of comprehensive checks and artifacts covering every critical aspect of the application and environment. These outputs are designed for both human review and future AI/automation integrations.

14.2. Types of Reports Generated
When the reporting script is executed, it generates and saves the following artifacts (usually in a timestamped reports/ subdirectory):

Code Snapshot (report_code_snapshot_YYYY-MM-DD_HH-MMam/pm.md)

Markdown dump of the current codebase, including directory trees and file listings. Useful for version review or debugging code state at any point in time.

Folder Tree (report_folder_tree_YYYY-MM-DD_HH-MMam/pm.txt)

Full text outline of the directory structure, highlighting locations of key assets, templates, and data files.

Combined Summary Report (report_combined_summary_YYYY-MM-DD_HH-MMam/pm.txt)

Plain English rollup of all major checks, including which components are present, status of routers/templates/config, any anomalies, and direct links/paths to relevant files.

Database Schema Report (report_db_schema_YYYY-MM-DD_HH-MMam/pm.txt)

Export of the current SQLite database schema for tables, fields, types, and indexes. Critical for verifying expected DB structure after migrations or updates.

Environment File Check

Confirmation that all required .env variables are set and correct (API keys, DB URLs, etc.).

OpenAI API Health Check

Quick verification that OpenAI API credentials are valid and connectivity is working.

14.3. System Health & Integrity Checks
Key checks run automatically and included in every report:

Route, Template, and Config File Discovery

Ensures all expected route, template, and config files exist and are in the right locations. Flags missing or extra files for manual review.

Python Syntax Validation

Scans all project Python files for syntax errors to catch issues before deployment or test runs.

Database File & Schema Checks

Verifies that the SQLite database exists, is accessible, and matches the expected schema.

Pip Package Status

Reports on outdated packages in the current virtual environment, making it easy to keep dependencies up to date and secure.

14.4. Usage in Day-to-Day Workflow
Pre-deployment Checklist

Always run the report script before deploying updates or major code merges. Review for missing files, errors, or config drift.

Debugging Aid

Use code and folder snapshots to roll back or diagnose complex bugs (“what changed since last good run?”).

Audit Trail

Saved reports provide an auditable trail of changes, config, and system health over time. Great for accountability or onboarding new devs.

AI/Assistant Friendly

All outputs are plain text or markdown—easy for future bots (or humans) to parse, search, or use as context for further troubleshooting or code generation.

14.5. Potential Improvements
Automated Alerts

Hook the report script into a notification system (email, Slack, etc.) for instant alerts when something critical changes or breaks.

Automated Rollbacks

With enough history and snapshotting, build an automated “restore last good state” command if a bad deploy is detected.

Report Comparison

Develop tools/scripts to diff two reports and highlight only what changed—very handy for large projects.

Direct Integration with Codex/AI Assistants

Allow bots to request or parse latest reports as “system context” for advanced troubleshooting, code generation, or documentation tasks.



15. Project Philosophy & Guiding Principles
15.1. Big Picture Approach
The DreamArtMachine project is built around a philosophy of automation, reliability, and continuous improvement—balancing creative control with robust systems engineering. The system is meant to serve not just the current needs of its creator, but to be flexible and future-proof enough for expansion, collaboration, and even AI-powered co-piloting.

15.2. Core Guiding Principles
A. Maintainability

Full File Edits: Always prefer full-file rewrites over code snippets or patchwork. Every update should result in a self-contained, easily-reviewed module.

Sectioned, Documented Code: All code and documentation should use clear section headers, comments, and unique section codes. No “magic numbers” or hidden logic.

No Scaffolding or Skeleton Code: Only include real, working logic. If a feature is incomplete, explicitly mark it as such or stub it out safely.

B. Robustness

Syntax & Health Checks: Nothing gets merged or deployed without passing automated checks (syntax, routes, templates, configs, DB, etc.).

Auditability: System must produce audit trails—code snapshots, report logs, and clear commit histories.

C. Transparency

Every Change is Explained: All significant code or config changes should be documented, preferably with clear commit messages and changelogs.

Clear Structure: Directory trees and code architecture should be easily navigable by humans and bots alike.

D. Automation First

Reporting, Testing, Linting: Where possible, automate mundane but critical processes (pre-deployment checks, test runs, code formatting, etc.).

Room for AI Co-Pilots: System is designed so AI tools (like Codex or ChatGPT) can understand, extend, or repair it without “insider knowledge.”

E. Minimal Friction for Creators

Simple UI/UX: Minimalist interfaces for workflow, easy navigation, and low cognitive load.

Batch Actions & Mass Edits: Designed for creators who handle hundreds or thousands of artworks at once, not just single uploads.

15.3. Commitment to Quality
No Placeholder Logic: If a feature is still under construction, it must be clearly marked and isolated—never break the main workflow.

No Data Loss or Regression: Migrations and updates must preserve all existing data, filenames, and structure unless a full backup is taken and confirmed.

Consistent Naming & Structure: All files, folders, and database fields use established conventions (e.g., SEO-named folders, artwork IDs, etc.).

15.4. EEAT & Professional Standards
Expertise, Authoritativeness, Trustworthiness (EEAT):

Listings, documentation, and UI text always reflect deep knowledge, real artistic practice, and cultural respect (especially with Aboriginal art or stories).

Accessibility & Respect:

All user-facing text and imagery should be welcoming, humorous (where appropriate), and professional—never culturally insensitive or exclusionary.

Production-Ready:

Code, templates, and outputs are always kept at “production ready” standard—even for small fixes or updates.

15.5. The “Robbie Mode™” Standard
A unique protocol for this project, “Robbie Mode™” means:

No content truncation.

No partial updates.

Every output and file rewrite must be complete, fully documented, and auditable.

Every change is reversible or tracked.

AI, automation, and humans must all be able to confidently extend, repair, or review the system at any stage.



16. Future Vision: Roadmap, Expansion & AI Co-Pilot Goals
16.1. End Game & “Members Only” Platform
DreamArtMachine is not just a personal tool— it’s built to become a robust, scalable members-only platform for professional artists and art sellers once workflows are fully tested and stable.

Step-by-step activation: First, finalize and polish all core workflows and quality controls for internal use. When proven, onboard trusted early members, then eventually open up to a broader art community with strict onboarding.

Premium/Exclusive Features: Future iterations could offer tiered access, exclusive art libraries, priority support, advanced analytics, and AI-powered creative tools.

16.2. Workflow Automation & Expansion
Full Workflow Automation: Every step, from artwork upload through mockup generation, curation, and listing export, will be as automated as possible—with safety checks and manual overrides.

Quality Assurance Bots:

Integrated AI agents will constantly check for file integrity, metadata accuracy, and compliance with export requirements (Etsy, Nembol, etc.).

Automated “pre-flight” checklists before any major export or bulk operation.

One-Click Publishing: Ultimate goal is that a creator can, with one click, safely push hundreds of artworks to all supported platforms, fully optimized and quality checked.

16.3. AI Co-Pilot & “Codex-Driven” Development
AI as a True Team Member:

The entire project is structured for AI co-pilots (like OpenAI Codex and ChatGPT) to help fix, extend, or optimize any part of the workflow—using clear code, section headers, and permanent section codes.

Routine “project health checks” and updates can be run by AI scripts, with transparent reporting and reversible actions.

Continuous Improvement:

The platform will learn from usage data, feedback, and common errors—so AI tools can suggest enhancements or spot bottlenecks in real time.

Documentation and templates always updated to the latest best practices, with input from both AI and human contributors.

16.4. Extensibility & Integration
New Features:

Modular structure makes it easy to add new analysis models (Gemini, Midjourney, etc.), support more print-on-demand services, or introduce batch video generation.

API-First Approach:

All core functions are exposed via a documented API, allowing for external integrations, partner services, or even white-label deployments in the future.

Plug-in System (Planned):

Artists and tech-savvy users can develop and share workflow plug-ins, analysis profiles, or mockup templates without breaking the core.

16.5. Long-Term Ethical & Cultural Commitments
Cultural Respect:

Continued focus on cultural safety, especially for Aboriginal and First Nations art. Ongoing consultation and permission protocols will be maintained as the system grows.

Data Privacy:

User and artwork data will be protected with strong access controls, transparent usage logs, and a clear opt-out for analytics or AI training.

Community-Driven Development:

Feature requests, bug reports, and improvements will be openly tracked and prioritized by both user demand and ethical priorities.

16.6. Final Notes on Expansion
Ready for the Unexpected:

System design anticipates that art, technology, and business needs will change—so everything from storage to interface can be upgraded with minimal drama.

Documentation & Onboarding:

Step-by-step guides, inline help, and AI onboarding wizards will help new members (and future bots) hit the ground running.



17. Appendices, References & Changelog Protocol
17.1. Reference Documents & Key Resources
Main Project Documents:

Full-Rundown.txt (this master system description, always kept up to date)

report_code_snapshot_YYYY-MM-DD_HH-MM.md (auto-generated source code snapshots)

report_combined_summary_YYYY-MM-DD_HH-MM.txt (operation & audit summaries)

report_folder_tree_YYYY-MM-DD_HH-MM.txt (folder structure and file presence)

report_db_schema_YYYY-MM-DD_HH-MM.txt (database schema at a glance)

Templates & Configuration:

/master_listing_templates/etsy_master_template.txt

/data/settings.json (listing profiles, AI configs)

/core/config.py (all project path, key, and setting definitions)

Where to Find Them:

All reports, changelogs, and snapshots are saved in the /reports/ directory, time- and date-stamped.

Key templates and configs live in their respective /data/ and /master_listing_templates/ folders.

Pro tip: Automated health check scripts will always output where the latest report versions are.

17.2. Changelog Protocol & Documentation Practice
Commit Messages:

Every code update must be accompanied by a detailed commit message (see previous examples)—summarizing purpose, scope, and affected areas.

Significant workflow or system-level changes should reference which section(s) of the master system document they affect.

Change Documentation:

Any major process or logic revision should trigger an update to Full-Rundown.txt (or its next version), with the revision date and a summary of what’s changed.

All documentation changes are version-controlled, and a rolling changelog is maintained at the end of the master doc.

Changelog Format Example:

## Changelog
[2025-06-13] - Added Section 16: AI Co-Pilot Roadmap and Future Vision
[2025-06-10] - Refactored analyze_routes.py for new file storage logic
[2025-05-27] - Initial DreamArtMachine workflow established
Code Comments & Section Markers:

All production code must use structured section headers and sub-section markers, e.g.:

# === [ Section 5: Export Workflow | export-py-5 ] ===
Permanent section codes are not to be changed—this enables automated doc/code alignment and search by both human and AI.

Automated Reports & Snapshots:

Before any big deployment, run a-total-nuclear.py report to generate current code, config, and DB snapshots.

Save all output in /reports/—this provides full rollback points and audit history for both code and documentation.

17.3. Protocol for AI-Assisted Collaboration
Codex/AI Protocol:

All future AI collaborators (Codex, ChatGPT, Gemini, etc.) are to:

Thoroughly read the master system doc before major interventions.

Always reference which section(s) their proposed code or doc changes touch.

Avoid “scaffolding”—only write or rewrite full sections/files with complete, production-ready logic.

Never remove section codes, table of contents, or documentation structure.

Human & AI Onboarding:

Anyone (or any bot) contributing to the project should start by reading the latest Full-Rundown.txt and all major templates/configs.

Quickstart checklists and inline documentation are prioritized to flatten the learning curve.

17.4. Final Words
Everything is a living document:

DreamArtMachine will keep evolving—system documentation, workflow guides, and templates should always be kept fresh, clear, and detailed.

Feedback, corrections, and improvements (from anyone, including bots!) are not just welcome, they’re expected.

If in doubt:

If a process, template, or piece of code isn’t clear or seems outdated, mark it for review and propose an update in the changelog.

System health above all:

Robust automation, rollback, and reporting are more important than fancy features—reliability, cultural respect, and user safety are the foundation.
```

---
## 📄 tests/test_csv_header.py

```py
import csv
from pathlib import Path

import scripts.sellbrite_csv_export as sb


def test_template_header_matches_file():
    template = Path('csv_product_template.csv')
    expected = sb.read_template_header(template)

    with open(template, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
        actual = [h.strip() for h in rows[2]]

    assert expected == actual

```

---
## 📄 tests/test_utils_cleaning.py

```py
import pytest
from routes import utils
from routes.artwork_routes import validate_listing_fields


def test_clean_terms():
    cleaned, changed = utils.clean_terms(["te-st", "b@d"])
    assert cleaned == ["test", "bd"]
    assert changed


def test_read_generic_text():
    txt = utils.read_generic_text("4x5")
    assert txt.strip() != ""


def test_validate_generic_error_message():
    generic = utils.read_generic_text("4x5")
    data = {
        "title": "t",
        "description": "short description",
        "tags": ["tag"],
        "materials": ["mat"],
        "primary_colour": "Black",
        "secondary_colour": "Brown",
        "seo_filename": "Test-Artwork-by-Robin-Custance-RJC-0001.jpg",
        "price": "17.88",
        "sku": "RJC-0001",
        "images": ["outputs/finalised-artwork/test/test.jpg"],
    }
    errors = validate_listing_fields(data, generic)
    joined = " ".join(errors)
    assert "correct generic context block" in joined


def test_validate_generic_present_with_whitespace():
    generic = utils.read_generic_text("4x5")
    base = "word " * 400
    desc = base + "\n\n" + generic + "\n   extra words after"  # within 50 words
    data = {
        "title": "t",
        "description": desc,
        "tags": ["tag"],
        "materials": ["mat"],
        "primary_colour": "Black",
        "secondary_colour": "Brown",
        "seo_filename": "Test-Artwork-by-Robin-Custance-RJC-0001.jpg",
        "price": "17.88",
        "sku": "RJC-0001",
        "images": ["outputs/finalised-artwork/test/test.jpg"],
    }
    errors = validate_listing_fields(data, generic)
    joined = " ".join(errors)
    assert "correct generic context block" not in joined


```

---
## 📄 tests/test_sku_assigner.py

```py
import json
from pathlib import Path

from utils.sku_assigner import get_next_sku, peek_next_sku


def test_peek_does_not_increment(tmp_path):
    tracker = tmp_path / "tracker.json"
    tracker.write_text(json.dumps({"last_sku": 2}))
    peek = peek_next_sku(tracker)
    assert peek == "RJC-0003"
    assert json.loads(tracker.read_text())['last_sku'] == 2


def test_get_next_sku_increments(tmp_path):
    tracker = tmp_path / "tracker.json"
    tracker.write_text(json.dumps({"last_sku": 10}))
    first = get_next_sku(tracker)
    second = get_next_sku(tracker)
    assert first == "RJC-0011"
    assert second == "RJC-0012"
    assert json.loads(tracker.read_text())['last_sku'] == 12


def test_cancel_does_not_consume(tmp_path):
    tracker = tmp_path / "tracker.json"
    tracker.write_text(json.dumps({"last_sku": 5}))
    preview = peek_next_sku(tracker)
    assert preview == "RJC-0006"
    # no assignment yet
    assert json.loads(tracker.read_text())['last_sku'] == 5
    final = get_next_sku(tracker)
    assert final == preview
    assert json.loads(tracker.read_text())['last_sku'] == 6

```

---
## 📄 tests/test_sku_tracker.py

```py
import json
import os
import shutil
from pathlib import Path
import sys
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("SKU_TRACKER_PATH", str(Path("/tmp/sku_tracker_default.json")))
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "scripts"))
from config import ARTWORKS_INPUT_DIR, ARTWORKS_PROCESSED_DIR
from unittest import mock
import analyze_artwork as aa
from routes import utils


class DummyChoice:
    def __init__(self, text):
        self.message = type('m', (), {'content': text})

class DummyResp:
    def __init__(self, text):
        self.choices = [DummyChoice(text)]


SAMPLE_JSON1 = json.dumps({
    "title": "First Artwork",
    "description": "Test description",
    "tags": ["tag"],
    "materials": ["mat"],
    "primary_colour": "Black",
    "secondary_colour": "Brown",
    "price": 18.27,
    "sku": "RJC-0000",
    "seo_filename": "first-artwork-by-robin-custance-rjc-0000.jpg"
})

SAMPLE_JSON2 = json.dumps({
    "title": "Second Artwork",
    "description": "Test description",
    "tags": ["tag"],
    "materials": ["mat"],
    "primary_colour": "Black",
    "secondary_colour": "Brown",
    "price": 18.27,
    "sku": "RJC-0000",
    "seo_filename": "second-artwork-by-robin-custance-rjc-0000.jpg"
})


def test_sequential_sku_assignment(tmp_path):
    tracker = tmp_path / 'sku_tracker.json'
    tracker.write_text(json.dumps({"last_sku": 80}))
    os.environ['SKU_TRACKER_PATH'] = str(tracker)
    aa.SKU_TRACKER = Path(os.environ['SKU_TRACKER_PATH'])

    # remove any pre-existing output folders from previous runs
    for folder in ('first-artwork', 'second-artwork'):
        shutil.rmtree(ARTWORKS_PROCESSED_DIR / folder, ignore_errors=True)

    img_src = next(ARTWORKS_INPUT_DIR.rglob('*.jpg'))
    img1 = tmp_path / 'a.jpg'
    img2 = tmp_path / 'b.jpg'
    shutil.copy2(img_src, img1)
    shutil.copy2(img_src, img2)

    responses = [DummyResp(SAMPLE_JSON1), DummyResp(SAMPLE_JSON2)]
    with mock.patch.object(aa.client.chat.completions, 'create', side_effect=responses):
        system_prompt = aa.read_onboarding_prompt()
        status = []
        entry1 = aa.analyze_single(img1, system_prompt, None, status)
        entry2 = aa.analyze_single(img2, system_prompt, None, status)

    # Analysis stage only previews the next SKU
    assert entry1['sku'] == 'RJC-0081'
    assert entry2['sku'] == 'RJC-0081'
    assert json.loads(tracker.read_text())['last_sku'] == 80

    # Finalising assigns sequential SKUs
    utils.assign_or_get_sku(Path(entry1['processed_folder']) / f"{entry1['seo_name']}-listing.json", tracker, force=True)
    utils.assign_or_get_sku(Path(entry2['processed_folder']) / f"{entry2['seo_name']}-listing.json", tracker, force=True)

    assert json.loads(tracker.read_text())['last_sku'] == 82

    with mock.patch.object(aa.client.chat.completions, 'create', return_value=DummyResp(SAMPLE_JSON1)):
        system_prompt = aa.read_onboarding_prompt()
        status = []
        entry1b = aa.analyze_single(img1, system_prompt, None, status)

    assert entry1b['sku'] == 'RJC-0081'

```

---
## 📄 tests/test_routes.py

```py
import re
from html.parser import HTMLParser
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href":
                    self.links.append(v)


def collect_template_endpoints():
    pattern = re.compile(r"url_for\(['\"]([^'\"]+)['\"]")
    endpoints = set()
    for path in Path("templates").rglob("*.html"):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        endpoints.update(pattern.findall(content))
    return endpoints


def test_template_endpoints_valid():
    registered = {r.endpoint for r in app.url_map.iter_rules()}
    templated = collect_template_endpoints()
    missing = [
        e for e in templated if e not in registered and not e.startswith("static")
    ]
    assert not missing, f"Unknown endpoints referenced: {missing}"


def test_routes_and_navigation():
    client = app.test_client()
    to_visit = ["/"]
    visited = set()
    while to_visit:
        url = to_visit.pop()
        if url in visited:
            continue
        resp = client.get(url)
        assert resp.status_code == 200, f"Failed loading {url}"
        visited.add(url)
        parser = LinkParser()
        parser.feed(resp.get_data(as_text=True))
        for link in parser.links:
            if link.startswith("http") or link.startswith("mailto:"):
                continue
            if link.startswith("/static") or "//" in link[1:]:
                continue
            if link == "#" or link.startswith("#"):
                continue
            link = link.split("?")[0]
            if link not in visited:
                to_visit.append(link)

    # Additional admin debug endpoints
    resp = client.get("/admin/debug/parse-ai")
    assert resp.status_code == 200
    resp = client.get("/admin/debug/next-sku")
    assert resp.status_code == 200

```

---
## 📄 tests/test_analyze_artwork.py

```py
import json
import os
from pathlib import Path
import sys
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "scripts"))
from config import ARTWORKS_INPUT_DIR
from unittest import mock
os.environ.setdefault("OPENAI_API_KEY", "test")
import analyze_artwork as aa


def dummy_openai_response(content):
    class Choice:
        def __init__(self, text):
            self.message = type('m', (), {'content': text})
    class Resp:
        def __init__(self, text):
            self.choices = [Choice(text)]
    return Resp(content)


def run_test():
    sample_json = json.dumps({
        "seo_filename": "test-artwork-by-robin-custance-rjc-0001.jpg",
        "title": "Test Artwork – High Resolution Digital Aboriginal Print",
        "description": "Test description " * 50,
        "tags": ["test", "digital art"],
        "materials": ["Digital artwork", "High resolution JPEG file"],
        "primary_colour": "Black",
        "secondary_colour": "Brown"
    })
    with mock.patch.object(aa.client.chat.completions, 'create', return_value=dummy_openai_response(sample_json)):
        system_prompt = aa.read_onboarding_prompt()
        img = next(ARTWORKS_INPUT_DIR.rglob('*.jpg'))
        status = []
        entry = aa.analyze_single(img, system_prompt, None, status)
        print(json.dumps(entry, indent=2)[:200])


if __name__ == '__main__':
    run_test()


```

---
## 📄 tests/test_export_tags_materials.py

```py
import csv
import os
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import scripts.sellbrite_csv_export as sb
import config


def test_export_tags_materials(tmp_path):
    template = tmp_path / "template.csv"
    header = [
        "SKU",
        "Name",
        "Description",
        "Price",
        "Quantity",
        "Condition",
        "Brand",
        "Category",
        "Weight",
        "Image 1",
        "Tags",
        "Materials",
        "Locked",
        "DWS",
    ]
    template.write_text(",".join(header))

    orig_template = os.environ.get("SELLBRITE_TEMPLATE_CSV")
    orig_tracker = os.environ.get("SKU_TRACKER_PATH")
    os.environ["SELLBRITE_TEMPLATE_CSV"] = str(template)
    os.environ["SKU_TRACKER_PATH"] = str(tmp_path / "tracker.json")
    Path(os.environ["SKU_TRACKER_PATH"]).write_text('{"last_sku": 1}')

    importlib.reload(config)
    importlib.reload(sb)

    listing = {
        "sku": "RJC-0001",
        "title": "Test",
        "description": "desc" * 50,
        "price": "10",
        "tags": ["a", "b", "c"],
        "materials": ["x", "y"],
        "images": ["img1.jpg"],
    }

    out_csv = tmp_path / "out.csv"
    sb.export_to_csv([listing], header, out_csv)

    rows = list(csv.DictReader(out_csv.open()))
    assert rows[0]["Tags"] == "a, b, c"
    assert rows[0]["Materials"] == "x, y"

    if orig_template is not None:
        os.environ["SELLBRITE_TEMPLATE_CSV"] = orig_template
    else:
        os.environ.pop("SELLBRITE_TEMPLATE_CSV", None)
    if orig_tracker is not None:
        os.environ["SKU_TRACKER_PATH"] = orig_tracker
    else:
        os.environ.pop("SKU_TRACKER_PATH", None)

    importlib.reload(config)
    importlib.reload(sb)

```

---
## 📄 tests/test_sku_utils.py

```py
import json
from pathlib import Path
from routes import utils


def test_assign_or_get_sku(tmp_path):
    tracker = tmp_path / 'sku.json'
    tracker.write_text(json.dumps({"last_sku": 5}))
    listing = tmp_path / 'art-listing.json'
    listing.write_text(json.dumps({"title": "Test"}))

    sku = utils.assign_or_get_sku(listing, tracker)
    assert sku == 'RJC-0006'
    assert json.loads(listing.read_text())['sku'] == sku
    assert json.loads(tracker.read_text())['last_sku'] == 6

    # Calling again should keep same SKU
    sku2 = utils.assign_or_get_sku(listing, tracker)
    assert sku2 == sku
    assert json.loads(tracker.read_text())['last_sku'] == 6


def test_assign_sku_updates_seo_filename(tmp_path):
    tracker = tmp_path / 'sku.json'
    tracker.write_text(json.dumps({"last_sku": 1}))
    listing = tmp_path / 'listing.json'
    listing.write_text(json.dumps({
        "title": "Test",
        "seo_filename": "Test-Artwork-by-Robin-Custance-RJC-0000.jpg"
    }))

    sku = utils.assign_or_get_sku(listing, tracker)
    data = json.loads(listing.read_text())
    assert sku == 'RJC-0002'
    assert data['sku'] == sku
    assert data['seo_filename'].endswith(f"{sku}.jpg")

    sku2 = utils.assign_or_get_sku(listing, tracker)
    data2 = json.loads(listing.read_text())
    assert sku2 == sku
    assert data2['seo_filename'].endswith(f"{sku}.jpg")
    assert json.loads(tracker.read_text())['last_sku'] == 2


def test_validate_all_skus(tmp_path):
    tracker = tmp_path / 'sku.json'
    tracker.write_text(json.dumps({"last_sku": 2}))

    good = [{"sku": "RJC-0001"}, {"sku": "RJC-0002"}]
    assert utils.validate_all_skus(good, tracker) == []

    dup = [{"sku": "RJC-0001"}, {"sku": "RJC-0001"}]
    assert any('Duplicate' in e for e in utils.validate_all_skus(dup, tracker))

    gap = [{"sku": "RJC-0001"}, {"sku": "RJC-0003"}]
    assert any('Gap' in e for e in utils.validate_all_skus(gap, tracker))

    missing = [{}, {"sku": "RJC-0002"}]
    assert any('invalid' in e for e in utils.validate_all_skus(missing, tracker))

```

---
## 📄 tests/test_upload.py

```py
import io
import json
from pathlib import Path
import os
import sys
os.environ.setdefault("OPENAI_API_KEY", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config
import scripts.analyze_artwork as aa
from unittest import mock


def dummy_openai_response(text):
    class C:
        def __init__(self, t):
            self.message = type('m', (), {'content': t})
    class R:
        def __init__(self, t):
            self.choices = [C(t)]
    return R(text)

SAMPLE_JSON = json.dumps({
    "seo_filename": "uploaded-artwork-by-robin-custance-rjc-9999.jpg",
    "title": "Test",
    "description": "desc",
    "tags": ["tag"],
    "materials": ["mat"],
    "primary_colour": "Black",
    "secondary_colour": "Brown"
})


def test_upload_single(tmp_path):
    client = app.test_client()
    img_path = next((config.ARTWORKS_INPUT_DIR).rglob('*.jpg'))
    data = img_path.read_bytes()
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': (io.BytesIO(data), 'test.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()
    tmp_files = list(config.UPLOADS_TEMP_DIR.glob('*.qc.json'))
    assert tmp_files, "QC file not created"


def test_upload_reject_corrupt(tmp_path):
    client = app.test_client()
    bad = io.BytesIO(b'notanimage')
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': (bad, 'bad.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    assert '\u274c'.encode() in resp.data or b'error' in resp.data
    m.assert_not_called()


def test_upload_batch(tmp_path):
    client = app.test_client()
    img_path = next((config.ARTWORKS_INPUT_DIR).rglob('*.jpg'))
    good = img_path.read_bytes()
    bad = io.BytesIO(b'bad')
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': [(io.BytesIO(good), 'good.jpg'), (bad, 'bad.jpg')]}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()
    qc_files = list(config.UPLOADS_TEMP_DIR.glob('*.qc.json'))
    assert len(qc_files) >= 1


```

---
## 📄 tests/test_ai_pipeline.py

```py
import json
import os
from pathlib import Path
from unittest import mock

import importlib
import sys

root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "scripts"))


def setup_env(tmp_path):
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ["LOGS_DIR"] = str(tmp_path / "logs")
    os.environ["PARSE_FAILURE_DIR"] = str(tmp_path / "pf")
    os.environ["OPENAI_PROMPT_LOG_DIR"] = str(tmp_path / "prompts")
    os.environ["OPENAI_RESPONSE_LOG_DIR"] = str(tmp_path / "responses")
    if "config" in sys.modules:
        importlib.reload(sys.modules["config"])
    if "scripts.analyze_artwork" in sys.modules:
        importlib.reload(sys.modules["scripts.analyze_artwork"])
    return importlib.import_module("scripts.analyze_artwork")


def dummy_resp(text):
    class C:
        def __init__(self, t):
            self.message = type("m", (), {"content": t})

    class R:
        def __init__(self, t):
            self.choices = [C(t)]

    return R(text)


SAMPLE_JSON = json.dumps(
    {
        "seo_filename": "test-artwork-by-robin-custance-rjc-9999.jpg",
        "title": "Test",
        "description": "desc" * 100,
        "tags": ["tag"],
        "materials": ["mat"],
        "primary_colour": "Black",
        "secondary_colour": "Brown",
        "price": 18.27,
        "sku": "RJC-9999",
    }
)


def test_markdown_wrapped_json(tmp_path):
    aa = setup_env(tmp_path)
    img = next((aa.ARTWORKS_DIR).rglob("*.jpg"))
    wrapped = "```json\n" + SAMPLE_JSON + "\n```"
    with mock.patch.object(aa.client.chat.completions, "create", return_value=dummy_resp(wrapped)):
        listing, raw, p_log, r_log, err = aa.generate_ai_listing(
            "prompt", img, "1x1", "RJC-9999"
        )
    assert listing and not err
    assert p_log.exists() and r_log.exists()


def test_retry_then_success(tmp_path):
    aa = setup_env(tmp_path)
    img = next((aa.ARTWORKS_DIR).rglob("*.jpg"))
    responses = [dummy_resp("not json"), dummy_resp(SAMPLE_JSON)]
    with mock.patch.object(aa.client.chat.completions, "create", side_effect=responses) as m:
        listing, raw, p_log, r_log, err = aa.generate_ai_listing(
            "prompt", img, "1x1", "RJC-9999"
        )
    assert listing and not err
    assert m.call_count == 2
    assert len(list((tmp_path / "responses").glob("*.txt"))) == 2


def test_failure_logged(tmp_path):
    aa = setup_env(tmp_path)
    img = next((aa.ARTWORKS_DIR).rglob("*.jpg"))
    with mock.patch.object(aa.client.chat.completions, "create", return_value=dummy_resp("bad")):
        listing, raw, p_log, r_log, err = aa.generate_ai_listing(
            "prompt", img, "1x1", "RJC-9999"
        )
    assert listing is None
    pf = list((tmp_path / "pf").glob("*.txt"))
    assert pf

```

---
## 📄 utils/ai_services.py

```py
import os
from openai import OpenAI
# import google.generativeai as genai  # Uncomment when you add the Gemini library

# --- LOAD API KEYS ---
# Make sure these are in your .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- INITIALIZE CLIENTS ---
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
# genai.configure(api_key=GEMINI_API_KEY)  # Uncomment for Gemini


def call_openai_api(prompt: str) -> str:
    """Sends a prompt to the OpenAI API and returns the rewritten text."""
    if not OPENAI_API_KEY:
        return "OpenAI API key not configured. Please set it in your .env file."
    global openai_client
    if openai_client is None:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    try:
        response = openai_client.chat.completions.create(
            model=os.getenv("OPENAI_PRIMARY_MODEL", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert copywriter. Rewrite the user's text based on their instruction. "
                        "Be creative and professional. Only return the rewritten text, with no extra commentary."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return f"Error from OpenAI: {e}"


def call_gemini_api(prompt: str) -> str:
    """Sends a prompt to the Gemini API and returns the rewritten text."""
    if not GEMINI_API_KEY:
        return "Gemini API key not configured. Please set it in your .env file."
    # TODO: Implement the actual Gemini API call here
    # model = genai.GenerativeModel('gemini-1.5-pro')
    # response = model.generate_content(prompt)
    # return response.text
    return f"(Gemini response for: '{prompt}')"  # Mock response


def call_ai_to_rewrite(prompt: str, provider: str) -> str:
    """Master function to call the appropriate AI provider."""
    if provider == "openai":
        return call_openai_api(prompt)
    elif provider == "gemini":
        return call_gemini_api(prompt)
    # Add logic for 'random' or 'combined' if desired
    else:
        return call_openai_api(prompt)  # Default to OpenAI

```

---
## 📄 utils/sku_assigner.py

```py
# === [ CapitalArt: SKU Assigner ] ====================================
# File: utils/sku_assigner.py  (or wherever fits your project layout)

import json
from pathlib import Path
import threading

SKU_PREFIX = "RJC-"
SKU_DIGITS = 4  # e.g., 0122 for 122

_LOCK = threading.Lock()  # for thread/process safety

def get_next_sku(tracker_path: Path) -> str:
    """Safely increment and return the next sequential SKU."""
    print("[SKU DEBUG] Using tracker file:", tracker_path)
    with _LOCK:
        # 1. Load or create tracker file
        if tracker_path.exists():
            with open(tracker_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_sku = int(data.get("last_sku", 0))
        else:
            last_sku = 0

        # 2. Increment
        next_sku_num = last_sku + 1
        next_sku_str = f"{SKU_PREFIX}{next_sku_num:0{SKU_DIGITS}d}"

        # 3. Write back to tracker
        data = {"last_sku": next_sku_num}
        with open(tracker_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return next_sku_str

def peek_next_sku(tracker_path: Path) -> str:
    """Return what the next SKU would be without incrementing."""
    print("[SKU DEBUG] Peeking tracker file:", tracker_path)
    if tracker_path.exists():
        with open(tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            last_sku = int(data.get("last_sku", 0))
    else:
        last_sku = 0

    next_sku_num = last_sku + 1
    next_sku_str = f"{SKU_PREFIX}{next_sku_num:0{SKU_DIGITS}d}"
    return next_sku_str


```

---
## 📄 generic_texts/2x3.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

2:3 (Vertical)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This captivating artwork is provided in a classic 2:3 portrait ratio, ideal for emphasizing height and creating a sense of grandeur. Your high-resolution JPEG file boasts 9600 x 14400 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints. 

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 32 x 48 inches (81.3 x 121.9 cm) without compromising quality.

Ideal Uses for the 2:3 Aspect Ratio: The elegant 2:3 portrait ratio is perfect for compositions that benefit from vertical emphasis, such as towering landscapes, architectural marvels, or captivating figure studies. It draws the viewer's eye upward, creating a feeling of spaciousness and depth.

* 10x15" (25x38 cm): Great for narrow wall sections, intimate spaces, or as part of a vertical grouping.
* 16x24" (40x60 cm): A popular choice for classic framing, offering a timeless aesthetic in living rooms or studies.
* 20x30" (50x76 cm): A versatile medium size that brings a refined vertical element to any room.
* 24x36" (60x91 cm): Creates a powerful visual statement in hallways, entryways, or as a focal point in a master bedroom.
* 32x48" (81x122 cm): A grand print that truly commands attention and fills a large wall in open, spacious environments.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.


Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!

```

---
## 📄 generic_texts/4x5.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

4:5 (Vertical)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This exquisite artwork is provided in a harmonious 4:5 portrait ratio, widely popular for its balanced and pleasing proportions. Your high-resolution JPEG file boasts 11520 x 14400 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 38.4 x 48 inches (97.5 x 121.9 cm) without compromising quality.

Ideal Uses for the 4:5 Aspect Ratio: The 4:5 portrait ratio is highly sought after for its aesthetically pleasing balance, often seen in fine art photography and portraiture. It provides ample vertical space while still feeling grounded, making it perfect for a wide range of subjects.

* 10x12.5" (25x32 cm): Excellent for bedside tables, mantels, or small gallery groupings, offering an intimate scale.
* 16x20" (40x50 cm): Incredibly versatile and fits well in almost any room, from living areas to studies, providing a classic proportion.
* 24x30" (60x76 cm): Makes a substantial and elegant statement, perfect for a dining room or foyer, drawing the eye effortlessly.
* 32x40" (81x102 cm): A commanding size that creates a significant visual impact in medium to large rooms.
* 38.4x48" (97.5x122 cm): Designed to be a captivating centerpiece in grand interiors, filling the wall with artistic presence.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!


```

---
## 📄 generic_texts/16x9.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

16:9 (Horizontal)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This dynamic artwork is provided in a cinematic 16:9 landscape ratio, delivering an expansive, widescreen experience. Your high-resolution JPEG file boasts 14400 x 8100 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints. 

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 48 x 27 inches (121.9 x 68.6 cm) without compromising quality.

Ideal Uses for the 16:9 Aspect Ratio: The 16:9 landscape ratio, familiar from film and television screens, is superb for capturing sweeping panoramas, wide-angle views, and immersive action scenes. It draws the viewer into the scene, making it feel grand and enveloping.

* 17.8x10" (45x25 cm): A natural fit for spaces where screens are prominent, like home offices or entertainment areas, or above smaller furniture.
* 24x13.5" (61x34 cm): Provides a contemporary widescreen element suitable for various rooms, offering a subtle yet expansive feel.
* 32x18" (81x45 cm): Works wonderfully above a sofa or console table, creating a modern and immersive focal point.
* 40x22.5" (102x57 cm): A significant widescreen piece that brings a sense of cinematic grandeur to a large wall.
* 48x27" (122x68.6 cm): Transforms a wall into a cinematic vista, perfect for large living rooms, media rooms, or open-plan designs.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.


Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!

```

---
## 📄 generic_texts/A-Series-Verical.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—proud Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour and dots. My journey began on Kaurna Country in Adelaide, and my family lines stretch back to Naracoorte (Boandik Country). Every artwork I create is a blend of ancient wisdom and modern wonder, with deep respect for Country and the powerful stories passed down through generations. My art is my way of giving back—celebrating our land, our history, and sharing a piece of Australian spirit with you, wherever you are in the world.

Dot painting, for me, is more than a technique—it’s a conversation with the past and a bridge to the future. I use both traditional and digital tools to honour old stories and invent new ones, always with a healthy dose of humour and warmth. When you bring my art into your home, you’re not just getting a pretty picture—you’re getting a piece of living culture, carefully crafted with heart and soul.

Did You Know? The Spirit & Story of Aboriginal Dot Painting
Aboriginal dot painting is one of Australia’s most iconic and respected art traditions, rooted in tens of thousands of years of deep connection to land, people, and spirit. While dot motifs have appeared in ancient rock art and ceremonial body painting across the continent, the world-famous “dot painting” style really took off in the early 1970s with the Papunya Tula art movement in the Central Desert.

Pioneering artists such as Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye created a whole new visual language—using dots to map out Dreamtime stories, songlines, and the sacred wisdom of Country. Dots were never just decoration: they protected the most important meanings from outsiders, while sharing the beauty, energy, and movement of the land with everyone.

Each dot can be seen as a footprint, a star, or a ripple in the sand—a symbol of connection between artist, Country, and viewer. Today, Aboriginal artists continue to keep this powerful tradition alive, blending ancient methods with new ideas, materials, and personal stories. No two dot paintings are ever the same; each one is a living story, capturing the resilience, creativity, and ongoing journey of Aboriginal people and places.

A-Series (Vertical)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This elegant artwork is provided in the versatile A-Series vertical ratio, aligning with international standard paper sizes and offering a clean, contemporary aesthetic. Your high-resolution JPEG file boasts 10182 x 14400 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 33.94 x 48 inches (86.2 x 121.9 cm) (based on A1 dimensions, scaled) without compromising quality.

Ideal Uses for the A-Series Vertical Aspect Ratio: The A-Series vertical format is characterized by its consistent proportions across different sizes (e.g., A4, A3, A2), making it perfect for cohesive gallery walls or when you need standard framing options. It's ideal for art that benefits from a clear, structured vertical presentation.

* 10x14.1" (25x36 cm): A versatile size that fits well in smaller vertical spaces, perfect for studies or bedrooms.
* 11.7x16.5" (A3) (29.7x42 cm): Excellent for creating uniform gallery walls, especially when mixed with other A-series prints, a professional look.
* 16.5x23.4" (A2) (42x59.4 cm): A substantial size that adds a refined and structured vertical element to living areas or offices.
* 23.4x33.1" (A1) (59.4x84.1 cm): Makes a significant impression, suitable for larger wall spaces in a contemporary setting.
* 33.94x48" (86.2x122 cm): A truly grand sized piece that delivers exceptional visual presence and simplifies framing for large-scale impact.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!


```

---
## 📄 generic_texts/4x3.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

4:3 (Horizontal)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This compelling artwork is provided in a classic 4:3 landscape ratio, offering a slightly more square-like horizontal composition. Your high-resolution JPEG file boasts 14400 x 10800 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 48 x 36 inches (121.9 x 91.4 cm) without compromising quality.

Ideal Uses for the 4:3 Aspect Ratio: The 4:3 landscape ratio offers a broader, more open feel than traditional landscape formats, making it excellent for showcasing scenes with interesting foregrounds or expansive skies. It provides a comfortable viewing experience, resembling many digital display formats.

* 13.3x10" (34x25 cm): Fits well into smaller spaces like kitchen nooks, hallways, or compact offices.
* 24x18" (60x45 cm): A popular size for placing above sofas, sideboards, or console tables, creating a balanced horizontal line.
* 32x24" (81x60 cm): Fantastic for creating a relaxed yet impactful atmosphere in media rooms or lounges.
* 40x30" (102x76 cm): A substantial piece that brings depth and breadth to larger living areas or commercial spaces.
* 48x36" (122x91 cm): For a truly immersive experience, this print fills a wall with a grand and inviting presence.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!

```

---
## 📄 generic_texts/9x16.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

9:16 (Vertical)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This striking artwork is provided in a contemporary 9:16 portrait ratio, mirroring modern screen dimensions and offering a dramatic vertical emphasis. Your high-resolution JPEG file boasts 8100 x 14400 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 27 x 48 inches (68.6 x 121.9 cm) without compromising quality.

Ideal Uses for the 9:16 Aspect Ratio: The 9:16 portrait ratio, often referred to as "vertical video" or "phone screen" format, is perfect for subjects that demand extreme verticality, such as towering natural formations, dramatic figure studies, or stylized architectural compositions. It creates a modern, immersive viewing experience.

* 10x17.8" (25x45 cm): Perfectly suited for slender wall sections, narrow nooks, or as a unique accent.
* 13.5x24" (34x61 cm): Offers a sleek, modern look in offices or minimalist living areas, drawing the eye upward.
* 18x32" (45x81 cm): Creates a significant vertical presence, ideal for adding height and drama to a room.
* 22.5x40" (57x102 cm): A commanding vertical piece that makes a strong artistic statement in contemporary spaces.
* 27x48" (68.6x122 cm): Creates a powerful, extreme vertical statement, ideal for high-ceiling rooms or as a striking focal point.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!



```

---
## 📄 generic_texts/5x7.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

5:7 (Vertical)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This stunning artwork is provided in a traditional 5:7 portrait ratio, a classic choice for showcasing detail and elegance. Your high-resolution JPEG file boasts 10286 x 14400 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 34.3 x 48 inches (87.1 x 121.9 cm) without compromising quality.

Ideal Uses for the 5:7 Aspect Ratio: The 5:7 portrait ratio is a time-honored choice, often associated with framed photographs and fine art. Its slightly narrower proportion guides the eye directly to the subject, making it excellent for portraits, botanical studies, or any composition that benefits from a focused vertical emphasis.

* 10x14" (25x35 cm): Perfect for adding charm to side tables, mantels, or bookcases, providing a classic, refined touch.
* 15x21" (38x53 cm): Fits beautifully into smaller wall spaces or as part of a curated collection, offering a graceful vertical line.
* 20x28" (50x70 cm): An elegant mid-size option that brings sophistication to studies, hallways, or bedrooms.
* 25x35" (63.5x89 cm): Provides a substantial and elegant statement in dining rooms or studies, enhancing the room's ambiance.
* 34.3x48" (87.1x122 cm): For a truly commanding and refined presence, this large print will elevate the ambiance of any spacious room.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.


Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!

```

---
## 📄 generic_texts/7x5.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

7:5 (Horizontal)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This elegant artwork is provided in a classic 7:5 landscape ratio, offering a slightly more elongated horizontal view. Your high-resolution JPEG file boasts 14400 x 10286 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 48 x 34.3 inches (121.9 x 87.1 cm) without compromising quality.

Ideal Uses for the 7:5 Aspect Ratio: The 7:5 landscape ratio is a timeless and versatile choice, providing a more expansive horizontal canvas than a 4:3, yet more contained than a 16:9. It's ideal for capturing broad scenes while retaining intimacy, making it excellent for landscapes, cityscapes, or group compositions.

* 14x10" (35x25 cm): A great addition to horizontal display areas like shelves or console tables, offering a classic aesthetic.
* 21x15" (53x38 cm): Fits wonderfully above a dining room buffet or a narrower stretch of wall, providing a harmonious balance.
* 28x20" (70x50 cm): Brings a sophisticated touch to living rooms or large hallways, creating a compelling visual.
* 35x25" (89x63.5 cm): A substantial piece that beautifully captures broad scenes and enhances the spaciousness of a room.
* 48x34.3" (122x87.1 cm): Designed to command attention in spacious, open-plan areas with its impressive and immersive view.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!



```

---
## 📄 generic_texts/1x1.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

1:1 (Square)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This stunning artwork is provided in a versatile 1:1 square ratio, perfect for creating symmetrical displays and fitting a wide range of frames. Your high-resolution JPEG file boasts 14400 x 14400 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints. 

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 48 x 48 inches (121.9 x 121.9 cm) without compromising quality.

Ideal Uses for the 1:1 Aspect Ratio: The timeless 1:1 square ratio offers balanced harmony, making it a versatile choice for a variety of spaces. Its inherent symmetry brings a sense of calm and order, perfect for creating visually pleasing displays.

* 10x10" (25x25 cm): Great for small spaces, shelves, or as part of a multi-piece grid.
* 16x16" (40x40 cm): Perfect for modern gallery walls or to complement other artwork.
* 24x24" (60x60 cm): A stylish medium size that suits any room or office, offering a balanced presence.
* 36x36" (90x90 cm): A large statement piece for significant impact in open areas.
* 48x48" (122x122 cm): A huge statement piece for big impact in open areas, truly dominating a wall.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!

```

---
## 📄 generic_texts/3x2.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

3:2 (Horizontal)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This striking artwork is provided in a timeless 3:2 landscape ratio, perfect for panoramic views and expansive scenes. Your high-resolution JPEG file boasts 14400 x 9600 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 48 x 32 inches (121.9 x 81.3 cm) without compromising quality.

Ideal Uses for the 3:2 Aspect Ratio: The classic 3:2 landscape ratio excels at capturing broad vistas, serene horizons, and dynamic action shots. It naturally guides the eye across the image, making it perfect for subjects that benefit from a wider field of view.

* 15x10" (38x25 cm): Excellent for adding a horizontal element to shelves, desks, or mantels in smaller areas.
* 24x16" (60x40 cm): Ideally suited for hanging above sideboards, console tables, or in a den.
* 30x20" (76x50 cm): A versatile medium size that looks great over a sofa or in a dining room, offering a broad view.
* 36x24" (91x60 cm): Provides a grand, immersive experience, perfect for dining rooms or large office spaces.
* 48x32" (122x81 cm): Designed to truly transform the atmosphere of a spacious room with its expansive presence.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!


```

---
## 📄 generic_texts/5x4.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

5:4 (Horizontal)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This beautiful artwork is provided in a classic 5:4 landscape ratio, known for its balanced, almost-square horizontal presentation. Your high-resolution JPEG file boasts 14400 x 11520 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 48 x 38.4 inches (121.9 x 97.5 cm) without compromising quality.

Ideal Uses for the 5:4 Aspect Ratio: The 5:4 landscape ratio offers a slightly more contained horizontal view, providing a sense of stability and focus. It's a fantastic choice for compositions where every element contributes to the overall scene, such as still life, architectural details, or serene landscapes.

* 12.5x10" (32x25 cm): Perfect for adding a touch of art to workspaces, kitchen counters, or compact display areas.
* 20x16" (50x40 cm): Integrates seamlessly into a gallery wall or as a standalone piece in a medium-sized room, offering a pleasant balance.
* 30x24" (76x60 cm): Creates a calm yet impactful presence in living rooms or dining areas, a versatile and popular choice.
* 40x32" (102x81 cm): A significant piece that brings a sense of grounded beauty and expansive detail to your space.
* 48x38.4" (122x97.5 cm): Delivers a broad, captivating view for expansive walls, making a powerful and elegant statement.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!

```

---
## 📄 generic_texts/3x4.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

3:4 (Vertical)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This captivating artwork is provided in a versatile 3:4 portrait ratio, offering a slightly wider vertical composition than the 2:3. Your high-resolution JPEG file boasts 10800 x 14400 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 36 x 48 inches (91.4 x 121.9 cm) without compromising quality.

Ideal Uses for the 3:4 Aspect Ratio: The 3:4 portrait ratio provides a balanced vertical emphasis that feels modern and approachable. It's an excellent choice for art that features strong vertical elements but also benefits from a bit more width, such as still life, portraits, or architectural details.

* 10x13.3" (25x34 cm): Perfect for bedrooms or home offices, offering an intimate feel on a small wall.
* 18x24" (45x60 cm): Integrates beautifully into gallery wall arrangements or can be paired with other artworks.
* 24x32" (60x81 cm): Makes a significant impact in living rooms or entryways, providing a strong vertical anchor.
* 30x40" (76x102 cm): A substantial piece that commands attention in larger rooms without overwhelming the space.
* 36x48" (91x122 cm): For a truly commanding presence, this print will be a focal point in any large room or open-plan area.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!
```

---
## 📄 generic_texts/A-Series-Horizontal.txt

```txt
About the Artist – Robin Custance
G’day, I’m Robin Custance—Aboriginal Aussie artist, part-time Kangaroo whisperer, and lifelong storyteller through colour, line, and imagination. My journey began on Kaurna Country here in Adelaide, and my roots reach back to the Naracoorte region (Boandik Country). 

Every artwork I create—whether it’s dot painting, digital design, or contemporary Aussie landscape—carries a deep respect for Country, community, and the vibrant stories handed down through generations.

No matter the style or subject, my intention as an artist is always to tell stories and share genuine emotion. Whether I’m working with ancient dot techniques, digital brushes, or bold, modern colours, I pour heart and meaning into every piece.

My art is a way to give back and keep culture strong—blending the timeless with the modern, and weaving together my heritage with today’s creative spirit. When you bring my art into your home, you’re welcoming a piece of Australian story and soul, crafted with passion and a fair bit of character.

Did You Know? Aboriginal Art & the Spirit of Dot Painting
Aboriginal art is one of the world’s oldest creative traditions, with roots stretching back tens of thousands of years. From ancient rock art to vibrant canvases, each style and technique tells a story about connection to land, people, and spirit.

Did you know that the famous “dot painting” style only became widely known in the early 1970s, through the ground-breaking Papunya Tula movement in Central Australia? Visionary artists like Kaapa Tjampitjinpa, Clifford Possum Tjapaltjarri, and Emily Kame Kngwarreye developed a new visual language using dots—not just for beauty, but to share and protect sacred Dreamtime stories and songlines.

In these works, each dot might represent a footprint, a star, or a ripple in the sand—a powerful link between artist, Country, and viewer.

Today, Aboriginal artists across Australia continue to adapt, innovate, and honour tradition in every medium—from dot paintings and digital art to sculpture and contemporary works. Every piece is part of a living story: a testament to resilience, creativity, and the unbreakable bond between people and place.

Thank you for supporting authentic Aboriginal and Australian art. Every purchase helps keep these stories and traditions alive!

A-Series (Horizontal)
What You’ll Receive: One high-resolution JPEG file (300 DPI). This striking artwork is provided in the versatile A-Series horizontal ratio, aligning with international standard paper sizes and offering a clean, contemporary aesthetic. Your high-resolution JPEG file boasts 14400 x 10182 pixels (with the long edge being 14400px), guaranteeing exceptional clarity and detail for large-format prints.

Maximum Printable Size (at 300 DPI): You can achieve a magnificent print up to 48 x 33.94 inches (121.9 x 86.2 cm) (based on A1 dimensions, scaled) without compromising quality.

Ideal Uses for the A-Series Horizontal Aspect Ratio: The A-Series horizontal format provides consistent proportions across different sizes, making it excellent for cohesive displays or when standard framing options are preferred. It's ideal for art that benefits from a clear, structured horizontal presentation, such as landscapes, cityscapes, or group compositions.

* 14.1x10" (36x25 cm): Great for smaller wall sections, desks, or as part of a multi-piece horizontal arrangement.
* 16.5x11.7" (A3) (42x29.7 cm): Excellent for creating a visually harmonious display, particularly when arranged with other standard-sized pieces.
* 23.4x16.5" (A2) (59.4x42 cm): A substantial size that brings a refined and structured horizontal element to living areas or studies.
* 33.1x23.4" (A1) (84.1x59.4 cm): Provides a broad and clean aesthetic, suitable for larger wall spaces in modern interiors.
* 48x33.94" (122x86.2 cm): A truly impressive, standard-sized piece that will beautifully fill a large wall space with clarity and impactful design.

Whether you want a cosy piece above your desk or a showstopper for your lounge, you’re sorted. And if you’re dreaming even bigger, just let me know—I’m always happy to help with custom sizes or display ideas.

Your image is available for download instantly and securely via Etsy—no PDFs, no third-party links, just simple and safe digital delivery.

Ready for Professional Printing: JPG file format for ease of use, or request other formats as needed.

Printing Tips:
For the best result, I always recommend using a quality professional print lab or one of the print-on-demand services listed below. This ensures vibrant colours and crisp detail—true to the spirit of the original artwork.
Avoid department store kiosks (like Big W or Harvey Norman), as they often can’t handle high-res art files and might leave you with a disappointing print.

Top 10 Print-On-Demand Services for Wall Art & Art Prints
1. Printful:
Renowned for gallery-quality posters, canvas, and framed prints. With global print hubs, you get fast, reliable shipping and excellent colour reproduction.

2. Printify:
A trusted network connecting you with print partners worldwide, offering affordable wall art options with lots of flexibility for sizing and materials.

3. Gelato:
Loved for local printing in 30+ countries. Their wall art—especially posters and framed prints—is top-notch and delivered fast. Great for supporting local wherever you are.

4. Gooten:
Specialists in home decor and wall art, Gooten offers consistent quality and worldwide shipping. Perfect for turning your digital art into beautiful, lasting pieces.

5. Prodigi:
Go-to for museum-quality fine art prints. Their giclée printing methods produce gallery-standard posters and canvases, capturing every detail and nuance.

6. Fine Art America (Pixels):
Huge range and artist-friendly platform. They handle everything from posters to metal and acrylic prints, with reliable fulfilment and global reach.

7. Displate:
For something different, Displate prints artwork directly onto premium metal panels—giving your art a bold, modern edge. Unique, collectible, and super durable.

8. Redbubble:
A favourite among indie artists. Redbubble offers posters, art prints, canvases, and a worldwide audience, so your art can brighten homes from Adelaide to Alaska.

9. Society6:
Trendy, stylish, and high-quality. Society6 caters to art lovers wanting something fresh, offering a wide range of print formats all made to a high spec.

10. InPrnt:
Respected for its professional artist community and gallery-quality art prints. If you want the best of the best, InPrnt delivers craftsmanship you can trust.

Important Notes:
This is a digital download only—no physical item will be shipped.
Colours may vary depending on your screen and printing method.
Personal use only—commercial use or redistribution is not permitted.
Need a different size or have a special request? Send me a message—I’m always happy to help!

❓ Frequently Asked Questions
Q: Is this a digital product?
A: Yes! You’ll get an instant download after purchase.

Q: Can I get a different size or format?
A: Absolutely—just send me a message before or after purchase.

Q: Is it for commercial use?
A: No, personal use only.

Q: Refunds?
A: Digital downloads are final sale, but I’ll fix any issues ASAP.

Q: Is it really limited edition?
A: 100%—only 25 total, ever.🎨 LET’S CREATE SOMETHING BEAUTIFUL TOGETHER
At the end of the day, my art is a reflection of a lifetime of curiosity, hard work, and relentless passion. Whether you’re a seasoned collector or someone just dipping their toes into the world of digital art, I invite you to explore my work.
Each piece is more than an image - it’s a conversation, a piece of my soul, and a snapshot of a life lived with creativity and heart.

🙌 THANK YOU – FROM MY STUDIO TO YOUR HOME
Thank you for taking the time to explore my collection. I hope my art inspires you, makes you smile, and maybe even encourages you to see the world a little differently.
Here’s to art, to life, and to the beautiful stories we all share. 🎨✨
 
🚀 EXPLORE MY WORK: 
🖼 Browse my full collection: 👉 https://robincustance.etsy.com 📩 Have a question? Need help? Send me a message - I’d love to chat!

💫 WHY YOU’LL LOVE THIS ARTWORK
Ever wished you could bottle up that perfect moment - that golden sunset, that crisp evening breeze, that deep connection to the land? Well, consider this artwork your time machine.
✅ Instant Digital Download – No waiting, no shipping delays. Just click, download, print, and enjoy!
 
✅ Premium-Quality Digital Art – Every detail crisp, every colour vibrant, every brushstroke filled with warmth.
 
✅ Versatile Printing Options – Frame it, stretch it on canvas, print on acrylic - make it yours.
 
✅ Authentic Australian Outback Scene – Inspired by real landscapes, real moments, real connection.
 
✅ Perfect Gift for Nature Lovers & Adventure Seekers – Because nothing says "I get you" like an artwork that stirs the soul.
 
This piece isn’t just wall art - it’s a feeling. A reminder of the vastness, beauty, and magic of the Australian landscape, captured for you to cherish.
 
🛒 HOW TO BUY & PRINT
Ordering is as easy as throwing a snag on the barbie. Here’s how:
1️⃣ Add to Cart – Just a couple of clicks and this beauty is yours.
2️⃣ Checkout Securely – Easy, safe, and hassle-free.
3️⃣ Download Instantly – Etsy will send you a direct link to your high-resolution file.
4️⃣ Print It Your Way – At home, through an online service, or at a professional print shop.
5️⃣ Display & Enjoy – Frame it, gift it, or just sit back and admire your excellent taste in art.
Need help with printing? Just shoot me a message - I’m here to help!

❤️ Thank You & Stay Connected
Thank you for supporting Aboriginal and Australian art—your purchase helps keep cultural stories alive.

Don’t wait—click Add to Basket now to secure one of just 25 copies.

If my art brings a smile to your space, I’d love to see a photo or hear from you in a review.

Browse my full collection:
https://www.etsy.com/au/shop/RobinCustance

Special request or a question? Message me anytime—always happy to help.

From my family to yours, thank you for sharing the spirit and stories of Australia with the world.
Warm regards,
Robin Custance

Add this artwork to your shopping basket and let a little bit of Aussie warmth and Dreaming brighten your day, every day.
Thanks for keeping art and culture alive!

```

---
## 📄 scripts/sellbrite_csv_export.py

```py
"""Generate a Sellbrite-compatible CSV from artwork data.

This script reads either an Etsy CSV export or CapitalArt listing JSON
files and produces a CSV ready for upload to Sellbrite. The Sellbrite
CSV header is taken from a provided template so the column order matches
exactly.

The business rules are enforced:
- Quantity fixed to 25
- Condition set to "New"
- Brand set to "Robin Custance Art"
- Category always "Art & Collectibles > Prints > Digital Prints"
- Weight set to 0 (digital product)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from routes import utils
import config

import pandas as pd


def read_template_header(template_path: Path) -> List[str]:
    """Return the header row from the Sellbrite template CSV."""
    with open(template_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    if rows and rows[0] and rows[0][0].startswith("SELLBRITE PRODUCT CSV"):
        header = rows[2] if len(rows) >= 3 else rows[-1]
    else:
        header = rows[0] if rows else []

    header = [h.strip() for h in header]
    if not header:
        raise ValueError("Template CSV missing header")
    return header


def load_etsy_csv(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield dicts from an Etsy export CSV."""
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        yield row.to_dict()


def load_listing_json(folder: Path) -> Iterable[Dict[str, Any]]:
    """Yield listing data from JSON files within ``folder``."""
    for listing in folder.rglob("*-listing.json"):
        try:
            utils.assign_or_get_sku(listing, config.SKU_TRACKER)
            with open(listing, "r", encoding="utf-8") as f:
                data = json.load(f)
            yield data
        except Exception:
            continue


def ensure_description(text: str) -> str:
    """Return a plain text description of at least 400 words."""
    if not text:
        text = "This digital artwork comes from Australian Aboriginal artist Robin Custance. "
    words = text.split()
    if len(words) < 400:
        pad = (400 - len(words))
        extra = (" Robin shares stories of culture and country through vibrant colours." * 50).split()[:pad]
        words.extend(extra)
    return " ".join(words)


def map_row(data: Dict[str, Any], header: List[str]) -> Dict[str, Any]:
    """Map input fields to Sellbrite fields applying business rules."""
    def first_non_empty(*keys: str):
        """Return first non-empty value from ``data`` for the given keys."""
        for k in keys:
            v = data.get(k)
            if isinstance(v, str):
                if v.strip():
                    return v.strip()
            elif v:
                return v
        return None

    sku = first_non_empty("SKU", "sku") or ""
    name = first_non_empty("Title", "title", "name") or sku
    description = first_non_empty("Description", "description") or ""
    description = ensure_description(description)
    price = first_non_empty("Price", "price") or "0"
    tags_raw = first_non_empty("Tags", "tags") or ""
    if isinstance(tags_raw, list):
        # Join tag list with comma+space for readability
        tags = ", ".join(t.strip() for t in tags_raw if t.strip())
    else:
        # Handle accidental string values
        tags = ", ".join(
            t.strip() for t in str(tags_raw).split(",") if t.strip()
        )

    materials_raw = first_non_empty("Materials", "materials") or ""
    if isinstance(materials_raw, list):
        # Join materials list with comma+space for readability
        materials = ", ".join(m.strip() for m in materials_raw if m.strip())
    else:
        # Handle accidental string values
        materials = ", ".join(
            m.strip() for m in str(materials_raw).split(",") if m.strip()
        )

    locked = data.get("locked")
    locked_flag = "Y" if locked else ""

    dws = (
        data.get("DWS")
        or data.get("dws")
        or data.get("digital_wall_size")
        or ""
    )

    images: List[str] = []
    for i in range(1, 9):
        img = data.get(f"Image{i}") or data.get(f"image_{i}")
        if not img and i == 1:
            img = data.get("Image1") or data.get("image")
        if img:
            images.append(str(img))
    if not images:
        imgs = data.get("images") or []
        if isinstance(imgs, str):
            imgs = [i for i in imgs.splitlines() if i.strip()]
        images = list(imgs)[:8]

    mapped: Dict[str, Any] = {}
    if "sku" in header:
        mapped["sku"] = sku
    if "SKU" in header:  # backward compat
        mapped["SKU"] = sku
    if "parent_sku" in header:
        mapped["parent_sku"] = ""
    if "name" in header or "Name" in header:
        mapped["name" if "name" in header else "Name"] = name
    if "description" in header or "Description" in header:
        mapped["description" if "description" in header else "Description"] = description
    if "price" in header or "Price" in header:
        mapped["price" if "price" in header else "Price"] = price
    if "quantity" in header or "Quantity" in header:
        mapped["quantity" if "quantity" in header else "Quantity"] = 25
    if "condition" in header or "Condition" in header:
        mapped["condition" if "condition" in header else "Condition"] = "New"
    if "brand" in header or "Brand" in header:
        mapped["brand" if "brand" in header else "Brand"] = "Robin Custance Art"
    if "category_name" in header or "Category" in header:
        mapped["category_name" if "category_name" in header else "Category"] = (
            "Art & Collectibles > Prints > Digital Prints"
        )
    if "package_weight" in header or "Weight" in header:
        mapped["package_weight" if "package_weight" in header else "Weight"] = 0

    # Optional fields for tags/materials
    if "Tags" in header or "tags" in header:
        mapped["Tags" if "Tags" in header else "tags"] = tags
    if "Materials" in header or "materials" in header:
        mapped["Materials" if "Materials" in header else "materials"] = materials

    if "Locked" in header:
        mapped["Locked"] = locked_flag
    if "DWS" in header:
        mapped["DWS"] = dws

    for idx in range(12):
        key1 = f"product_image_{idx+1}"
        key2 = f"Image {idx+1}"
        if key1 in header or key2 in header:
            mapped[key1 if key1 in header else key2] = images[idx] if idx < len(images) else ""

    return mapped


def export_to_csv(data: Iterable[Dict[str, Any]], template_header: List[str], output: Path) -> None:
    """Write mapped rows to ``output`` with header from template."""
    rows = list(data)
    errors = utils.validate_all_skus(rows, config.SKU_TRACKER)
    if errors:
        raise ValueError("; ".join(errors))

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=template_header)
        writer.writeheader()
        for item in rows:
            mapped = map_row(item, template_header)
            row = {k: mapped.get(k, "") for k in template_header}
            writer.writerow(row)



def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate Sellbrite CSV")
    parser.add_argument("template", type=Path, help="Sellbrite template CSV")
    parser.add_argument("output", type=Path, help="Output CSV path")
    parser.add_argument("--etsy", type=Path, help="Etsy CSV export")
    parser.add_argument("--json-dir", type=Path, help="Directory of listing JSON files")
    args = parser.parse_args()

    header = read_template_header(args.template)
    rows: List[Dict[str, Any]] = []
    if args.etsy and args.etsy.exists():
        rows.extend(load_etsy_csv(args.etsy))
    if args.json_dir and args.json_dir.exists():
        rows.extend(load_listing_json(args.json_dir))
    if not rows:
        raise SystemExit("No input data provided")

    export_to_csv(rows, header, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()

```

---
## 📄 scripts/analyze_artwork.py

```py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""DreamArtMachine Lite | analyze_artwork.py
===============================================================
Professional, production-ready, fully sectioned and sub-sectioned
Robbie Mode™ script for analyzing artworks with OpenAI.

This revision adds comprehensive logging, robust error handling and
optional feedback injection for AI analysis. All activity is written to
``capitalart/logs/analyze-artwork-YYYY-MM-DD-HHMM.log``.

Output JSON logic, filename conventions and colour detection remain
compatible with the previous version.
"""

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
    ARTWORKS_INPUT_DIR as ARTWORKS_DIR,
    MOCKUPS_INPUT_DIR as MOCKUPS_DIR,
    GENERIC_TEXTS_DIR,
    ONBOARDING_PATH,
    OUTPUT_JSON,
    OUTPUT_PROCESSED_ROOT,
    LOGS_DIR,
    PARSE_FAILURE_DIR,
    OPENAI_PROMPT_LOG_DIR,
    OPENAI_RESPONSE_LOG_DIR,
    TMP_DIR as AI_TEMP_DIR,
    SKU_TRACKER,
)

Image.MAX_IMAGE_PIXELS = None

load_dotenv()
client = OpenAI()


# ======================= [ 1. CONFIGURATION & PATHS ] =======================
PROJECT_ROOT = BASE_DIR

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
START_TS = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d-%H%M")
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


_log_fp = open(LOG_FILE, "a", encoding="utf-8")
sys.stdout = _Tee(sys.stdout, _log_fp)
sys.stderr = _Tee(sys.stderr, _log_fp)


logger.info("=== DreamArtMachine Lite: OpenAI Analyzer Started ===")


# ======================== [ 3. UTILITY FUNCTIONS ] ==========================

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


def read_generic_text(aspect: str) -> str:
    txt_path = GENERIC_TEXTS_DIR / f"{aspect}.txt"
    if txt_path.exists():
        logger.info(f"Loaded generic text for {aspect}")
        return txt_path.read_text(encoding="utf-8")
    logger.warning(f"No generic text found for {aspect}")
    return ""


def read_onboarding_prompt() -> str:
    return Path(ONBOARDING_PATH).read_text(encoding="utf-8")


def _log_to_dir(directory: Path, stem: str, suffix: str, content: str) -> Path:
    """Write content to ``directory`` and return the file path."""
    directory.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = directory / f"{stem}-{ts}{suffix}"
    path.write_text(content, encoding="utf-8")
    return path


def _strip_markdown(text: str) -> str:
    """Remove common markdown fences from a string."""
    if text.strip().startswith("```"):
        text = re.sub(r"^```(?:json)?\n", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```\s*$", "", text.strip())
    return text.strip()


REQUIRED_FIELDS = {
    "seo_filename",
    "title",
    "description",
    "tags",
    "materials",
    "primary_colour",
    "secondary_colour",
    "price",
    "sku",
}


def _fields_complete(data: dict) -> bool:
    """Return True if all required fields are present and non-empty."""
    for key in REQUIRED_FIELDS:
        if key not in data:
            return False
        val = data[key]
        if val is None or (isinstance(val, str) and not val.strip()):
            return False
        if isinstance(val, list) and not val:
            return False
    return True


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\- ]+", "", text)
    text = text.strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()


# Use the central SKU assigner for all SKU operations
from utils.sku_assigner import get_next_sku, peek_next_sku


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


def save_finalised_artwork(original_path: Path, seo_name: str, output_base_dir: Path):
    target_folder = Path(output_base_dir) / seo_name
    target_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created/using folder {target_folder}")

    orig_filename = original_path.name
    seo_main_jpg = target_folder / f"{seo_name}.jpg"
    orig_jpg = target_folder / f"original-{orig_filename}"
    thumb_jpg = target_folder / f"{seo_name}-THUMB.jpg"

    shutil.copy2(original_path, orig_jpg)
    shutil.copy2(original_path, seo_main_jpg)
    logger.info(f"Copied original files for {seo_name}")

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
) -> Path:
    """Return path to optimized JPEG for AI analysis.

    The image is resized so the longest edge is ``max_edge`` pixels if larger.
    It is then saved as JPEG, reducing quality in steps until the file is under
    ``target_bytes`` or ``min_quality`` is reached. This keeps OpenAI vision
    inputs small without obvious artefacts.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
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
    system_prompt: str,
    image_path: Path,
    aspect: str,
    assigned_sku: str,
    feedback: str | None = None,
) -> tuple[dict | None, str, Path, Path, str]:
    """Return parsed listing dict or ``None`` if parsing failed.

    The full prompt and raw responses are logged for every attempt.
    """
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to read image for OpenAI: {e}")
        raise

    user_content = [
        {
            "type": "text",
            "text": (
                f"Artwork filename: {image_path.name}\n"
                f"Aspect ratio: {aspect}\n"
                "Describe and analyze the artwork visually, then generate the listing as per the instructions above."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
        },
    ]

    full_prompt = (
        system_prompt.strip()
        + f"\n\nThe SKU for this artwork is {assigned_sku}. "
        + "NEVER invent a SKU, ALWAYS use the provided assigned_sku for the 'sku' and filename fields."
    )

    messages = [
        {"role": "system", "content": full_prompt},
        {"role": "user", "content": user_content},
    ]
    if feedback:
        messages.append({"role": "user", "content": feedback})

    stem = Path(image_path).stem
    prompt_path = _log_to_dir(
        OPENAI_PROMPT_LOG_DIR,
        stem,
        "-prompt.json",
        json.dumps({"messages": messages}, indent=2),
    )

    logger.info(f"OpenAI API call for {image_path.name} [{aspect}]")
    max_attempts = 3
    last_error = ""
    last_raw = ""
    response_path = Path()
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_PRIMARY_MODEL", "gpt-4.1"),
                messages=messages,
                max_tokens=2100,
                temperature=0.92,
                timeout=60,
            )
            last_raw = response.choices[0].message.content.strip()
            response_path = _log_to_dir(
                OPENAI_RESPONSE_LOG_DIR,
                f"{stem}-attempt{attempt}",
                ".txt",
                last_raw,
            )
            text = _strip_markdown(last_raw)
            try:
                parsed = json.loads(text)
            except Exception as exc:
                last_error = f"JSON parse error: {exc}"
                logger.warning(last_error)
                if attempt < max_attempts:
                    continue
                break

            if not _fields_complete(parsed):
                missing = [k for k in REQUIRED_FIELDS if not parsed.get(k)]
                last_error = f"Missing fields: {', '.join(missing)}"
                logger.warning(last_error)
                if attempt < max_attempts:
                    continue
                break

            logger.info("Parsed JSON response successfully")
            return parsed, last_raw, prompt_path, response_path, ""
        except Exception as e:
            last_error = str(e)
            logger.error(f"OpenAI API error on attempt {attempt}: {e}")
            logger.error(traceback.format_exc())
            if attempt < max_attempts:
                import time

                time.sleep(2)

    PARSE_FAILURE_DIR.mkdir(parents=True, exist_ok=True)
    fail_file = _log_to_dir(PARSE_FAILURE_DIR, stem, ".txt", last_raw or last_error)
    logger.error(f"OpenAI API failed after {max_attempts} attempts: {last_error}")
    return None, last_raw, prompt_path, response_path, last_error

# ======================== [ 6. MAIN ANALYSIS LOGIC ] ========================

def analyze_single(image_path: Path, system_prompt: str, feedback_text: str | None, statuses: list):
    """Analyze and process a single image path."""

    status = {"file": str(image_path), "success": False, "error": ""}
    try:
        if not image_path.is_file():
            raise FileNotFoundError(str(image_path))

        aspect = get_aspect_ratio(image_path)
        mockups = pick_mockups(aspect, MOCKUPS_PER_LISTING)
        generic_text = read_generic_text(aspect)
        fallback_base = image_path.stem
        # Preview the next SKU so the AI can embed it without consuming
        assigned_sku = peek_next_sku(SKU_TRACKER)

        opt_img = make_optimized_image_for_ai(image_path, AI_TEMP_DIR)
        size_bytes = Path(opt_img).stat().st_size
        with Image.open(opt_img) as _im:
            dimensions = f"{_im.width}x{_im.height}"
        log_entry = {
            "file": str(image_path),
            "opt_image": str(opt_img),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1024 / 1024, 2),
            "dimensions": dimensions,
            "time_sent": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        start_ts = _dt.datetime.now(_dt.timezone.utc)
        analysis_entry = {
            "original_file": str(image_path),
            "optimized_file": str(opt_img),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1024 / 1024, 2),
            "dimensions": dimensions,
            "time_sent": start_ts.isoformat(),
        }
        ai_listing, raw_response, p_log, r_log, error_text = generate_ai_listing(
            system_prompt,
            opt_img,
            aspect,
            assigned_sku,
            feedback_text,
        )
        log_entry.update({
            "prompt_log": str(p_log),
            "response_log": str(r_log),
        })
        call_end_ts = _dt.datetime.now(_dt.timezone.utc)
        analysis_entry.update({
            "time_responded": call_end_ts.isoformat(),
            "duration_sec": (call_end_ts - start_ts).total_seconds(),
        })
        if ai_listing is None:
            log_entry.update({"status": "fail", "error": error_text})
            analysis_entry.update({"status": "fail", "api_response": error_text})
            openai_logger.info(json.dumps(log_entry))
            status["error"] = error_text
            return None
        else:
            log_entry.update({"status": "success"})
            analysis_entry.update({"status": "success", "api_response": "ok"})

        seo_name, used_fallback_naming, naming_method = extract_seo_filename(ai_listing, raw_response, fallback_base)
        if used_fallback_naming:
            logger.warning(f"SEO filename derived by {naming_method} for {image_path.name}: {seo_name}")
        else:
            logger.info(f"SEO filename from JSON for {image_path.name}: {seo_name}")
        log_entry.update({
            "used_fallback_naming": used_fallback_naming,
            "naming_method": naming_method,
        })
        analysis_entry.update({
            "used_fallback_naming": used_fallback_naming,
            "naming_method": naming_method,
        })

        main_jpg, orig_jpg, thumb_jpg, folder_path = save_finalised_artwork(image_path, seo_name, OUTPUT_PROCESSED_ROOT)

        primary_colour, secondary_colour = get_dominant_colours(Path(main_jpg), 2)

        end_ts = _dt.datetime.now(_dt.timezone.utc)
        log_entry.update({
            "time_responded": end_ts.isoformat(),
            "duration_sec": (end_ts - start_ts).total_seconds(),
            "seo_filename": f"{seo_name}.jpg",
            "processed_folder": str(folder_path),
        })
        openai_logger.info(json.dumps(log_entry))

        desc = ai_listing.get("description", "") if isinstance(ai_listing, dict) else ""
        if desc:
            desc = re.sub(r"\[Generic block here\]\s*$", "", desc, flags=re.IGNORECASE).rstrip()
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
            # Use the previewed SKU captured earlier
            existing_sku = assigned_sku
            logger.info(
                f"Previewing SKU {existing_sku} for {seo_name} (not yet assigned)"
            )

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
        queue_file = OUTPUT_PROCESSED_ROOT / "pending_mockups.json"
        add_to_pending_mockups_queue(main_jpg, str(queue_file))

        status["success"] = True
        logger.info(f"Completed analysis for {image_path.name}")
        return artwork_entry

    except Exception as e:  # noqa: BLE001
        status["error"] = str(e)
        logger.error(f"Failed processing {image_path}: {e}")
        logger.error(traceback.format_exc())
        return None
    finally:
        with contextlib.suppress(Exception):
            if 'opt_img' in locals() and Path(opt_img).exists():
                Path(opt_img).unlink()
        statuses.append(status)


# ============================ [ 7. MAIN ENTRY ] ============================

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze artwork(s) with OpenAI")
    parser.add_argument("image", nargs="?", help="Single image path to process")
    parser.add_argument("--feedback", help="Optional feedback text file")
    return parser.parse_args()


def main() -> None:
    print("\n===== DreamArtMachine Lite: OpenAI Analyzer =====\n")
    shutil.rmtree(AI_TEMP_DIR, ignore_errors=True)
    AI_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        system_prompt = read_onboarding_prompt()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Could not read onboarding prompt: {e}")
        logger.error(traceback.format_exc())
        print(f"Error: Could not read onboarding prompt. See log at {LOG_FILE}")
        sys.exit(1)

    args = parse_args()
    feedback_text = None
    if args.feedback:
        try:
            feedback_text = Path(args.feedback).read_text(encoding="utf-8")
            logger.info(f"Loaded feedback from {args.feedback}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to read feedback file {args.feedback}: {e}")
            logger.error(traceback.format_exc())

    single_path = Path(args.image) if args.image else None

    results = []
    statuses: list = []

    if single_path:
        logger.info(f"Single-image mode: {single_path}")
        entry = analyze_single(single_path, system_prompt, feedback_text, statuses)
        if entry:
            results.append(entry)
    else:
        all_images = [f for f in ARTWORKS_DIR.rglob("*.jpg") if f.is_file()]
        logger.info(f"Batch mode: {len(all_images)} images found")
        for idx, img_path in enumerate(sorted(all_images), 1):
            print(f"[{idx}/{len(all_images)}] {img_path.relative_to(ARTWORKS_DIR)}")
            entry = analyze_single(img_path, system_prompt, feedback_text, statuses)
            if entry:
                results.append(entry)

    if results:
        OUTPUT_JSON.parent.mkdir(exist_ok=True)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as out_f:
            json.dump(results, out_f, indent=2, ensure_ascii=False)
        logger.info(f"Wrote master JSON to {OUTPUT_JSON}")

    success_count = len([s for s in statuses if s["success"]])
    fail_count = len(statuses) - success_count
    logger.info(f"Analysis complete. Success: {success_count}, Failures: {fail_count}")

    print(f"\nListings processed! See logs at: {LOG_FILE}")
    if fail_count:
        print(f"{fail_count} file(s) failed. Check the log for details.")


if __name__ == "__main__":
    main()


```

---
## 📄 scripts/generate_composites.py

```py
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

from config import (
    ARTWORKS_PROCESSED_DIR as ARTWORKS_ROOT,
    COORDS_DIR as COORDS_ROOT,
    MOCKUPS_INPUT_DIR as MOCKUPS_ROOT,
)

Image.MAX_IMAGE_PIXELS = None
DEBUG_MODE = False

# ======================= [ 1. CONFIG & PATHS ] =======================
POSSIBLE_ASPECT_RATIOS = [
    "1x1", "2x3", "3x2", "3x4", "4x3", "4x5", "5x4", "5x7", "7x5",
    "9x16", "16x9", "A-Series-Horizontal", "A-Series-Vertical"
]

QUEUE_FILE = ARTWORKS_ROOT / "pending_mockups.json"

# ======================= [ 2. UTILITIES ] =========================

def resize_image_for_long_edge(image: Image.Image, target_long_edge=2000) -> Image.Image:
    width, height = image.size
    if width > height:
        new_width = target_long_edge
        new_height = int(height * (target_long_edge / width))
    else:
        new_height = target_long_edge
        new_width = int(width * (target_long_edge / height))
    return image.resize((new_width, new_height), Image.LANCZOS)

def draw_debug_overlay(img: Image.Image, points: list) -> Image.Image:
    draw = ImageDraw.Draw(img)
    for x, y in points:
        draw.ellipse([x - 6, y - 6, x + 6, y + 6], fill='red', outline='white')
    return img

def apply_perspective_transform(art_img, mockup_img, dst_coords):
    w, h = art_img.size
    src_points = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst_points = np.float32(dst_coords)
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    art_np = np.array(art_img)
    warped = cv2.warpPerspective(art_np, matrix, (mockup_img.width, mockup_img.height))
    mask = np.any(warped > 0, axis=-1).astype(np.uint8) * 255
    mask = Image.fromarray(mask).convert("L")
    composite = Image.composite(Image.fromarray(warped), mockup_img, mask)
    if DEBUG_MODE:
        composite = draw_debug_overlay(composite, dst_coords)
    return composite

def clean_base_name(filename):
    name = os.path.splitext(os.path.basename(filename))[0]
    name = name.replace(" ", "-").replace("_", "-").replace("(", "").replace(")", "")
    name = "-".join(filter(None, name.split('-')))
    return name

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
    print("\n===== CapitalArt Lite: Composite Generator (Queue Mode) =====\n")

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
    for img_path in queue[:]:  # Copy list, in case we mutate queue
        img_path = Path(img_path)
        if not img_path.exists():
            print(f"❌ File not found (skipped): {img_path}")
            remove_from_queue(str(img_path), QUEUE_FILE)
            continue

        # Detect aspect ratio from folder or from JSON listing if available
        folder = img_path.parent
        seo_name = clean_base_name(img_path.stem)
        aspect = None
        json_listing = next(folder.glob(f"{seo_name}-listing.json"), None)
        if json_listing:
            with open(json_listing, "r", encoding="utf-8") as jf:
                entry = json.load(jf)
                aspect = entry.get("aspect_ratio")
        if not aspect:
            # Try to extract from grandparent dir (may be folder name if deeply nested)
            aspect = folder.parent.name
            print(f"  [WARNING] Could not read aspect from JSON, using folder: {aspect}")

        print(f"\n[{processed_count+1}/{len(queue)}] Processing: {img_path.name} [{aspect}]")

        # ----- Find categorised mockups for aspect -----
        mockups_cat_dir = MOCKUPS_ROOT / f"{aspect}-categorised"
        coords_dir = COORDS_ROOT / aspect
        if not mockups_cat_dir.exists() or not coords_dir.exists():
            print(f"⚠️ Missing mockups or coordinates for aspect: {aspect}")
            remove_from_queue(str(img_path), QUEUE_FILE)
            continue

        # ----- Load artwork image (resize for composites) -----
        art_img = Image.open(img_path).convert("RGBA")
        art_img_for_composite = resize_image_for_long_edge(art_img, target_long_edge=2000)
        mockup_seq = 1
        mockup_entries = []

        # ----- For each category: one random PNG mockup -----
        categories = sorted([
            d for d in os.listdir(mockups_cat_dir)
            if (mockups_cat_dir / d).is_dir()
        ])
        for category in categories:
            category_dir = mockups_cat_dir / category
            png_mockups = [f for f in os.listdir(category_dir) if f.lower().endswith(".png")]
            if not png_mockups:
                continue
            selected_mockup = random.choice(png_mockups)
            mockup_file = category_dir / selected_mockup
            coord_path = coords_dir / f"{os.path.splitext(selected_mockup)[0]}.json"
            if not coord_path.exists():
                print(f"⚠️ Missing coordinates for {selected_mockup} ({aspect}/{category})")
                continue

            with open(coord_path, "r", encoding="utf-8") as f:
                coords_data = json.load(f)
            if "corners" not in coords_data:
                print(f"⚠️ Invalid or missing 'corners' in {coord_path}")
                continue

            raw_corners = coords_data["corners"]
            dst_coords = [
                [raw_corners[0]["x"], raw_corners[0]["y"]],
                [raw_corners[1]["x"], raw_corners[1]["y"]],
                [raw_corners[3]["x"], raw_corners[3]["y"]],
                [raw_corners[2]["x"], raw_corners[2]["y"]]
            ]

            mockup_img = Image.open(mockup_file).convert("RGBA")
            composite = apply_perspective_transform(art_img_for_composite, mockup_img, dst_coords)

            # ---- [Naming and Saving] ----
            output_filename = f"{seo_name}-{Path(selected_mockup).stem}.jpg"
            output_path = folder / output_filename
            composite.convert("RGB").save(output_path, "JPEG", quality=85)
            mockup_entries.append(
                {
                    "category": category,
                    "source": f"{category}/{selected_mockup}",
                    "composite": output_filename,
                }
            )
            print(f"   - Mockup {mockup_seq}: {output_filename} ({category})")
            mockup_seq += 1

        # ---- Update listing JSON with new structure ----
        listing_file = folder / f"{seo_name}-listing.json"
        try:
            with open(listing_file, "r", encoding="utf-8") as lf:
                listing_data = json.load(lf)
        except Exception:
            listing_data = {}
        listing_data["mockups"] = mockup_entries
        with open(listing_file, "w", encoding="utf-8") as lf:
            json.dump(listing_data, lf, indent=2, ensure_ascii=False)

        print(f"🎯 Finished all mockups for {img_path.name}.")
        processed_count += 1

        # ----- Remove this artwork from queue after processing -----
        remove_from_queue(str(img_path), QUEUE_FILE)

    print(f"\n✅ Done. {processed_count} artwork(s) processed and removed from queue.\n")

if __name__ == "__main__":
    main()

```

---
## 📄 scripts/dev_cycle.sh

```sh
#!/bin/bash

# === [ CapitalArt: Dev Cycle Script – Robust Logging ] ===
# Automates: git pull, applies patches, installs, lints, tests, logs everything.
# If all pass, launches Flask app. Logs are saved in dev-logs/dev_cycle-YYYYMMDD-HHMMSS.log.

set -euo pipefail  # Exit on error, error on unset var, propagate failures in pipes

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATCH_DIR="$PROJECT_ROOT/patches"
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON="$VENV_DIR/bin/python"
FLASK_APP="app.py"
PORT=5050
LOGS_DIR="$PROJECT_ROOT/dev-logs"
NOW="$(date +'%Y%m%d-%H%M%S')"
LOG_FILE="$LOGS_DIR/dev_cycle-$NOW.log"

mkdir -p "$LOGS_DIR"
cd "$PROJECT_ROOT"

# --- Helper for logging and error reporting ---
log()  { echo "$@" | tee -a "$LOG_FILE"; }
err()  { echo "[ERROR] $@" | tee -a "$LOG_FILE" >&2; }
run()  { log ">>> $@"; "$@" 2>&1 | tee -a "$LOG_FILE"; }

# --- Error trap for anything that fails ---
trap 'err "Dev cycle failed at step: $BASH_COMMAND (exit code: $?)"; log "See full log: $LOG_FILE"; exit 1' ERR

log "=== [Dev Cycle] $(date) ==="
log "Running in $PROJECT_ROOT"
log "Saving logs to $LOG_FILE"
log "Python: $PYTHON"
log "-----------------------------------------"

log "1. GIT: Checkout and pull main branch"
run git checkout main
run git pull origin main

log "2. PATCH: Apply all .patch files in patches/"
if [ -d "$PATCH_DIR" ]; then
  for patch in "$PATCH_DIR"/*.patch; do
    [ -e "$patch" ] || continue
    log "   > Applying $patch ..."
    if git apply --3way "$patch"; then
      log "   > Applied $patch OK."
    else
      err "   > Failed to apply $patch! See above for details."
      exit 2
    fi
  done
else
  log "   > No patches directory found, skipping."
fi

log "3. PYTHON: Activate virtualenv, install dependencies"
source "$VENV_DIR/bin/activate"
run pip install -r requirements.txt

log "4. LINT: Black and Ruff (format, lint)"
run black . --check --diff
run ruff .

log "5. TEST: Pytest with coverage"
run pytest --maxfail=3 --disable-warnings --cov=.

log "6. STATUS: Git commit summary and coverage"
run git log -n 10 --oneline --graph
run coverage report || true

log "-----------------------------------------"
log "All checks PASSED! Ready to launch CapitalArt Flask app."
log "Starting Flask at http://localhost:$PORT/ (Ctrl+C to stop)"
log "-----------------------------------------"

# If all passes, launch Flask app (will show in console, also logs)
run $PYTHON $FLASK_APP

log "=== [Dev Cycle] Finished cleanly at $(date) ==="
log "See logs at: $LOG_FILE"

# --- End script (no need for explicit exit 0) ---

```

---
## 📄 templates/debug_status.html

```html
{% extends 'main.html' %}
{% block title %}System Status{% endblock %}
{% block content %}
<h1>Debug: System Status</h1>
<ul>
  <li>OpenAI Key Configured: {{ info.openai_key }}</li>
  <li>Processed Folder Exists: {{ info.processed_dir }}</li>
  <li>Finalised Folder Exists: {{ info.finalised_dir }}</li>
  <li>Parse Failures: {{ info.parse_failures|length }}</li>
</ul>
{% if info.parse_failures %}
<h2>Failed Parses</h2>
<ul>
  {% for f in info.parse_failures %}
  <li>{{ f }} - <a href="{{ url_for('admin.parse_ai', file=f) }}">retry parse</a></li>
  {% endfor %}
</ul>
{% endif %}
{% endblock %}

```

---
## 📄 templates/index.html

```html
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}CapitalArt Home{% endblock %}
{% block content %}

<!-- ========== [IN.1] Home Hero Section ========== -->
<div class="home-hero">
  <h1>🎨 Welcome to CapitalArt Listing Machine</h1>
  <p class="home-intro">
    G’day! Start in the Artwork Gallery, analyze new pieces, review your AI-generated listings and mockups, and prep everything for marketplace export—all streamlined for you.
  </p>
</div>

<!-- ========== [IN.2] Home Quick Actions ========== -->
<div class="workflow-grid">
  <a href="{{ url_for('artwork.upload_artwork') }}" class="step-btn">1️⃣ Upload<br>to Art Gallery</a>
  <a href="{{ url_for('artwork.artworks') }}" class="step-btn">2️⃣ Art Gallery<br>Select to Analyze</a>
  {% if latest_artwork %}
    <a href="{{ url_for('artwork.edit_listing', aspect=latest_artwork.aspect, filename=latest_artwork.filename) }}" class="step-btn">3️⃣ Edit Review<br>and Finalise Artwork</a>
  {% else %}
    <span class="step-btn disabled">3️⃣ Edit Review<br>and Finalise Artwork</span>
  {% endif %}
  <a href="{{ url_for('artwork.finalised_gallery') }}" class="step-btn">4️⃣ Finalised Gallery<br>(Select to List)</a>
  <span class="step-btn disabled">5️⃣ List Artwork<br>(Export to Sellbrite)</span>
</div>

<!-- ========== [IN.3] How It Works Section ========== -->
<section class="how-it-works">
  <h2>How It Works</h2>
  <ol>
    <li><b>Upload:</b> Chuck your artwork into the gallery (easy drag & drop).</li>
    <li><b>Analyze:</b> Let the AI do its magic—SEO, titles, pro description, the lot.</li>
    <li><b>Edit & Finalise:</b> Quick review and tweak, fix anything you like.</li>
    <li><b>Mockups:</b> Instantly see your art in bedrooms, offices, nurseries—looks a million bucks.</li>
    <li><b>Final Gallery:</b> See all your finished work, ready for showtime.</li>
    <li><b>Export:</b> Coming soon! Blast your art onto Sellbrite and more with one click.</li>
  </ol>
</section>
{% endblock %}

```

---
## 📄 templates/mockup_selector.html

```html
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}Select Mockups | CapitalArt{% endblock %}
{% block content %}
<h1>🖼️ Select Your Mockup Lineup</h1>
<div class="grid">
  {% for slot, options in zipped %}
  <div class="item">
    {% if slot.image %}
      <img src="{{ url_for('artwork.mockup_img', category=slot.category, filename=slot.image) }}" alt="{{ slot.category }}" />
    {% else %}
      <p>No images for {{ slot.category }}</p>
    {% endif %}
    <strong>{{ slot.category }}</strong>
    <form method="post" action="{{ url_for('artwork.regenerate') }}">
      <input type="hidden" name="slot" value="{{ loop.index0 }}" />
      <button type="submit">🔄 Regenerate</button>
    </form>
    <form method="post" action="{{ url_for('artwork.swap') }}">
      <input type="hidden" name="slot" value="{{ loop.index0 }}" />
      <select name="new_category">
        <!-- DEBUG: Options for slot {{ loop.index0 }}: {{ options|join(", ") }} -->
        {% for c in options %}
        <option value="{{ c }}" {% if c == slot.category %}selected{% endif %}>{{ c }}</option>
        {% endfor %}
      </select>
      <button type="submit">🔁 Swap</button>
    </form>
  </div>
  {% endfor %}
</div>
<form method="post" action="{{ url_for('artwork.proceed') }}">
  <button class="composite-btn" type="submit">✅ Generate Composites</button>
</form>
<div style="text-align:center;margin-top:1em;">
  {% if session.latest_seo_folder %}
    <a href="{{ url_for('artwork.composites_specific', seo_folder=session.latest_seo_folder) }}" class="composite-btn" style="background:#666;">👁️ Preview Composites</a>
  {% else %}
    <a href="{{ url_for('artwork.composites_preview') }}" class="composite-btn" style="background:#666;">👁️ Preview Composites</a>
  {% endif %}
</div>
{% endblock %}

```

---
## 📄 templates/review.html

```html
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}Review | CapitalArt{% endblock %}
{% block content %}
<h1>Review &amp; Approve Listing</h1>
<section class="review-artwork">
  <h2>{{ artwork.title }}</h2>
  <div class="artwork-images">
    <img src="{{ url_for('static', filename='outputs/processed/' ~ artwork.seo_name ~ '/' ~ artwork.main_image) }}"
         alt="Main artwork" class="main-art-img" style="max-width:360px;">
    <img src="{{ url_for('static', filename='outputs/processed/' ~ artwork.seo_name ~ '/' ~ artwork.thumb) }}"
         alt="Thumbnail" class="thumb-img" style="max-width:120px;">
  </div>
  <h3>Description</h3>
  <div class="art-description" style="max-width:431px;">
    <pre style="white-space: pre-wrap; font-family:inherit;">{{ artwork.description }}</pre>
  </div>
  <h3>Mockups</h3>
  <div class="grid">
    {% for slot in slots %}
    <div class="item">
      <img src="{{ url_for('artwork.mockup_img', category=slot.category, filename=slot.image) }}" alt="{{ slot.category }}">
      <strong>{{ slot.category }}</strong>
    </div>
    {% endfor %}
  </div>
</section>
<form method="get" action="{{ url_for('artwork.select') }}">
  <input type="hidden" name="reset" value="1">
  <button class="composite-btn" type="submit">Start Over</button>
</form>
<div style="text-align:center;margin-top:1.5em;">
  <a href="{{ url_for('artwork.composites_specific', seo_folder=artwork.seo_name) }}" class="composite-btn" style="background:#666;">Preview Composites</a>
</div>
{% endblock %}

```

---
## 📄 templates/artworks.html

```html
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}Artwork Gallery | CapitalArt{% endblock %}
{% block content %}

<div class="gallery-section">

  {% if ready_artworks %}
    <h2 class="mb-3">Ready to Analyze</h2>
    <div class="artwork-grid">
      {% for art in ready_artworks %}
      <div class="gallery-card">
        <div class="card-thumb">
          <img class="card-img-top"
               src="{{ url_for('artwork.temp_image', filename=art.thumb) }}"
               alt="{{ art.title }}">
        </div>
        <div class="card-details">
          <div class="card-title">{{ art.title }}</div>
          <form method="post" action="{{ url_for('artwork.analyze_upload', base=art.base) }}" class="analyze-form">
            <button type="submit" class="btn btn-primary">Analyze</button>
          </form>
        </div>
      </div>
      {% endfor %}
    </div>
  {% endif %}

  {% if processed_artworks %}
    <h2 class="mb-3 mt-5">Processed Artworks</h2>
    <div class="artwork-grid">
      {% for art in processed_artworks %}
      <div class="gallery-card">
        <div class="card-thumb">
          <img class="card-img-top"
               src="{{ url_for('artwork.processed_image', seo_folder=art.seo_folder, filename=art.thumb) }}"
               alt="{{ art.title }}">
        </div>
        <div class="card-details">
          <div class="card-title">{{ art.title }}</div>
          <a href="{{ url_for('artwork.edit_listing', aspect=art.aspect, filename=art.filename) }}"
             class="btn btn-secondary">Review</a>
        </div>
      </div>
      {% endfor %}
    </div>
  {% endif %}

  {% if finalised_artworks %}
    <h2 class="mb-3 mt-5">Finalised Artworks</h2>
    <div class="artwork-grid">
      {% for art in finalised_artworks %}
      <div class="gallery-card">
        <div class="card-thumb">
          <img class="card-img-top"
               src="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.thumb) }}"
               alt="{{ art.title }}">
        </div>
        <div class="card-details">
          <div class="card-title">{{ art.title }}</div>
          <a href="{{ url_for('artwork.edit_listing', aspect=art.aspect, filename=art.filename) }}" class="btn btn-secondary">Edit</a>
        </div>
      </div>
      {% endfor %}
    </div>
  {% endif %}
  {% if not ready_artworks and not processed_artworks and not finalised_artworks %}
    <p class="empty-msg">No artworks found. Please upload artwork to get started!</p>
  {% endif %}

</div>

{% endblock %}

```

---
## 📄 templates/test_description.html

```html
{% extends "main.html" %}
{% block title %}Test Combined Description{% endblock %}
{% block content %}
<h1>Test Combined Description</h1>
<div class="desc-text" style="white-space: pre-wrap;border:1px solid #ccc;padding:10px;">
  {{ combined_description }}
</div>
{% endblock %}

```

---
## 📄 templates/debug_parse_ai.html

```html
{% extends 'main.html' %}
{% block title %}Parse AI Output{% endblock %}
{% block content %}
<h1>Debug: Parse AI Output</h1>
<form method="post">
  <textarea name="raw" rows="15" cols="80">{{ raw }}</textarea><br>
  <button type="submit">Parse</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if parsed %}
<pre>{{ parsed | tojson(indent=2) }}</pre>
{% endif %}
{% endblock %}

```

---
## 📄 templates/dws_editor.html

```html
{% extends "main.html" %}
{% block title %}Generic Description Writing System (GDWS) Editor{% endblock %}

{% block content %}
<!-- SortableJS for Drag-and-Drop functionality -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.0/Sortable.min.js"></script>

<!-- Custom Styles for the GDWS Editor Page, inheriting from your style.css -->
<style>
    .dws-container {
        display: flex;
        gap: 2em;
        align-items: flex-start;
        max-width: 1400px;
        margin: 0 auto;
    }
    .dws-sidebar {
        width: 300px;
        flex-shrink: 0;
        background-color: var(--card-bg);
        padding: 1.5em;
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        border: 1px solid var(--border);
    }
    .dws-main-content {
        flex-grow: 1;
    }
    .dws-sidebar h1, .dws-sidebar h2 {
        text-align: left;
        margin-bottom: 0.5em;
    }
    .dws-sidebar h1 {
        font-size: 1.5em;
        margin-bottom: 1em;
    }
    .dws-sidebar h2 {
        font-size: 1.2em;
        margin-top: 1.5em;
        border-bottom: 1px solid var(--border);
        padding-bottom: 0.3em;
    }
    .dws-sidebar .btn-black {
        width: 100%;
        margin-bottom: 0.75em;
    }
    .dws-rules-box {
        background-color: #f7f7f7;
        padding: 1em;
        margin-top: 1em;
        border-radius: var(--radius);
    }
    .dws-rules-box label {
        font-weight: 500;
        font-size: 0.9em;
    }
    .dws-rules-box input, .dws-rules-box select {
        width: 100%;
        box-sizing: border-box;
        margin-top: 0.2em;
        margin-bottom: 0.8em;
    }

    .paragraph-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        padding: 1.5em;
        margin-bottom: 1em;
        box-shadow: var(--shadow);
        transition: box-shadow 0.2s ease-in-out;
        border-radius: var(--radius);
    }
    .paragraph-card:hover {
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    .paragraph-card-header {
        display: flex;
        align-items: center;
        margin-bottom: 1em;
        gap: 0.8em;
    }
    .drag-handle {
        cursor: grab;
        font-size: 1.5em;
        color: #999;
    }
    .pinned-placeholder {
        width: 1.5em;
    }
    .paragraph-card-header input[type="text"] {
        font-size: 1.2em;
        font-weight: bold;
        border: none;
        background: transparent;
        padding: 0.2em;
        width: 100%;
    }
    .paragraph-card-header input[type="text"]:focus {
        background: #f0f0f0;
    }
    .paragraph-card textarea {
        width: 100%;
        box-sizing: border-box;
        height: 150px;
        resize: vertical;
        padding: 0.8em;
        font-size: 1em;
        line-height: 1.6;
    }
    .ai-instruction-input {
        width: 100%;
        box-sizing: border-box;
        margin-top: 0.8em;
        padding: 0.5em;
        font-size: 0.9em;
        border: 1px solid #ddd;
    }
    .paragraph-card-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 1em;
        font-size: 0.9em;
    }
    .word-count-display.error {
        color: #c00;
        font-weight: bold;
    }
    .count-separator {
        margin: 0 0.5em;
    }
    .paragraph-card-actions .btn-card-action {
        margin-left: 0.5em;
        font-size: 0.9em;
        padding: 0.4em 0.8em;
        background: #f0f0f0;
        border: none;
        color: #333;
        cursor: pointer;
        transition: background-color 0.2s;
        font-weight: 500;
        border-radius: var(--radius);
        position: relative;
    }
    .paragraph-card-actions .btn-card-action:hover {
        background: #dcdcdc;
    }
    .paragraph-card-actions .delete-btn:hover {
        background: #a60000;
        color: #fff;
    }

    .sortable-ghost {
        opacity: 0.4;
        background: #eef;
        border: 1px dashed var(--accent);
    }
    .sortable-chosen {
        cursor: grabbing;
    }
    .modal-overlay {
        display: none;
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.6);
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }
    .modal-box {
        background: white;
        padding: 2em;
        max-width: 500px;
        width: 90%;
        border: 1px solid var(--border);
        box-shadow: var(--shadow);
        border-radius: var(--radius);
    }
    .modal-box .btn {
        background: #f0f0f0;
        border: 1px solid #ccc;
        color: #333;
    }
    #confirm-delete-btn:hover {
        background-color: #a60000 !important;
    }
    .spinner-overlay {
        display: none;
        position: absolute;
        inset: 0;
        background: rgba(255, 255, 255, 0.8);
        align-items: center;
        justify-content: center;
    }
    .spinner {
        border: 3px solid #f3f3f3;
        border-top: 3px solid #3498db;
        border-radius: 50%;
        width: 24px;
        height: 24px;
        animation: spin 1s linear infinite;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .version-status {
        font-size: 0.85em;
        margin-bottom: 0.5em;
    }
    .version-status .status-match {
        color: #28a745;
        font-weight: bold;
    }
    .version-status .status-mismatch {
        color: #dc3545;
        font-weight: bold;
    }
</style>


<div class="dws-container">
    <!-- Sidebar for Master Controls -->
    <aside class="dws-sidebar">
        <h1>GDWS Controls</h1>
        
        <div class="dws-rules-box">
            <label for="aspect-ratio-selector">Select Aspect Ratio Template</label>
            <select id="aspect-ratio-selector" name="aspect-ratio-selector">
                <option value="4x5">4x5</option>
                <option value="16x9">16x9</option>
                <option value="1x1">1x1</option>
                <option value="A-Series-Verical">A-Series-Verical</option>
            </select>
        </div>

        <!-- Master Actions -->
        <div>
            <h2>Master Actions</h2>
            <button id="save-all-btn" class="btn-black">💾 Save All Changes</button>
            <button id="add-paragraph-btn" class="btn-black">➕ Add New Paragraph</button>
            <button id="regenerate-all-btn" class="btn-black">✨ Regenerate All</button>
            <button id="shuffle-btn" class="btn-black">🔀 Shuffle Paragraphs</button>
        </div>

        <!-- AI & Content Rules -->
        <div class="dws-rules-box">
            <h2>AI & Content Rules</h2>
            <div>
                <label for="ai-provider">AI Provider</label>
                <select id="ai-provider" name="ai-provider">
                    <option value="openai">OpenAI</option>
                    <option value="gemini">Gemini</option>
                    <option value="random">Random</option>
                    <option value="combined">Combined</option>
                </select>
            </div>
            <div>
                <label for="min-words">Min Words per Block</label>
                <input type="number" id="min-words" value="20">
            </div>
            <div>
                <label for="max-words">Max Words per Block</label>
                <input type="number" id="max-words" value="150">
            </div>
            <button id="save-rules-btn" class="btn-black">Save Rules</button>
        </div>

        <!-- System Version Check -->
        <div class="dws-rules-box">
            <h2>System Versions</h2>
            <div id="version-checker">
                <p>Loading version status...</p>
            </div>
            <div>
                <label for="new-version-key">Update Version For:</label>
                <select id="new-version-key">
                    <option value="app_version">App Version</option>
                    <option value="config_version">Config.py Version</option>
                    <option value="env_version">.env Version</option>
                    <option value="openai_primary_model">OpenAI Primary Model</option>
                    <option value="openai_fallback_model">OpenAI Fallback Model</option>
                    <option value="gemini_primary_model">Gemini Primary Model</option>
                </select>
                <label for="new-version-value">New Version #:</label>
                <input type="text" id="new-version-value" placeholder="e.g., 1.2.1 or gpt-4o">
                <button id="save-new-version-btn" class="btn-black">Save New Version</button>
            </div>
        </div>
        <p style="text-align:center; font-size:0.8em; color:#999; margin-top:2em;">CapitalArt GDWS v1.5</p>
    </aside>

    <!-- Main Content Area for Paragraph Cards -->
    <main class="dws-main-content">
        <div id="header-blocks"></div>
        <div id="draggable-blocks"></div>
        <div id="footer-blocks"></div>
    </main>
</div>

<!-- Delete Confirmation Modal -->
<div id="delete-modal" class="modal-overlay">
    <div class="modal-box">
        <h3>Confirm Deletion</h3>
        <p>Are you sure you want to delete this paragraph block? This cannot be undone.</p>
        <div style="margin-top: 1.5em; text-align: right;">
            <button id="cancel-delete-btn" class="btn">Cancel</button>
            <button id="confirm-delete-btn" class="btn-black">Delete</button>
        </div>
    </div>
</div>

<!-- JavaScript for all interactivity -->
<script>
    document.addEventListener('DOMContentLoaded', () => {
        let currentBlockToDelete = null;
        let currentCardToDelete = null;
        let minWords = 20;
        let maxWords = 150;

        const headerContainer = document.getElementById('header-blocks');
        const draggableContainer = document.getElementById('draggable-blocks');
        const footerContainer = document.getElementById('footer-blocks');
        const deleteModal = document.getElementById('delete-modal');
        const aspectRatioSelector = document.getElementById('aspect-ratio-selector');
        const slugify = (text) => text.toString().toLowerCase().replace(/[^\w\s-]/g, '').trim().replace(/[-\s]+/g, '_');

        const renderBlocks = (blocks) => {
            headerContainer.innerHTML = '';
            draggableContainer.innerHTML = '';
            footerContainer.innerHTML = '';

            blocks.forEach(block => {
                const card = document.createElement('div');
                card.className = 'paragraph-card';
                card.dataset.id = block.id;
                card.dataset.isNew = block.isNew ? 'true' : 'false';

                const content = block.content || '';
                const words = content.split(/\s+/).filter(Boolean).length;
                const chars = content.length;
                const wordCountErrorClass = (words < minWords || words > maxWords) ? 'error' : '';

                card.innerHTML = `
                    <div class="paragraph-card-header">
                        ${!block.pinned ? '<div class="drag-handle">☰</div>' : '<div class="pinned-placeholder"></div>'}
                        <input type="text" value="${block.title}">
                    </div>
                    <textarea>${content}</textarea>
                    <input type="text" class="ai-instruction-input" placeholder="AI Instructions (e.g., make it more poetic)">
                    <div class="paragraph-card-footer">
                        <div class="count-container">
                            <span class="word-count-display ${wordCountErrorClass}">${words} words</span>
                            <span class="count-separator">/</span>
                            <span class="char-count-display">${chars} chars</span>
                        </div>
                        <div class="paragraph-card-actions">
                            <button class="regenerate-btn btn-card-action">
                                <span class="btn-text">Regenerate</span>
                                <div class="spinner-overlay"><div class="spinner"></div></div>
                            </button>
                            ${block.deletable ? '<button class="delete-btn btn-card-action">Delete</button>' : ''}
                            <button class="save-btn btn-card-action">Save</button>
                        </div>
                    </div>
                `;
                
                const container = block.pinned === 'top' ? headerContainer : block.pinned === 'bottom' ? footerContainer : draggableContainer;
                container.appendChild(card);
            });

            attachAllListeners();
        };

        const loadTemplate = async (aspectRatio) => {
            const res = await fetch(`/admin/gdws/template/${aspectRatio}`);
            const data = await res.json();
            minWords = data.settings?.minWords || 20;
            maxWords = data.settings?.maxWords || 150;
            document.getElementById('min-words').value = minWords;
            document.getElementById('max-words').value = maxWords;
            renderBlocks(data.blocks);
        };

        new Sortable(draggableContainer, {
            animation: 150,
            handle: '.drag-handle',
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
        });
        
        const updateCounts = (textarea) => {
            const card = textarea.closest('.paragraph-card');
            const wordDisplay = card.querySelector('.word-count-display');
            const charDisplay = card.querySelector('.char-count-display');
            
            const content = textarea.value;
            const words = content.split(/\s+/).filter(Boolean).length;
            const chars = content.length;

            wordDisplay.textContent = `${words} words`;
            charDisplay.textContent = `${chars} chars`;
            
            wordDisplay.classList.toggle('error', words < minWords || words > maxWords);
        };
        
        const attachCardListeners = (card) => {
            const id = card.dataset.id;
            const deleteBtn = card.querySelector('.delete-btn');
            const regenerateBtn = card.querySelector('.regenerate-btn');
            const saveBtn = card.querySelector('.save-btn');
            const textarea = card.querySelector('textarea');
            const instructionInput = card.querySelector('.ai-instruction-input');
            const titleInput = card.querySelector('.paragraph-card-header input[type="text"]');
            let originalTitle = titleInput.value;

            if (deleteBtn) {
                deleteBtn.onclick = () => {
                    currentBlockToDelete = id;
                    currentCardToDelete = card;
                    deleteModal.style.display = 'flex';
                };
            }
            
            if (regenerateBtn) {
                regenerateBtn.onclick = async () => {
                    const btnText = regenerateBtn.querySelector('.btn-text');
                    const spinner = regenerateBtn.querySelector('.spinner-overlay');

                    btnText.style.visibility = 'hidden';
                    spinner.style.display = 'flex';
                    regenerateBtn.disabled = true;

                    const aiProvider = document.getElementById('ai-provider').value;
                    const instructions = instructionInput.value;

                    const res = await fetch('/admin/gdws/regenerate-paragraph', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ content: textarea.value, instructions, ai_provider: aiProvider })
                    });
                    const data = await res.json();
                    textarea.value = data.new_content;
                    updateCounts(textarea);

                    btnText.style.visibility = 'visible';
                    spinner.style.display = 'none';
                    regenerateBtn.disabled = false;
                };
            }

            if (saveBtn) {
                saveBtn.onclick = () => {
                    const isNew = card.dataset.isNew === 'true';
                    const payload = {
                        id: isNew ? `var_${Date.now()}` : id,
                        title: titleInput.value,
                        content: textarea.value,
                        type: slugify(titleInput.value)
                    };

                    if (!isNew && originalTitle !== titleInput.value) {
                        fetch('/admin/gdws/rename-paragraph-type', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ old_title: originalTitle, new_title: titleInput.value })
                        });
                        originalTitle = titleInput.value;
                    }

                    fetch('/admin/gdws/save-paragraph', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    }).then(res => res.json()).then(data => {
                        if (data.status === 'success') {
                            alert('Paragraph saved!');
                            card.dataset.id = data.new_id;
                            card.dataset.isNew = 'false';
                        } else {
                            alert(`Error: ${data.message}`);
                        }
                    });
                };
            }

            if (textarea) {
                textarea.addEventListener('input', () => updateCounts(textarea));
                updateCounts(textarea);
            }
        };
        
        const attachAllListeners = () => {
            document.querySelectorAll('.paragraph-card').forEach(attachCardListeners);
        };

        aspectRatioSelector.addEventListener('change', (e) => {
            loadTemplate(e.target.value);
        });

        const versionCheckerContainer = document.getElementById('version-checker');
        const fetchVersionStatus = async () => {
            const mockStatus = {
                expected: { 
                    app_version: "2.5.1",
                    config_version: "1.2.0", 
                    env_version: "1.1.0", 
                    openai_primary_model: "gpt-4o",
                    openai_fallback_model: "gpt-4-turbo"
                },
                loaded: { 
                    app_version: "2.5.1",
                    config_version: "1.2.0", 
                    env_version: "1.0.0", // Mismatch example
                    openai_primary_model: "gpt-4.1", // Mismatch example
                    openai_fallback_model: "gpt-4-turbo"
                }
            };
            
            let html = '';
            for (const key in mockStatus.expected) {
                const expected = mockStatus.expected[key];
                const loaded = mockStatus.loaded[key] || 'Not Set';
                const isMatch = expected === loaded;
                const statusClass = isMatch ? 'status-match' : 'status-mismatch';
                const statusIcon = isMatch ? '✅' : '❌';
                
                html += `
                    <div class="version-status">
                        <strong>${key.replace(/_/g, ' ').replace(/(?:^|\s)\S/g, a => a.toUpperCase())}:</strong>
                        <span class="${statusClass}">${statusIcon} ${isMatch ? 'Match' : 'Mismatch'}</span><br>
                        <small>Expected: ${expected} | Loaded: ${loaded}</small>
                    </div>
                `;
            }
            versionCheckerContainer.innerHTML = html;
        };
        fetchVersionStatus();

        document.getElementById('save-new-version-btn').addEventListener('click', () => {
            const key = document.getElementById('new-version-key').value;
            const value = document.getElementById('new-version-value').value;
            if (!value) {
                alert('Please enter a new version number.');
                return;
            }
            console.log(`Saving new version: { "${key}": "${value}" }`);
            alert('New version saved to console!');
        });


        // --- OTHER EVENT LISTENERS ---
        document.getElementById('add-paragraph-btn').addEventListener('click', () => {
            const newId = `block_${Date.now()}`;
            const newBlock = { id: newId, title: "New Paragraph", content: "", pinned: false, deletable: true, isNew: true };
            renderBlocks([...getCurrentBlocks(), newBlock]);
        });

        document.getElementById('shuffle-btn').addEventListener('click', () => {
            const cards = Array.from(draggableContainer.children);
            for (let i = cards.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [cards[i], cards[j]] = [cards[j], cards[i]];
            }
            cards.forEach(card => draggableContainer.appendChild(card));
        });

        document.getElementById('save-rules-btn').addEventListener('click', () => {
            minWords = parseInt(document.getElementById('min-words').value, 10);
            maxWords = parseInt(document.getElementById('max-words').value, 10);
            console.log('Saving rules:', { minWords, maxWords });
            alert('Content rules saved!');
            document.querySelectorAll('textarea').forEach(updateCounts);
        });

        document.getElementById('cancel-delete-btn').addEventListener('click', () => {
            deleteModal.style.display = 'none';
        });

        document.getElementById('confirm-delete-btn').addEventListener('click', () => {
            if (currentCardToDelete) {
                currentCardToDelete.remove();
            }
            deleteModal.style.display = 'none';
            console.log(`Deleted block ${currentBlockToDelete}`);
        });
        
        document.getElementById('save-all-btn').addEventListener('click', () => {
            const allBlocks = [];
            const containers = [headerContainer, draggableContainer, footerContainer];
            containers.forEach(container => {
                container.querySelectorAll('.paragraph-card').forEach(card => {
                    allBlocks.push({
                        id: card.dataset.id,
                        title: card.querySelector('input[type="text"]').value,
                        content: card.querySelector('textarea').value,
                        pinned: card.closest('#header-blocks') ? 'top' : (card.closest('#footer-blocks') ? 'bottom' : false)
                    });
                });
            });

            console.log("Saving all data:", JSON.stringify(allBlocks, null, 2));
            alert("All changes saved to console! Check the developer tools.");
        });

        document.getElementById('regenerate-all-btn').addEventListener('click', () => {
            document.querySelectorAll('.regenerate-btn').forEach(btn => btn.click());
        });
        
        const getCurrentBlocks = () => {
             const allBlocks = [];
            const containers = [headerContainer, draggableContainer, footerContainer];
            containers.forEach(container => {
                container.querySelectorAll('.paragraph-card').forEach(card => {
                    allBlocks.push({
                        id: card.dataset.id,
                        title: card.querySelector('input[type="text"]').value,
                        content: card.querySelector('textarea').value,
                        pinned: card.closest('#header-blocks') ? 'top' : (card.closest('#footer-blocks') ? 'bottom' : false),
                        deletable: !!card.querySelector('.delete-btn')
                    });
                });
            });
            return allBlocks;
        };

        // Initial load
        loadTemplate(aspectRatioSelector.value);
    });
</script>
{% endblock %}

```

---
## 📄 templates/locked.html

```html
{# Gallery of all finalised artworks with edit and export actions. #}
{% extends "main.html" %}
{% block title %}Locked Artworks{% endblock %}
{% block content %}
<h1>Locked Artworks</h1>
<p class="help-tip">These artworks are locked and cannot be edited until unlocked.</p>
<div class="view-toggle">
  <button id="grid-view-btn" class="btn-small">Grid</button>
  <button id="list-view-btn" class="btn-small">List</button>
</div>
<form method="post" action="{{ url_for('exports.run_sellbrite_export', locked=1) }}">
  <button type="submit" class="btn-black">Export to CSV</button>
</form>
{% if not artworks %}
  <p>No artworks have been finalised yet. Come back after you approve some beautiful pieces!</p>
{% else %}
<div class="finalised-grid">
  {% for art in artworks %}
  <div class="final-card">
    <div class="card-thumb">
      {% if art.main_image %}
      <a href="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.main_image) }}" class="final-img-link" data-img="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.main_image) }}">
        <img src="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.main_image) }}" class="card-img-top" alt="{{ art.title }}">
      </a>
      {% else %}
      <img src="{{ url_for('static', filename='img/no-image.svg') }}" class="card-img-top" alt="No image">
      {% endif %}
    </div>
    <div class="card-details">
      <div class="card-title">{{ art.title }}</div>
      <div class="desc-snippet" title="{{ art.description }}">
        {{ art.description[:200] }}{% if art.description|length > 200 %}...{% endif %}
      </div>
      <div>SKU: {{ art.sku }}</div>
      <div>Price: {{ art.price }}</div>
      <div>Colours: {{ art.primary_colour }} / {{ art.secondary_colour }}</div>
      <div>SEO: {{ art.seo_filename }}</div>
      <div>Tags: {{ art.tags|join(', ') }}</div>
      <div>Materials: {{ art.materials|join(', ') }}</div>
      {% if art.mockups %}
      <div class="mini-mockup-grid">
        {% for m in art.mockups %}
        <img src="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=m.filename) }}" alt="mockup"/>
        {% endfor %}
      </div>
      {% endif %}
      {% if art.images %}
      <details class="img-urls">
        <summary>Image URLs</summary>
        <ul>
          {% for img in art.images %}
          <li>
            <a href="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=img.split('/')[-1]) }}" target="_blank">/{{ img }}</a>
          </li>
          {% endfor %}
        </ul>
      </details>
      {% endif %}
    </div>
  <div class="final-actions">
    <a class="btn-black btn-disabled" aria-disabled="true">Edit</a>
    <form method="post" action="{{ url_for('artwork.unlock_listing', aspect=art.aspect, filename=art.filename) }}" style="display:inline;">
      <button type="submit" class="btn-black">Unlock</button>
    </form>
    <form method="post" action="{{ url_for('artwork.delete_finalised', aspect=art.aspect, filename=art.filename) }}" class="locked-delete-form" style="display:inline;">
      <input type="hidden" name="confirm" value="">
      <button type="submit" class="btn-black btn-danger">Delete</button>
    </form>
  </div>
  </div>
  {% endfor %}
</div>
{% endif %}
<div id="final-modal-bg" class="modal-bg">
  <button id="final-modal-close" class="modal-close" aria-label="Close modal">&times;</button>
  <div class="modal-img"><img id="final-modal-img" src="" alt="Full image"/></div>
</div>
<script>
  document.querySelectorAll('.final-img-link').forEach(link => {
    link.addEventListener('click', function(e){
      e.preventDefault();
      const modal = document.getElementById('final-modal-bg');
      const img = document.getElementById('final-modal-img');
      img.src = this.dataset.img;
      modal.style.display = 'flex';
    });
  });
  document.getElementById('final-modal-close').onclick = function(){
    document.getElementById('final-modal-bg').style.display='none';
    document.getElementById('final-modal-img').src='';
  };
  document.getElementById('final-modal-bg').onclick = function(e){
    if(e.target===this){
      this.style.display='none';
      document.getElementById('final-modal-img').src='';
    }
  };
  document.querySelectorAll('.locked-delete-form').forEach(f=>{
    f.addEventListener('submit',function(ev){
      const val=prompt('This listing is locked and will be permanently deleted. Type DELETE to confirm');
      if(val!=='DELETE'){ev.preventDefault();}
      else{this.querySelector('input[name="confirm"]').value='DELETE';}
    });
  });
  const gBtn=document.getElementById('grid-view-btn');
  const lBtn=document.getElementById('list-view-btn');
  const grid=document.querySelector('.finalised-grid');
  function apply(v){ if(v==='list'){grid.classList.add('list-view');} else {grid.classList.remove('list-view');} }
  if(gBtn) gBtn.addEventListener('click',()=>{apply('grid'); localStorage.setItem('lockedView','grid');});
  if(lBtn) lBtn.addEventListener('click',()=>{apply('list'); localStorage.setItem('lockedView','list');});
  apply(localStorage.getItem('lockedView')||'grid');
</script>
{% endblock %}

```

---
## 📄 templates/composites_preview.html

```html
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}Composite Preview | CapitalArt{% endblock %}
{% block content %}
<h1 style="text-align:center;">Composite Preview: {{ seo_folder }}</h1>
{% if listing %}
  <div style="text-align:center;margin-bottom:1.5em;">
    <img src="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=seo_folder+'.jpg') }}" alt="artwork" style="max-width:260px;border-radius:8px;box-shadow:0 2px 6px #0002;">
  </div>
{% endif %}
{% if images %}
<div class="grid">
  {% for img in images %}
  <div class="item">
    {% if img.exists %}
    <img src="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=img.filename) }}" alt="{{ img.filename }}">
    {% else %}
    <div class="missing-img">Image Not Found</div>
    {% endif %}
    <div style="font-size:0.9em;color:#555;word-break:break-all;">{{ img.filename }}</div>
    {% if img.category %}<div style="color:#888;font-size:0.9em;">{{ img.category }}</div>{% endif %}
    <form method="post" action="{{ url_for('artwork.regenerate_composite', seo_folder=seo_folder, slot_index=img.index) }}">
      <button type="submit" class="btn btn-reject">Regenerate</button>
    </form>
  </div>
  {% endfor %}
</div>
<form method="post" action="{{ url_for('artwork.approve_composites', seo_folder=seo_folder) }}" style="text-align:center;margin-top:2em;">
  <button type="submit" class="composite-btn">Finalize &amp; Approve</button>
</form>
{% else %}
<p style="text-align:center;margin:2em 0;">No composites found.</p>
{% endif %}
<div style="text-align:center;margin-top:2em;">
  <a href="{{ url_for('artwork.select') }}" class="composite-btn" style="background:#666;">Back to Selector</a>
</div>
{% endblock %}

```

---
## 📄 templates/missing_endpoint.html

```html
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}Missing Endpoint{% endblock %}
{% block content %}
<h1>Endpoint Error</h1>
<p>{{ error }}</p>
{% endblock %}

```

---
## 📄 templates/gallery.html

```html

```

---
## 📄 templates/main.html

```html
{# main.html - CapitalArt Main Layout Template #}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{% block title %}CapitalArt{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
  <!-- ========== [MA.1] Top Navigation ========== -->
  <nav class="main-nav">
    <a href="{{ url_for('artwork.home') }}">Home</a>
    <a href="{{ url_for('artwork.upload_artwork') }}">Upload</a>
    <a href="{{ url_for('artwork.artworks') }}">Artwork Gallery</a>
    <a href="{{ url_for('artwork.finalised_gallery') }}">Finalised</a>
    <a href="{{ url_for('artwork.locked_gallery') }}">Locked</a>
    <a href="{{ url_for('exports.sellbrite_exports') }}">Exports</a>
    <a href="{{ url_for('admin.debug_status') }}">Admin</a>
    <a href="{{ url_for('gdws_admin.editor') }}">GDWS Editor</a>
  </nav>

  <main>
    <!-- ========== [MA.2] Flash Message Area ========== -->
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="flash">
          {% for category, msg in messages %}
            <div class="flash-{{ category|default('info') }}">{{ msg }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}

    <!-- ========== [MA.3] Main Content Block ========== -->
    {% block content %}{% endblock %}
  </main>

  <!-- ========== [MA.4] Analysis Progress Modal ========== -->
  <div id="analysis-modal" class="analysis-modal">
    <div class="analysis-box">
      <button id="analysis-close" class="modal-close" aria-label="Close">&times;</button>
      <h3>Analyzing Artwork...</h3>
      <div class="analysis-progress" aria-label="analysis progress">
        <div id="analysis-bar" class="analysis-progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
      </div>
      <div id="analysis-status" class="analysis-status" aria-live="polite"></div>
      <div class="analysis-friendly">This can take up to a couple of minutes. Go have a coffee while the AI works its magic! ☕️</div>
    </div>
  </div>

  <!-- ========== [MA.5] Analysis Modal JavaScript ========== -->
  <script>
    document.addEventListener('DOMContentLoaded', function() {
      const modal = document.getElementById('analysis-modal');
      const bar = document.getElementById('analysis-bar');
      const statusEl = document.getElementById('analysis-status');
      const closeBtn = document.getElementById('analysis-close');
      const statusUrl = "{{ url_for('artwork.analysis_status') }}";
      let pollStatus;

      function openModal() {
        modal.classList.add('active');
        fetchStatus();
        pollStatus = setInterval(fetchStatus, 1000);
      }

      function closeModal() {
        modal.classList.remove('active');
        clearInterval(pollStatus);
      }

      function fetchStatus() {
        fetch(statusUrl)
          .then(r => r.json())
          .then(d => {
            const pct = d.percent || 0;
            bar.style.width = pct + '%';
            bar.setAttribute('aria-valuenow', pct);
            statusEl.textContent = d.step || '';
          });
      }

      if (closeBtn) closeBtn.addEventListener('click', closeModal);

      document.querySelectorAll('form.analyze-form').forEach(f => {
        f.addEventListener('submit', function(ev) {
          ev.preventDefault();
          openModal();
          const data = new FormData(f);
          fetch(f.action, { method: 'POST', body: data })
            .then(response => {
              if (response.ok && response.redirected) {
                window.location.href = response.url;
              } else {
                console.error("Form submission failed or did not redirect.");
                closeModal();
              }
            })
            .catch(error => {
              console.error("Network error during form submission:", error);
              closeModal();
            });
        });
      });
    });
  </script>
</body>
</html>

```

---
## 📄 templates/sellbrite_exports.html

```html
{% extends "main.html" %}
{% block title %}Sellbrite Exports{% endblock %}
{% block content %}
<h1>Sellbrite Exports</h1>
<p class="help-tip">Review all previous exports below. Warnings show missing fields or short descriptions.</p>
<div class="export-actions">
  <form method="post" action="{{ url_for('exports.run_sellbrite_export') }}" style="display:inline">
    <button type="submit" class="btn-black">Export Now (All)</button>
  </form>
  <form method="post" action="{{ url_for('exports.run_sellbrite_export', locked=1) }}" style="display:inline">
    <button type="submit" class="btn-black">Export Now (Locked)</button>
  </form>
</div>
<table class="exports-table">
  <thead>
    <tr><th>Date</th><th>Type</th><th>CSV</th><th>Preview</th><th>Log</th></tr>
  </thead>
  <tbody>
  {% for e in exports %}
    <tr>
      <td>{{ e.mtime.strftime('%Y-%m-%d %H:%M') }}</td>
      <td>{{ e.type }}</td>
      <td><a href="{{ url_for('exports.download_sellbrite', csv_filename=e.name) }}">{{ e.name }}</a></td>
      <td><a href="{{ url_for('exports.preview_sellbrite_csv', csv_filename=e.name) }}">Preview</a></td>
      <td>{% if e.log %}<a href="{{ url_for('exports.view_sellbrite_log', log_filename=e.log) }}">Log</a>{% else %}-{% endif %}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}

```

---
## 📄 templates/sellbrite_csv_preview.html

```html
{% extends "main.html" %}
{% block title %}Preview {{ csv_filename }}{% endblock %}
{% block content %}
<h1>Preview {{ csv_filename }}</h1>
<p><a class="btn-black" href="{{ url_for('exports.download_sellbrite', csv_filename=csv_filename) }}">Download Full CSV</a></p>
<div class="csv-preview">
  <table class="exports-table">
    <thead>
      <tr>
        {% for h in header %}<th>{{ h }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}

```

---
## 📄 templates/finalised.html

```html
{# Gallery of all finalised artworks with edit and export actions. #}
{% extends "main.html" %}
{% block title %}Finalised Artworks{% endblock %}
{% block content %}
<h1>Finalised Artworks</h1>
<p class="help-tip">Finalised artworks are ready for publishing or exporting to Sellbrite. You can still edit or delete them here.</p>
<div class="view-toggle">
  <button id="grid-view-btn" class="btn-small">Grid</button>
  <button id="list-view-btn" class="btn-small">List</button>
</div>
<form method="post" action="{{ url_for('exports.run_sellbrite_export') }}">
  <button type="submit" class="btn-black">Export to CSV</button>
</form>
{% if not artworks %}
  <p>No artworks have been finalised yet. Come back after you approve some beautiful pieces!</p>
{% else %}
<div class="finalised-grid">
  {% for art in artworks %}
  <div class="final-card">
    <div class="card-thumb">
      {% if art.main_image %}
      <a href="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.main_image) }}" class="final-img-link" data-img="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.main_image) }}">
        <img src="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.main_image) }}" class="card-img-top" alt="{{ art.title }}">
      </a>
      {% else %}
      <img src="{{ url_for('static', filename='img/no-image.svg') }}" class="card-img-top" alt="No image">
      {% endif %}
    </div>
    <div class="card-details">
      <div class="card-title">{{ art.title }}{% if art.locked %} <span class="locked-badge">Locked</span>{% endif %}</div>
      <div class="desc-snippet" title="{{ art.description }}">
        {{ art.description[:200] }}{% if art.description|length > 200 %}...{% endif %}
      </div>
      <div>SKU: {{ art.sku }}</div>
      <div>Price: {{ art.price }}</div>
      <div>Colours: {{ art.primary_colour }} / {{ art.secondary_colour }}</div>
      <div>SEO: {{ art.seo_filename }}</div>
      <div>Tags: {{ art.tags|join(', ') }}</div>
      <div>Materials: {{ art.materials|join(', ') }}</div>
      {% if art.mockups %}
      <div class="mini-mockup-grid">
        {% for m in art.mockups %}
        <img src="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=m.filename) }}" alt="mockup"/>
        {% endfor %}
      </div>
      {% endif %}
      {% if art.images %}
      <details class="img-urls">
        <summary>Image URLs</summary>
        <ul>
          {% for img in art.images %}
          <li>
            <a href="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=img.split('/')[-1]) }}" target="_blank">/{{ img }}</a>
          </li>
          {% endfor %}
        </ul>
      </details>
      {% endif %}
    </div>
  <div class="final-actions">
    {% if art.locked %}
      <a class="btn-black btn-disabled" aria-disabled="true">Edit</a>
      <form method="post" action="{{ url_for('artwork.unlock_listing', aspect=art.aspect, filename=art.filename) }}" style="display:inline;">
        <button type="submit" class="btn-black">Unlock</button>
      </form>
      <form method="post" action="{{ url_for('artwork.delete_finalised', aspect=art.aspect, filename=art.filename) }}" class="locked-delete-form" style="display:inline;">
        <input type="hidden" name="confirm" value="">
        <button type="submit" class="btn-black btn-danger">Delete</button>
      </form>
    {% else %}
      <a href="{{ url_for('artwork.edit_listing', aspect=art.aspect, filename=art.filename) }}" class="btn-black">Edit</a>
      <form method="post" action="{{ url_for('artwork.lock_listing', aspect=art.aspect, filename=art.filename) }}" style="display:inline;">
        <button type="submit" class="btn-black">Lock it in</button>
      </form>
      <form method="post" action="{{ url_for('artwork.delete_finalised', aspect=art.aspect, filename=art.filename) }}" onsubmit="return confirm('Delete this artwork?');" style="display:inline;">
        <button type="submit" class="btn-black btn-danger">Delete</button>
      </form>
    {% endif %}
  </div>
  </div>
  {% endfor %}
</div>
{% endif %}
<div id="final-modal-bg" class="modal-bg">
  <button id="final-modal-close" class="modal-close" aria-label="Close modal">&times;</button>
  <div class="modal-img"><img id="final-modal-img" src="" alt="Full image"/></div>
</div>
<script>
  document.querySelectorAll('.final-img-link').forEach(link => {
    link.addEventListener('click', function(e){
      e.preventDefault();
      const modal = document.getElementById('final-modal-bg');
      const img = document.getElementById('final-modal-img');
      img.src = this.dataset.img;
      modal.style.display = 'flex';
    });
  });
  document.getElementById('final-modal-close').onclick = function(){
    document.getElementById('final-modal-bg').style.display='none';
    document.getElementById('final-modal-img').src='';
  };
  document.getElementById('final-modal-bg').onclick = function(e){
    if(e.target===this){
      this.style.display='none';
      document.getElementById('final-modal-img').src='';
    }
  };
  document.querySelectorAll('.locked-delete-form').forEach(f=>{
    f.addEventListener('submit',function(ev){
      const val=prompt('This listing is locked and will be permanently deleted. Type DELETE to confirm');
      if(val!=='DELETE'){ev.preventDefault();}
      else{this.querySelector('input[name="confirm"]').value='DELETE';}
    });
  });
  const gBtn=document.getElementById('grid-view-btn');
  const lBtn=document.getElementById('list-view-btn');
  const grid=document.querySelector('.finalised-grid');
  function apply(v){
    if(v==='list'){grid.classList.add('list-view');} else {grid.classList.remove('list-view');}
  }
  if(gBtn) gBtn.addEventListener('click',()=>{apply('grid'); localStorage.setItem('view','grid');});
  if(lBtn) lBtn.addEventListener('click',()=>{apply('list'); localStorage.setItem('view','list');});
  apply(localStorage.getItem('view')||'grid');
</script>
{% endblock %}

```

---
## 📄 templates/upload_results.html

```html
{% extends "main.html" %}
{% block title %}Upload Results{% endblock %}
{% block content %}
<h2 class="mb-3">Upload Summary</h2>
<ul>
  {% for r in results %}
    <li>{% if r.success %}✅ {{ r.original }}{% else %}❌ {{ r.original }}: {{ r.error }}{% endif %}</li>
  {% endfor %}
</ul>
<a href="{{ url_for('artwork.artworks') }}" class="btn btn-primary">Return to Gallery</a>
{% endblock %}

```

---
## 📄 templates/sellbrite_log.html

```html
{% extends "main.html" %}
{% block title %}Export Log{% endblock %}
{% block content %}
<h1>Export Log {{ log_filename }}</h1>
<pre class="export-log">{{ log_text }}</pre>
{% endblock %}

```

---
## 📄 templates/edit_listing.html

```html
{# Edit and finalise a single artwork listing with preview and metadata fields. #}
{% extends "main.html" %}
{% block title %}Edit Listing{% endblock %}
{% block content %}

<div class="review-artwork-grid">
  <!-- === Mockup Column === -->
  <div class="mockup-col">
    <div class="main-thumb">
      <a href="#" 
    class="main-thumb-link" 
    data-img="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=seo_folder+'.jpg') }}">
    <img src="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=seo_folder+'-THUMB.jpg') }}" class="main-thumbnail-img" alt="thumbnail">
  </a>
<div class="thumb-note">Click thumbnail for full size</div>
    </div>
    <div>
      <h3>Preview Mockups</h3>
      <div class="mockup-preview-grid">
        {% for m in mockups %}
          <div class="mockup-card">
            {% if m.exists %}
              <a href="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=m.path.name) }}"
                 class="mockup-img-link"
                 data-img="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=m.path.name) }}">
                <img src="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=m.path.name) }}" class="mockup-thumb-img" alt="mockup">
              </a>
            {% else %}
              <div class="missing-img">Image Not Found</div>
            {% endif %}
            <form method="post" action="{{ url_for('artwork.review_swap_mockup', seo_folder=seo_folder, slot_idx=m.index) }}" class="swap-form">
              <select name="new_category">
                {% for c in categories %}
                  <option value="{{ c }}" {% if c == m.category %}selected{% endif %}>{{ c }}</option>
                {% endfor %}
              </select>
              <button type="submit" class="btn btn-sm">Swap</button>
            </form>
          </div>
        {% endfor %}
      </div>
    </div>
  </div>

  <!-- === Edit Fields Column === -->
  <div class="edit-listing-col">
    <h1>Edit Listing</h1>
    <!-- Status at Top -->
    <p class="status-line {% if finalised %}status-finalised{% else %}status-pending{% endif %}">
      Status: This artwork is {% if finalised %}<strong>finalised</strong>{% else %}<em>NOT yet finalised</em>{% endif %}
      {% if locked %}<span class="locked-badge">Locked</span>{% endif %}
    </p>
    <!-- Validation errors -->
    {% if errors %}
      <div class="flash-error">
        <ul>{% for e in errors %}<li>{{ e }}</li>{% endfor %}</ul>
      </div>
    {% endif %}

    <!-- Main Edit Form -->
    <form id="edit-form" method="POST" autocomplete="off">
      <label>Title:</label>
      <textarea name="title" rows="2" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.title|e }}</textarea>

      <label>Description:</label>
      <textarea name="description" rows="12" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.description|e }}</textarea>

      <label>Tags (comma-separated):</label>
      <textarea name="tags" rows="2" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.tags|e }}</textarea>

      <label>Materials (comma-separated):</label>
      <textarea name="materials" rows="2" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.materials|e }}</textarea>

      <div class="row-inline" style="display:flex; gap:1em;">
        <div style="flex:1;">
          <label>Primary Colour:</label>
          <select name="primary_colour" class="long-field" {% if not editable %}disabled{% endif %}>
            {% for col in colour_options %}
              <option value="{{ col }}" {% if artwork.primary_colour==col %}selected{% endif %}>{{ col }}</option>
            {% endfor %}
          </select>
        </div>
        <div style="flex:1;">
          <label>Secondary Colour:</label>
          <select name="secondary_colour" class="long-field" {% if not editable %}disabled{% endif %}>
            {% for col in colour_options %}
              <option value="{{ col }}" {% if artwork.secondary_colour==col %}selected{% endif %}>{{ col }}</option>
            {% endfor %}
          </select>
        </div>
      </div>

      <label>SEO Filename:</label>
      <input type="text" class="long-field" name="seo_filename" value="{{ artwork.seo_filename|e }}" {% if not editable %}disabled{% endif %}>

      <div class="price-sku-row">
        <div>
          <label>Price:</label>
          <input type="text" name="price" value="{{ artwork.price|e }}" class="long-field" {% if not editable %}disabled{% endif %}>
        </div>
        <div>
          <label>SKU:</label>
          <!-- SKU is assigned by the system and never user-editable -->
          <input type="text" value="{{ artwork.sku|e }}" class="long-field" readonly disabled>
        </div>
      </div>

      <label>Image URLs (one per line):</label>
      <textarea name="images" rows="5" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.images|e }}</textarea>
    </form>

    <!-- Action Buttons -->
    <div class="edit-actions-col">
      <button form="edit-form" type="submit" name="action" value="save" class="btn btn-success wide-btn require-images" {% if not editable %}disabled{% endif %}>Save Changes</button>
      <button form="edit-form" type="submit" name="action" value="delete" class="btn btn-danger wide-btn" onclick="return confirm('Delete this artwork and all files?');" {% if not editable %}disabled{% endif %}>Delete</button>
      {% if not finalised %}
        <form method="post" action="{{ url_for('artwork.finalise_artwork', aspect=aspect, filename=filename) }}" style="width:100%;">
          <button type="submit" class="btn btn-primary wide-btn require-images">Finalise</button>
        </form>
      {% endif %}
      <form method="POST" action="{{ url_for('artwork.analyze_artwork', aspect=aspect, filename=filename) }}" style="width:100%;" class="analyze-form">
        <button type="submit" class="btn btn-primary wide-btn" {% if locked %}disabled{% endif %}>Re-analyse Artwork</button>
      </form>
      {% if finalised and not locked %}
        <form method="post" action="{{ url_for('artwork.lock_listing', aspect=aspect, filename=filename) }}" style="width:100%;">
          <button type="submit" class="btn btn-primary wide-btn">Lock it in</button>
        </form>
      {% elif locked %}
        <form method="post" action="{{ url_for('artwork.unlock_listing', aspect=aspect, filename=filename) }}" style="width:100%;">
          <button type="submit" class="btn btn-primary wide-btn">Unlock</button>
        </form>
      {% endif %}
      <form method="post" action="{{ url_for('artwork.reset_sku', aspect=aspect, filename=filename) }}" style="width:100%;">
        <button type="submit" class="btn btn-warning wide-btn" {% if locked %}disabled{% endif %}>Reset SKU</button>
      </form>
    </div>
    {% if openai_analysis %}
      <div class="openai-details">
        <h3>OpenAI Analysis Details</h3>
        {% set entries = openai_analysis if openai_analysis is iterable and openai_analysis.__class__ != dict else [openai_analysis] %}
        {% for info in entries %}
        <table class="openai-table">
          <tr><th>Original File</th><td>{{ info.original_file }}</td></tr>
          <tr><th>Optimized File</th><td>{{ info.optimized_file }}</td></tr>
          <tr><th>Size</th><td>{{ info.size_mb }} MB ({{ info.size_bytes }} bytes)</td></tr>
          <tr><th>Dimensions</th><td>{{ info.dimensions }}</td></tr>
          <tr><th>Time Sent</th><td>{{ info.time_sent }}</td></tr>
          <tr><th>Time Responded</th><td>{{ info.time_responded }}</td></tr>
          <tr><th>Duration</th><td>{{ info.duration_sec }} s</td></tr>
          <tr><th>Status</th><td>{{ info.status }}</td></tr>
          {% if info.api_response %}<tr><th>API Response</th><td>{{ info.api_response }}</td></tr>{% endif %}
          {% if info.naming_method %}<tr><th>Naming Method</th><td>{{ info.naming_method }}{% if info.used_fallback_naming %} (fallback){% endif %}</td></tr>{% endif %}
        </table>
        {% endfor %}
      </div>
    {% endif %}
    {% if generic_text %}
      <div class="dws-section">
        <h3>Dynamic Writing System Output</h3>
        <textarea readonly class="long-field" rows="8">{{ generic_text }}</textarea>
      </div>
    {% endif %}
  </div>
</div>

<!-- Mockup modal for image preview -->
<div id="mockup-modal-bg" class="modal-bg">
  <button id="mockup-modal-close" class="modal-close" aria-label="Close modal">&times;</button>
  <div class="modal-img">
    <img id="mockup-modal-img" src="" alt="Full-size Mockup Preview" />
  </div>
</div>

<script>
  // Wait for DOM (robust for template includes)
  document.addEventListener('DOMContentLoaded', function() {
    const modalBg = document.getElementById('mockup-modal-bg');
    const modalImg = document.getElementById('mockup-modal-img');
    const modalClose = document.getElementById('mockup-modal-close');

    // --- Helper to open modal with any img ---
    function openModal(imgUrl) {
      if (modalImg) modalImg.src = imgUrl;
      if (modalBg) modalBg.style.display = 'flex';
    }
    function closeModal() {
      if (modalBg) modalBg.style.display = 'none';
      if (modalImg) modalImg.src = '';
    }

    // --- Attach to mockup images ---
    document.querySelectorAll('.mockup-img-link').forEach(link => {
      link.addEventListener('click', function(e) {
        e.preventDefault();
        openModal(this.dataset.img);
      });
    });

    // --- Attach to main artwork thumbnail ---
    const thumbLink = document.querySelector('.main-thumb-link');
    if (thumbLink) {
      thumbLink.addEventListener('click', function(e) {
        e.preventDefault();
        openModal(this.dataset.img);
      });
    }

    // --- Close modal on cross click ---
    if (modalClose) {
      modalClose.onclick = closeModal;
    }

    // --- Close modal on background click ---
    if (modalBg) {
      modalBg.onclick = function(e) {
        if (e.target === this) closeModal();
      };
    }

    // --- Optional: ESC key closes modal ---
    document.addEventListener('keydown', function(e) {
      if (e.key === "Escape") closeModal();
    });

    // === Enable/disable buttons depending on image field ===
    function toggleActionBtns() {
      const txt = document.querySelector('textarea[name="images"]');
      const disabled = !(txt && txt.value.trim());
      document.querySelectorAll('.require-images').forEach(btn => { btn.disabled = disabled; });
    }
    const imagesTextarea = document.querySelector('textarea[name="images"]');
    if (imagesTextarea) imagesTextarea.addEventListener('input', toggleActionBtns);
    toggleActionBtns();
  });
</script>

{% endblock %}

```

---
## 📄 templates/upload.html

```html
{% extends "main.html" %}
{% block title %}Upload Artwork{% endblock %}
{% block content %}
<h2 class="mb-3">Upload New Artwork</h2>
<form id="upload-form" method="post" enctype="multipart/form-data">
  <input id="file-input" type="file" name="images" accept="image/*" multiple hidden>
  <div id="dropzone" class="upload-dropzone">
    Drag & Drop images here or click to choose files
  </div>
  <ul id="upload-list" class="upload-list"></ul>
</form>
<script src="{{ url_for('static', filename='js/upload.js') }}"></script>
{% endblock %}

```

---
## 📄 assets/style.css

```css
body {
  font-family: system-ui, sans-serif;
  margin: 0;
  background: #f9f9f9;
  color: #222;
}
header, footer {
  background: #333;
  color: #fff;
  padding: 1em;
  text-align: center;
}
main {
  display: flex;
  flex-wrap: wrap;
  padding: 2em;
  gap: 1em;
  justify-content: center;
}
.artwork {
  border: 1px solid #ccc;
  background: #fff;
  padding: 1em;
  max-width: 300px;
}
.artwork img {
  max-width: 100%;
  height: auto;
  display: block;
}

```

---
## 📄 routes/sellbrite_service.py

```py
"""Sellbrite API integration utilities."""

from __future__ import annotations

import base64
import logging
import os
from typing import Dict

import requests
from flask import Blueprint, jsonify
from dotenv import load_dotenv

load_dotenv()

SELLBRITE_TOKEN = os.getenv("SELLBRITE_TOKEN")
SELLBRITE_SECRET = os.getenv("SELLBRITE_SECRET")
API_BASE = "https://api.sellbrite.com/v1"

logger = logging.getLogger(__name__)

bp = Blueprint("sellbrite", __name__)


def _auth_header() -> Dict[str, str]:
    """Return the HTTP Authorization header for Sellbrite."""
    if not SELLBRITE_TOKEN or not SELLBRITE_SECRET:
        logger.error("Sellbrite credentials not configured")
        return {}
    creds = f"{SELLBRITE_TOKEN}:{SELLBRITE_SECRET}".encode("utf-8")
    encoded = base64.b64encode(creds).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}


def test_sellbrite_connection() -> bool:
    """Attempt a simple authenticated request to verify credentials."""
    url = f"{API_BASE}/products"
    try:
        resp = requests.get(url, headers=_auth_header(), timeout=10)
    except requests.RequestException as exc:
        logger.error("Sellbrite connection error: %s", exc)
        return False
    if resp.status_code == 200:
        logger.info("Sellbrite authentication succeeded")
        return True
    logger.error(
        "Sellbrite authentication failed: %s %s", resp.status_code, resp.text
    )
    return False


@bp.route("/sellbrite/test")
def sellbrite_test():
    """Flask route demonstrating a simple API connectivity check."""
    success = test_sellbrite_connection()
    status = 200 if success else 500
    return jsonify({"success": success}), status


if __name__ == "__main__":
    ok = test_sellbrite_connection()
    print("Connection successful" if ok else "Connection failed")

```

---
## 📄 routes/sellbrite_export.py

```py
"""Utilities for exporting listings to Sellbrite.

Field mapping between our artwork JSON and Sellbrite's Listings API:

| JSON field       | Sellbrite field |
|------------------|-----------------|
| title            | name            |
| description      | description     |
| tags             | tags            |
| materials        | materials       |
| primary_colour   | primary_colour  |
| secondary_colour | secondary_colour|
| seo_filename     | seo_filename    |
| sku              | sku             |
| price            | price           |
| images           | images          |
"""

from __future__ import annotations

from typing import Any, Dict


def generate_sellbrite_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dictionary formatted for the Sellbrite Listings API."""
    sb = {
        "sku": data.get("sku"),
        "name": data.get("title"),
        "description": data.get("description"),
        "price": data.get("price"),
        "tags": data.get("tags", []),
        "materials": data.get("materials", []),
        "primary_colour": data.get("primary_colour"),
        "secondary_colour": data.get("secondary_colour"),
        "seo_filename": data.get("seo_filename"),
        "images": data.get("images", []),
    }
    return {k: v for k, v in sb.items() if v not in (None, "", [])}

```

---
## 📄 routes/__init__.py

```py

```

---
## 📄 routes/gdws_admin_routes.py

```py
from flask import Blueprint, render_template, request, jsonify
import json
import os
import random
import re
from pathlib import Path
import shutil
from datetime import datetime

from config import BASE_DIR
from routes.utils import get_menu
from utils.ai_services import call_ai_to_rewrite  # We will create this module next

GDWS_CONTENT_PATH = BASE_DIR / "gdws_content"

bp = Blueprint("gdws_admin", __name__, url_prefix="/admin/gdws")

def slugify(text):
    """A simple function to create a filesystem-safe name."""
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)


def get_paragraph_folders():
    if not GDWS_CONTENT_PATH.exists():
        return []
    return [p.name for p in GDWS_CONTENT_PATH.iterdir() if p.is_dir()]


@bp.route("/")
def editor():
    """Renders the main GDWS editor page."""
    return render_template("dws_editor.html", menu=get_menu())


@bp.route("/template/<aspect_ratio>")
def get_template_data(aspect_ratio):
    """
    Fetches a set of paragraphs for a given aspect ratio template.
    This simulates the final assembly process for preview in the editor.
    """
    # Note: In this new model, aspect ratio might just define which paragraph
    # types to load, or it might load a base template that you can edit.
    # For now, we'll load one random variation from each folder.

    all_blocks = []
    paragraph_folders = get_paragraph_folders()

    for folder_name in paragraph_folders:
        folder_path = GDWS_CONTENT_PATH / folder_name
        variations = list(folder_path.glob("*.json"))
        if variations:
            random_variation_path = random.choice(variations)
            with open(random_variation_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Add any other necessary fields for the frontend
            data['deletable'] = True  # Example
            data['pinned'] = False  # Example
            all_blocks.append(data)

    # You can add logic here for pinned blocks etc.
    # This is a simplified example.
    return jsonify({"templateId": aspect_ratio, "blocks": all_blocks})


@bp.route("/regenerate-paragraph", methods=['POST'])
def regenerate_paragraph():
    """Handles AI regeneration for a single paragraph."""
    data = request.json
    prompt = (
        f"Rewrite the following text based on the instruction. "
        f"Instruction: '{data.get('instructions', 'make it better')}'. "
        f"Original Text: '{data.get('content')}'"
    )

    new_text = call_ai_to_rewrite(
        prompt,
        provider=data.get('ai_provider', 'openai')
    )

    return jsonify({"new_content": new_text})


@bp.route("/save-paragraph", methods=['POST'])
def save_paragraph():
    """Saves a single paragraph variation to a JSON file."""
    data = request.json
    title = data.get('title')
    content = data.get('content')

    # The folder name is derived from the title
    folder_name = slugify(title)
    folder_path = GDWS_CONTENT_PATH / folder_name
    folder_path.mkdir(exist_ok=True)

    # Create a unique filename for this variation
    variation_id = data.get('id', f"var_{int(datetime.now().timestamp())}")
    file_path = folder_path / f"{variation_id}.json"

    save_data = {
        "id": variation_id,
        "title": title,
        "content": content,
        "version": "1.0",
        "last_updated": datetime.now().isoformat()
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=4)

    return jsonify({"status": "success", "message": f"Saved {file_path}", "new_id": variation_id})


@bp.route("/rename-paragraph-type", methods=['POST'])
def rename_paragraph_type():
    """Renames a paragraph folder when a title is changed."""
    data = request.json
    old_title = data.get('old_title')
    new_title = data.get('new_title')

    old_folder_name = slugify(old_title)
    new_folder_name = slugify(new_title)

    old_path = GDWS_CONTENT_PATH / old_folder_name
    new_path = GDWS_CONTENT_PATH / new_folder_name

    if not old_path.exists():
        return jsonify({"status": "error", "message": "Original folder not found."}), 404

    if new_path.exists():
        return jsonify({"status": "error", "message": "A paragraph type with that name already exists."}), 400

    shutil.move(str(old_path), str(new_path))

    return jsonify({"status": "success", "message": f"Renamed folder to {new_folder_name}"})

```

---
## 📄 routes/export_routes.py

```py
from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path
from typing import List, Dict

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, abort

import config
from . import utils
from scripts import sellbrite_csv_export as sb

bp = Blueprint("exports", __name__, url_prefix="/exports")


def _collect_listings(locked_only: bool) -> List[Dict]:
    listings = []
    for listing in config.ARTWORKS_FINALISED_DIR.rglob("*-listing.json"):
        try:
            utils.assign_or_get_sku(listing, config.SKU_TRACKER)
            with open(listing, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if locked_only and not data.get("locked"):
            continue
        listings.append(data)
    return listings


def _export_csv(listings: List[Dict], locked_only: bool) -> tuple[Path, Path, List[str]]:
    config.SELLBRITE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    kind = "locked" if locked_only else "all"
    csv_path = config.SELLBRITE_OUTPUT_DIR / f"sellbrite_{stamp}_{kind}.csv"
    log_path = config.SELLBRITE_OUTPUT_DIR / f"sellbrite_{stamp}_{kind}.log"

    header = sb.read_template_header(config.SELLBRITE_TEMPLATE_CSV)

    errors = utils.validate_all_skus(listings, config.SKU_TRACKER)
    if errors:
        raise ValueError("; ".join(errors))

    warnings: List[str] = []
    def row_iter():
        for data in listings:
            missing = [k for k in ("title", "description", "sku", "price") if not data.get(k)]
            if len((data.get("description") or "").split()) < 400:
                missing.append("description<400w")
            if not data.get("images"):
                missing.append("images")
            if missing:
                warnings.append(f"{data.get('seo_filename', 'unknown')}: {', '.join(missing)}")
            yield data

    sb.export_to_csv(row_iter(), header, csv_path)
    with open(log_path, "w", encoding="utf-8") as log:
        if warnings:
            log.write("\n".join(warnings))
        else:
            log.write("No warnings")
    return csv_path, log_path, warnings


@bp.route("/sellbrite")
def sellbrite_exports():
    items = []
    for csv_file in sorted(config.SELLBRITE_OUTPUT_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True):
        log_file = csv_file.with_suffix(".log")
        export_type = "Locked" if "locked" in csv_file.stem else "All"
        items.append({
            "name": csv_file.name,
            "mtime": datetime.datetime.fromtimestamp(csv_file.stat().st_mtime),
            "type": export_type,
            "log": log_file.name if log_file.exists() else None,
        })
    return render_template("sellbrite_exports.html", exports=items, menu=utils.get_menu())


@bp.route("/sellbrite/run", methods=["GET", "POST"])
def run_sellbrite_export():
    locked = request.args.get("locked") in {"1", "true", "yes"}
    try:
        listings = _collect_listings(locked)
        csv_path, log_path, warns = _export_csv(listings, locked)
        flash(f"Export created: {csv_path.name}", "success")
        if warns:
            flash(f"{len(warns)} warning(s) generated", "warning")
    except Exception as exc:  # noqa: BLE001
        flash(f"Export failed: {exc}", "danger")
    return redirect(url_for("exports.sellbrite_exports"))


@bp.route("/sellbrite/download/<path:csv_filename>")
def download_sellbrite(csv_filename: str):
    return send_from_directory(config.SELLBRITE_OUTPUT_DIR, csv_filename, as_attachment=True)


@bp.route("/sellbrite/preview/<path:csv_filename>")
def preview_sellbrite_csv(csv_filename: str):
    path = config.SELLBRITE_OUTPUT_DIR / csv_filename
    if not path.exists():
        abort(404)
    rows = []
    header: List[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for i, row in enumerate(reader):
            if i >= 20:
                break
            rows.append(row)
    return render_template(
        "sellbrite_csv_preview.html",
        csv_filename=csv_filename,
        header=header,
        rows=rows,
        menu=utils.get_menu(),
    )


@bp.route("/sellbrite/log/<path:log_filename>")
def view_sellbrite_log(log_filename: str):
    path = config.SELLBRITE_OUTPUT_DIR / log_filename
    if not path.exists():
        abort(404)
    text = path.read_text(encoding="utf-8")
    return render_template(
        "sellbrite_log.html",
        log_filename=log_filename,
        log_text=text,
        menu=utils.get_menu(),
    )

```

---
## 📄 routes/utils.py

```py
import os
import json
import random
import re
import logging
import csv
import fcntl
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Iterable

from utils.sku_assigner import get_next_sku, peek_next_sku

from dotenv import load_dotenv
from flask import session
from PIL import Image
import cv2
import numpy as np

from config import (
    BASE_DIR,
    ARTWORKS_INPUT_DIR as ARTWORKS_DIR,
    ARTWORKS_PROCESSED_DIR as ARTWORK_PROCESSED_DIR,
    SELECTIONS_DIR,
    COMPOSITES_DIR,
    ARTWORKS_FINALISED_DIR as FINALISED_DIR,
    LOGS_DIR,
    MOCKUPS_CATEGORISED_DIR as MOCKUPS_DIR,
    ANALYSE_MAX_DIM,
    GENERIC_TEXTS_DIR,
    COORDS_DIR as COORDS_ROOT,
    ANALYZE_SCRIPT_PATH,
    GENERATE_SCRIPT_PATH,
    FILENAME_TEMPLATES,
    UPLOADS_TEMP_DIR,
)

# ==============================
# Paths & Configuration
# ==============================
load_dotenv()

# Etsy accepted colour values
ALLOWED_COLOURS = [
    "Beige",
    "Black",
    "Blue",
    "Bronze",
    "Brown",
    "Clear",
    "Copper",
    "Gold",
    "Grey",
    "Green",
    "Orange",
    "Pink",
    "Purple",
    "Rainbow",
    "Red",
    "Rose gold",
    "Silver",
    "White",
    "Yellow",
]

ALLOWED_COLOURS_LOWER = {c.lower(): c for c in ALLOWED_COLOURS}

Image.MAX_IMAGE_PIXELS = None
for directory in [
    ARTWORKS_DIR,
    MOCKUPS_DIR,
    ARTWORK_PROCESSED_DIR,
    SELECTIONS_DIR,
    COMPOSITES_DIR,
    FINALISED_DIR,
    LOGS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

# ==============================
# Utility Helpers
# ==============================

def get_categories() -> List[str]:
    """Return sorted list of mockup categories."""
    return sorted([
        f.name
        for f in MOCKUPS_DIR.iterdir()
        if f.is_dir() and f.name.lower() != "uncategorised"
    ])


def random_image(category: str) -> Optional[str]:
    """Return a random image filename for the given category."""
    cat_dir = MOCKUPS_DIR / category
    images = [f.name for f in cat_dir.glob("*.png")]
    return random.choice(images) if images else None


def init_slots() -> None:
    """Initialise mockup slot selections in the session."""
    cats = get_categories()
    session["slots"] = [{"category": c, "image": random_image(c)} for c in cats]


def compute_options(slots) -> List[List[str]]:
    """Return category options for each slot."""
    cats = get_categories()
    return [cats for _ in slots]


def relative_to_base(path: Path | str) -> str:
    """Return a path string relative to the project root."""
    return str(Path(path).resolve().relative_to(BASE_DIR))


def resize_image_for_long_edge(image: Image.Image, target_long_edge: int = 2000) -> Image.Image:
    """Resize image maintaining aspect ratio."""
    width, height = image.size
    if width > height:
        new_width = target_long_edge
        new_height = int(height * (target_long_edge / width))
    else:
        new_height = target_long_edge
        new_width = int(width * (target_long_edge / height))
    return image.resize((new_width, new_height), Image.LANCZOS)


def apply_perspective_transform(art_img: Image.Image, mockup_img: Image.Image, dst_coords: list) -> Image.Image:
    """Overlay artwork onto mockup using perspective transform."""
    w, h = art_img.size
    src_points = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst_points = np.float32(dst_coords)
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    art_np = np.array(art_img)
    warped = cv2.warpPerspective(art_np, matrix, (mockup_img.width, mockup_img.height))
    mask = np.any(warped > 0, axis=-1).astype(np.uint8) * 255
    mask = Image.fromarray(mask).convert("L")
    composite = Image.composite(Image.fromarray(warped), mockup_img, mask)
    return composite


def latest_composite_folder() -> Optional[str]:
    """Return the most recent composite output folder name."""
    latest_time = 0
    latest_folder = None
    for folder in ARTWORK_PROCESSED_DIR.iterdir():
        if not folder.is_dir():
            continue
        images = list(folder.glob("*-mockup-*.jpg"))
        if not images:
            continue
        recent = max(images, key=lambda p: p.stat().st_mtime)
        if recent.stat().st_mtime > latest_time:
            latest_time = recent.stat().st_mtime
            latest_folder = folder.name
    return latest_folder


def latest_analyzed_artwork() -> Optional[Dict[str, str]]:
    """Return info about the most recently analysed artwork."""
    latest_time = 0
    latest_info = None
    for folder in ARTWORK_PROCESSED_DIR.iterdir():
        if not folder.is_dir():
            continue
        listing = folder / f"{folder.name}-listing.json"
        if not listing.exists():
            continue
        t = listing.stat().st_mtime
        if t > latest_time:
            latest_time = t
            try:
                with open(listing, "r", encoding="utf-8") as f:
                    data = json.load(f)
                latest_info = {
                    "aspect": data.get("aspect_ratio"),
                    "filename": data.get("filename"),
                }
            except Exception:
                continue
    return latest_info


def clean_display_text(text: str) -> str:
    """Collapse excess whitespace/newlines in description text."""
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r"\n{2,}", "\n\n", cleaned)
    return cleaned


def build_full_listing_text(ai_desc: str, generic_text: str) -> str:
    """Combine AI description and generic text into one string."""
    parts = [clean_display_text(ai_desc), clean_display_text(generic_text)]
    combined = "\n\n".join([p for p in parts if p])
    return clean_display_text(combined)


def slugify(text: str) -> str:
    """Return a slug suitable for filenames."""
    text = re.sub(r"[^\w\- ]+", "", text)
    text = text.strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()


def prettify_slug(slug: str) -> str:
    """Return a human friendly title from a slug or filename."""
    name = os.path.splitext(slug)[0]
    name = name.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name)
    return name.title()


def list_processed_artworks() -> Tuple[List[Dict], set]:
    """Collect processed artworks and set of original filenames."""
    items: List[Dict] = []
    processed_names: set = set()
    for folder in ARTWORK_PROCESSED_DIR.iterdir():
        if not folder.is_dir():
            continue
        listing_path = folder / f"{folder.name}-listing.json"
        if not listing_path.exists():
            continue
        try:
            with open(listing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        original_name = data.get("filename")
        if original_name:
            processed_names.add(original_name)
        items.append(
            {
                "seo_folder": folder.name,
                "filename": original_name or f"{folder.name}.jpg",
                "aspect": data.get("aspect_ratio", ""),
                "title": data.get("title") or prettify_slug(folder.name),
                "thumb": f"{folder.name}-THUMB.jpg",
            }
        )
    items.sort(key=lambda x: x["title"].lower())
    return items, processed_names


def list_ready_to_analyze(_: set) -> List[Dict]:
    """Return artworks uploaded but not yet analyzed."""
    ready: List[Dict] = []
    for qc_path in UPLOADS_TEMP_DIR.glob("*.qc.json"):
        base = qc_path.name[:-8]  # remove .qc.json
        try:
            with open(qc_path, "r", encoding="utf-8") as f:
                qc = json.load(f)
        except Exception:
            continue
        ext = qc.get("extension", "jpg")
        aspect = qc.get("aspect_ratio", "")
        title = prettify_slug(Path(qc.get("original_filename", base)).stem)
        ready.append(
            {
                "aspect": aspect,
                "filename": f"{base}.{ext}",
                "title": title,
                "thumb": f"{base}-thumb.jpg",
                "base": base,
            }
        )
    ready.sort(key=lambda x: x["title"].lower())
    return ready


def list_finalised_artworks() -> List[Dict]:
    """Return artworks that have been finalised."""
    items: List[Dict] = []
    if FINALISED_DIR.exists():
        for folder in FINALISED_DIR.iterdir():
            if not folder.is_dir():
                continue
            listing_file = folder / f"{folder.name}-listing.json"
            if not listing_file.exists():
                continue
            try:
                with open(listing_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            items.append(
                {
                    "seo_folder": folder.name,
                    "filename": data.get("filename", f"{folder.name}.jpg"),
                    "aspect": data.get("aspect_ratio", ""),
                    "title": data.get("title") or prettify_slug(folder.name),
                    "thumb": f"{folder.name}-THUMB.jpg",
                }
            )
    items.sort(key=lambda x: x["title"].lower())
    return items


def list_finalised_artworks_extended() -> List[Dict]:
    """Return detailed info for finalised artworks including locked state."""
    items: List[Dict] = []
    if FINALISED_DIR.exists():
        for folder in FINALISED_DIR.iterdir():
            if not folder.is_dir():
                continue
            listing_file = folder / f"{folder.name}-listing.json"
            if not listing_file.exists():
                continue
            try:
                with open(listing_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            items.append(
                {
                    "seo_folder": folder.name,
                    "title": data.get("title") or prettify_slug(folder.name),
                    "description": data.get("description", ""),
                    "sku": data.get("sku", ""),
                    "primary_colour": data.get("primary_colour", ""),
                    "secondary_colour": data.get("secondary_colour", ""),
                    "price": data.get("price", ""),
                    "seo_filename": data.get("seo_filename", f"{folder.name}.jpg"),
                    "tags": data.get("tags", []),
                    "materials": data.get("materials", []),
                    "aspect": data.get("aspect_ratio", ""),
                    "filename": data.get("filename", f"{folder.name}.jpg"),
                    "locked": data.get("locked", False),
                    "images": [
                        str(p)
                        for p in data.get("images", [])
                        if (BASE_DIR / p).exists()
                    ],
                }
            )
    items.sort(key=lambda x: x["title"].lower())
    return items


def find_seo_folder_from_filename(aspect: str, filename: str) -> str:
    """Return the best matching SEO folder for ``filename``.

    This searches both processed and finalised outputs and compares the given
    base name against multiple permutations found in each listing file. If
    multiple folders match, the most recently modified one is returned.
    """

    basename = Path(filename).stem.lower()
    slug_base = slugify(basename)
    candidates: list[tuple[float, str]] = []

    for base in (ARTWORK_PROCESSED_DIR, FINALISED_DIR):
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            listing_file = folder / FILENAME_TEMPLATES["listing_json"].format(seo_slug=folder.name)
            if not listing_file.exists():
                continue
            try:
                with open(listing_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            stems = {
                Path(data.get("filename", "")).stem.lower(),
                Path(data.get("seo_filename", "")).stem.lower(),
                folder.name.lower(),
                slugify(Path(data.get("filename", "")).stem),
                slugify(Path(data.get("seo_filename", "")).stem),
                slugify(folder.name),
            }

            if basename in stems or slug_base in stems:
                candidates.append((listing_file.stat().st_mtime, folder.name))

    if not candidates:
        raise FileNotFoundError(f"SEO folder not found for {filename}")

    return max(candidates, key=lambda x: x[0])[1]


def regenerate_one_mockup(seo_folder: str, slot_idx: int) -> bool:
    """Regenerate a single mockup in-place."""
    folder = ARTWORK_PROCESSED_DIR / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    if not listing_file.exists():
        folder = FINALISED_DIR / seo_folder
        listing_file = folder / f"{seo_folder}-listing.json"
        if not listing_file.exists():
            return False
    with open(listing_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    mockups = data.get("mockups", [])
    if slot_idx < 0 or slot_idx >= len(mockups):
        return False
    entry = mockups[slot_idx]
    if isinstance(entry, dict):
        category = entry.get("category")
    else:
        category = Path(entry).parent.name
    mockup_files = list((MOCKUPS_DIR / category).glob("*.png"))
    if not mockup_files:
        return False
    new_mockup = random.choice(mockup_files)
    aspect = data.get("aspect_ratio")
    coords_path = COORDS_ROOT / aspect / f"{new_mockup.stem}.json"
    art_path = folder / f"{seo_folder}.jpg"
    output_path = folder / f"{seo_folder}-{new_mockup.stem}.jpg"
    try:
        with open(coords_path, "r", encoding="utf-8") as cf:
            c = json.load(cf)["corners"]
        dst = [[c[0]["x"], c[0]["y"]], [c[1]["x"], c[1]["y"]], [c[3]["x"], c[3]["y"]], [c[2]["x"], c[2]["y"]]]
        art_img = Image.open(art_path).convert("RGBA")
        art_img = resize_image_for_long_edge(art_img)
        mock_img = Image.open(new_mockup).convert("RGBA")
        composite = apply_perspective_transform(art_img, mock_img, dst)
        composite.convert("RGB").save(output_path, "JPEG", quality=85)
        data.setdefault("mockups", [])[slot_idx] = {
            "category": category,
            "source": f"{category}/{new_mockup.name}",
            "composite": output_path.name,
        }
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logging.error("Regenerate error: %s", e)
        return False


def swap_one_mockup(seo_folder: str, slot_idx: int, new_category: str) -> bool:
    """Swap a mockup to a new category and regenerate."""
    folder = ARTWORK_PROCESSED_DIR / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    if not listing_file.exists():
        folder = FINALISED_DIR / seo_folder
        listing_file = folder / f"{seo_folder}-listing.json"
        if not listing_file.exists():
            return False
    with open(listing_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    mockups = data.get("mockups", [])
    if slot_idx < 0 or slot_idx >= len(mockups):
        return False
    mockup_files = list((MOCKUPS_DIR / new_category).glob("*.png"))
    if not mockup_files:
        return False
    new_mockup = random.choice(mockup_files)
    aspect = data.get("aspect_ratio")
    coords_path = COORDS_ROOT / aspect / f"{new_mockup.stem}.json"
    art_path = folder / f"{seo_folder}.jpg"
    output_path = folder / f"{seo_folder}-{new_mockup.stem}.jpg"
    try:
        with open(coords_path, "r", encoding="utf-8") as cf:
            c = json.load(cf)["corners"]
        dst = [[c[0]["x"], c[0]["y"]], [c[1]["x"], c[1]["y"]], [c[3]["x"], c[3]["y"]], [c[2]["x"], c[2]["y"]]]
        art_img = Image.open(art_path).convert("RGBA")
        art_img = resize_image_for_long_edge(art_img)
        mock_img = Image.open(new_mockup).convert("RGBA")
        composite = apply_perspective_transform(art_img, mock_img, dst)
        composite.convert("RGB").save(output_path, "JPEG", quality=85)
        data.setdefault("mockups", [])[slot_idx] = {
            "category": new_category,
            "source": f"{new_category}/{new_mockup.name}",
            "composite": output_path.name,
        }
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logging.error("Swap error: %s", e)
        return False


def get_menu() -> List[Dict[str, str | None]]:
    """Return navigation items for templates."""
    from flask import url_for

    menu = [
        {"name": "Home", "url": url_for("artwork.home")},
        {"name": "Artwork Gallery", "url": url_for("artwork.artworks")},
        {"name": "Finalised", "url": url_for("artwork.finalised_gallery")},
    ]
    latest = latest_analyzed_artwork()
    if latest:
        menu.append({
            "name": "Review Latest Listing",
            "url": url_for("artwork.edit_listing", aspect=latest["aspect"], filename=latest["filename"]),
        })
    else:
        menu.append({"name": "Review Latest Listing", "url": None})
    return menu


def get_allowed_colours() -> List[str]:
    """Return the list of allowed Etsy colour values."""
    return ALLOWED_COLOURS.copy()


def infer_sku_from_filename(filename: str) -> Optional[str]:
    """Infer SKU from an SEO filename using 'RJC-XXXX' at the end."""
    m = re.search(r"RJC-([A-Za-z0-9-]+)(?:\.jpg)?$", filename or "")
    return f"RJC-{m.group(1)}" if m else None


def sync_filename_with_sku(seo_filename: str, sku: str) -> str:
    """Return SEO filename updated so the SKU matches the given value."""
    if not seo_filename:
        return seo_filename
    if not sku:
        return seo_filename
    return re.sub(r"RJC-[A-Za-z0-9-]+(?=\.jpg$)", sku, seo_filename)


def is_finalised_image(path: str | Path) -> bool:
    """Return True if the given path is within the finalised-artwork folder."""
    try:
        Path(path).resolve().relative_to(FINALISED_DIR)
        return True
    except Exception:
        return False


def parse_csv_list(text: str) -> List[str]:
    """Parse a comma-separated string into a list of trimmed values."""
    import csv

    if not text:
        return []
    reader = csv.reader([text], skipinitialspace=True)
    row = next(reader, [])
    return [item.strip() for item in row if item.strip()]


def join_csv_list(items: List[str]) -> str:
    """Join a list of strings into a comma-separated string for display."""
    return ", ".join(item.strip() for item in items if item.strip())


def read_generic_text(aspect: str) -> str:
    """Return the generic text block for the given aspect ratio."""
    path = GENERIC_TEXTS_DIR / f"{aspect}.txt"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        logging.warning("Generic text for %s not found", aspect)
        return ""


def clean_terms(items: List[str]) -> Tuple[List[str], List[str]]:
    """Clean list entries by stripping invalid characters and hyphens."""
    cleaned: List[str] = []
    changed = False
    for item in items:
        new = re.sub(r"[^A-Za-z0-9 ,]", "", item)
        new = new.replace("-", "")
        new = re.sub(r"\s+", " ", new).strip()
        cleaned.append(new)
        if new != item.strip():
            changed = True
    return cleaned, cleaned if changed else []


def resolve_listing_paths(aspect: str, filename: str) -> Tuple[str, Path, Path, bool]:
    """Return the folder and listing path for an artwork.

    Searches both processed and finalised directories using
    :func:`find_seo_folder_from_filename` and returns a tuple of
    ``(seo_folder, folder_path, listing_path, finalised)``.
    Raises ``FileNotFoundError`` if nothing matches.
    """

    seo_folder = find_seo_folder_from_filename(aspect, filename)
    processed_dir = ARTWORK_PROCESSED_DIR / seo_folder
    final_dir = FINALISED_DIR / seo_folder

    listing = processed_dir / f"{seo_folder}-listing.json"
    if listing.exists():
        return seo_folder, processed_dir, listing, False

    listing = final_dir / f"{seo_folder}-listing.json"
    if listing.exists():
        return seo_folder, final_dir, listing, True

    raise FileNotFoundError(f"Listing file for {filename} not found")


def find_aspect_filename_from_seo_folder(seo_folder: str) -> Optional[Tuple[str, str]]:
    """Return the aspect ratio and main filename for a given SEO folder.

    The lookup checks both processed and finalised folders. Information is
    primarily loaded from the listing JSON, but if fields are missing the
    filename is inferred from disk contents. Filenames are normalised to use a
    ``.jpg`` extension and to match the actual casing on disk when possible.
    """

    for base in (ARTWORK_PROCESSED_DIR, FINALISED_DIR):
        folder = base / seo_folder
        listing = folder / f"{seo_folder}-listing.json"
        aspect = ""
        filename = ""

        if listing.exists():
            try:
                with open(listing, "r", encoding="utf-8") as lf:
                    data = json.load(lf)
                aspect = data.get("aspect_ratio") or data.get("aspect") or ""
                filename = (
                    data.get("seo_filename")
                    or data.get("filename")
                    or data.get("seo_name")
                    or ""
                )
                if not filename:
                    for key in ("main_jpg_path", "orig_jpg_path", "thumb_jpg_path"):
                        val = data.get(key)
                        if val:
                            filename = Path(val).name
                            break
            except Exception as e:  # noqa: BLE001
                logging.error("Failed reading listing for %s: %s", seo_folder, e)

        if folder.exists() and not filename:
            # Look for an image whose stem matches the folder name
            for p in folder.iterdir():
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"} and p.stem.lower() == seo_folder.lower():
                    filename = p.name
                    break

        if filename:
            if not filename.lower().endswith(".jpg"):
                filename = f"{Path(filename).stem}.jpg"
            # Normalise casing to match actual disk file
            disk_file = folder / filename
            if not disk_file.exists():
                stem = Path(filename).stem.lower()
                for p in folder.iterdir():
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png"} and p.stem.lower() == stem:
                        filename = p.name
                        break
            return aspect, filename

    return None


def assign_or_get_sku(
    listing_json_path: Path, tracker_path: Path, *, force: bool = False
) -> str:
    """Return existing SKU or assign the next sequential one.

    Parameters
    ----------
    listing_json_path:
        Path to the ``*-listing.json`` file.
    tracker_path:
        Path to ``sku_tracker.json`` storing ``last_sku``.
    force:
        If ``True`` always allocate a new SKU even if one exists.
    """
    listing_json_path = Path(listing_json_path)
    tracker_path = Path(tracker_path)

    logger = logging.getLogger(__name__)

    if not listing_json_path.exists():
        raise FileNotFoundError(listing_json_path)

    try:
        with open(listing_json_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Failed reading %s: %s", listing_json_path, exc)
        raise

    existing = str(data.get("sku") or "").strip()
    seo_field = str(data.get("seo_filename") or "").strip()
    if existing and not force:
        new_seo = sync_filename_with_sku(seo_field, existing)
        if new_seo != seo_field:
            data["seo_filename"] = new_seo
            try:
                with open(listing_json_path, "w", encoding="utf-8") as lf:
                    json.dump(data, lf, indent=2, ensure_ascii=False)
            except Exception as exc:  # pragma: no cover - unexpected IO
                logger.error("Failed writing SEO filename to %s: %s", listing_json_path, exc)
                raise
        return existing

    # Allocate the next SKU using the central assigner
    sku = get_next_sku(tracker_path)
    data["sku"] = sku
    if seo_field:
        data["seo_filename"] = sync_filename_with_sku(seo_field, sku)
    try:
        with open(listing_json_path, "w", encoding="utf-8") as lf:
            json.dump(data, lf, indent=2, ensure_ascii=False)
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Failed writing SKU %s to %s: %s", sku, listing_json_path, exc)
        raise

    logger.info("Assigned SKU %s to %s", sku, listing_json_path.name)
    return sku


def assign_sequential_sku(listing_json_path: Path, tracker_path: Path) -> str:
    """Backward compatible wrapper for ``assign_or_get_sku``."""
    return assign_or_get_sku(listing_json_path, tracker_path)


def validate_all_skus(listings: Iterable[Dict], tracker_path: Path) -> list[str]:
    """Return a list of SKU validation errors for the given listings."""
    tracker_last = 0
    try:
        with open(tracker_path, "r", encoding="utf-8") as tf:
            tracker_last = int(json.load(tf).get("last_sku", 0))
    except Exception:
        pass

    errors: list[str] = []
    seen: dict[int, int] = {}
    nums: list[int] = []

    for idx, data in enumerate(listings):
        sku = str(data.get("sku") or "")
        m = re.fullmatch(r"RJC-(\d{4})", sku)
        if not m:
            errors.append(f"Listing {idx}: invalid or missing SKU")
            continue
        num = int(m.group(1))
        if num in seen:
            errors.append(f"Duplicate SKU {sku} in listings {seen[num]} and {idx}")
        seen[num] = idx
        nums.append(num)

    if nums:
        nums.sort()
        for a, b in zip(nums, nums[1:]):
            if b != a + 1:
                errors.append(f"Gap or out-of-sequence SKU between {a:04d} and {b:04d}")
                break
        if nums[-1] > tracker_last:
            errors.append("Tracker last_sku behind recorded SKUs")

    return errors


```

---
## 📄 routes/admin_debug.py

```py
from __future__ import annotations

import datetime
import json

from flask import Blueprint, request, render_template, Response

import config
from routes import utils
from utils.sku_assigner import peek_next_sku
from scripts.analyze_artwork import parse_text_fallback

bp = Blueprint("admin", __name__, url_prefix="/admin")
# TODO: Protect admin debug routes with authentication/authorization


@bp.route("/debug/parse-ai", methods=["GET", "POST"])
def parse_ai():
    raw = ""
    parsed = None
    error = ""
    file_name = request.args.get("file")
    if file_name:
        path = config.PARSE_FAILURE_DIR / file_name
        if path.exists():
            raw = path.read_text(encoding="utf-8")
    if request.method == "POST":
        raw = request.form.get("raw", "")
        try:
            parsed = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            try:
                parsed = parse_text_fallback(raw)
                error = f"Input was not valid JSON: {exc}"
            except Exception as inner:  # noqa: BLE001
                error = f"Parse failed: {inner}"
                config.PARSE_FAILURE_DIR.mkdir(parents=True, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                fail_file = config.PARSE_FAILURE_DIR / f"parse_fail_{ts}.txt"
                fail_file.write_text(raw, encoding="utf-8")
    return render_template(
        "debug_parse_ai.html",
        raw=raw,
        parsed=parsed,
        error=error,
        menu=utils.get_menu(),
    )


@bp.route("/debug/next-sku")
def preview_next_sku_admin():
    return Response(peek_next_sku(config.SKU_TRACKER), mimetype="text/plain")


@bp.route("/debug/status")
def debug_status():
    info = {
        "openai_key": bool(config.OPENAI_API_KEY),
        "processed_dir": config.ARTWORKS_PROCESSED_DIR.exists(),
        "finalised_dir": config.ARTWORKS_FINALISED_DIR.exists(),
        "parse_failures": sorted(
            p.name for p in config.PARSE_FAILURE_DIR.glob("*.txt")
        ),
    }
    return render_template("debug_status.html", info=info, menu=utils.get_menu())

```

---
## 📄 routes/artwork_routes.py

```py
"""Artwork-related Flask routes.

This module powers the full listing workflow from initial review to
finalisation. It handles validation, moving files, regenerating image link
lists and serving gallery pages for processed and finalised artworks.
"""
from __future__ import annotations

import json
import subprocess
import uuid
import random
from pathlib import Path
import shutil
import os
import datetime
from config import (
    ARTWORKS_PROCESSED_DIR,
    ARTWORKS_FINALISED_DIR,
    BASE_DIR,
    ANALYSIS_STATUS_FILE,
)
import config

from PIL import Image
import io
import scripts.analyze_artwork as aa

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    Response,
)
import re

from . import utils
from .utils import (
    ALLOWED_COLOURS_LOWER,
    relative_to_base,
    FINALISED_DIR,
    parse_csv_list,
    join_csv_list,
    read_generic_text,
    clean_terms,
    infer_sku_from_filename,
    sync_filename_with_sku,
    is_finalised_image,
    get_allowed_colours,
)

bp = Blueprint("artwork", __name__)


def _write_analysis_status(step: str, percent: int, file: str | None = None) -> None:
    """Write simple progress info for frontend polling."""
    try:
        ANALYSIS_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ANALYSIS_STATUS_FILE.write_text(
            json.dumps({"step": step, "percent": percent, "file": file})
        )
    except Exception:
        pass


@bp.route("/status/analyze")
def analysis_status():
    """Return JSON progress info for the current analysis job."""
    if ANALYSIS_STATUS_FILE.exists():
        data = json.loads(ANALYSIS_STATUS_FILE.read_text())
    else:
        data = {"step": "idle", "percent": 0}
    return Response(json.dumps(data), mimetype="application/json")


def validate_listing_fields(data: dict, generic_text: str) -> list[str]:
    """Return a list of validation error messages for the listing."""
    errors: list[str] = []

    title = data.get("title", "").strip()
    if not title:
        errors.append("Title cannot be blank")
    if len(title) > 140:
        errors.append("Title exceeds 140 characters")

    tags = data.get("tags", [])
    if len(tags) > 13:
        errors.append("Too many tags (max 13)")
    seen = set()
    for t in tags:
        if not t or len(t) > 20:
            errors.append(f"Invalid tag: '{t}'")
        if "-" in t or "," in t:
            errors.append(f"Tag may not contain hyphens or commas: '{t}'")
        if not re.fullmatch(r"[A-Za-z0-9 ]+", t):
            errors.append(f"Tag has invalid characters: '{t}'")
        low = t.lower()
        if low in seen:
            errors.append(f"Duplicate tag: '{t}'")
        seen.add(low)

    materials = data.get("materials", [])
    if len(materials) > 13:
        errors.append("Too many materials (max 13)")
    seen_mats = set()
    for m in materials:
        if len(m) > 45:
            errors.append(f"Material too long: '{m}'")
        if not re.fullmatch(r"[A-Za-z0-9 ,]+", m):
            errors.append(f"Material has invalid characters: '{m}'")
        ml = m.lower()
        if ml in seen_mats:
            errors.append(f"Duplicate material: '{m}'")
        seen_mats.add(ml)

    seo_filename = data.get("seo_filename", "")
    if len(seo_filename) > 70:
        errors.append("SEO filename exceeds 70 characters")
    if " " in seo_filename or not re.fullmatch(r"[A-Za-z0-9.-]+", seo_filename):
        errors.append("SEO filename has invalid characters or spaces")
    if not re.search(r"Artwork-by-Robin-Custance-RJC-[A-Za-z0-9-]+\.jpg$", seo_filename):
        errors.append("SEO filename must end with 'Artwork-by-Robin-Custance-RJC-XXXX.jpg'")

    sku = data.get("sku", "")
    if not sku:
        errors.append("SKU is required")
    if len(sku) > 32 or not re.fullmatch(r"[A-Za-z0-9-]+", sku):
        errors.append("SKU must be <=32 chars and alphanumeric/hyphen")
    if sku and not sku.startswith("RJC-"):
        errors.append("SKU must start with 'RJC-'")
    if sku and infer_sku_from_filename(seo_filename or "") != sku:
        errors.append("SKU must match value in SEO filename")

    try:
        price = float(data.get("price"))
        if abs(price - 17.88) > 1e-2:
            errors.append("Price must be 17.88")
    except Exception:
        errors.append("Price must be a number (17.88)")

    for colour_key in ("primary_colour", "secondary_colour"):
        col = data.get(colour_key, "").strip()
        if not col:
            errors.append(f"{colour_key.replace('_', ' ').title()} is required")
            continue
        if col.lower() not in ALLOWED_COLOURS_LOWER:
            errors.append(f"{colour_key.replace('_', ' ').title()} invalid")

    images = [i.strip() for i in data.get("images", []) if str(i).strip()]
    if not images:
        errors.append("At least one image required")
    for img in images:
        if " " in img or not re.search(r"\.(jpg|jpeg|png)$", img, re.I):
            errors.append(f"Invalid image filename: '{img}'")
        if not is_finalised_image(img):
            errors.append(f"Image not in finalised-artwork folder: '{img}'")

    desc = data.get("description", "").strip()
    if len(desc.split()) < 400:
        errors.append("Description must be at least 400 words")
    GENERIC_MARKER = "About the Artist – Robin Custance"
    if generic_text:
        # Normalise whitespace for both description and generic block
        desc_norm = " ".join(desc.split()).lower()
        generic_norm = " ".join(generic_text.split()).lower()
        # Only require that the generic marker exists somewhere in the description (case-insensitive)
        if GENERIC_MARKER.lower() not in desc_norm:
            errors.append(
                f"Description must include the correct generic context block: {GENERIC_MARKER}"
            )
        if "<" in desc or ">" in desc:
            errors.append("Description may not contain HTML")

        return errors

@bp.app_context_processor
def inject_latest_artwork():
    latest = utils.latest_analyzed_artwork()
    return dict(latest_artwork=latest)


@bp.route("/")
def home():
    latest = utils.latest_analyzed_artwork()
    return render_template("index.html", menu=utils.get_menu(), latest_artwork=latest)


@bp.route("/upload", methods=["GET", "POST"])
def upload_artwork():
    """Upload new artwork files and run pre-QC then AI analysis."""
    if request.method == "POST":
        files = request.files.getlist("images")
        results = []
        for f in files:
            res = _process_upload_file(f)
            results.append(res)

        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return json.dumps(results), 200, {"Content-Type": "application/json"}

        successes = [r for r in results if r["success"]]
        if successes:
            flash(f"Uploaded {len(successes)} file(s) successfully", "success")
        failures = [r for r in results if not r["success"]]
        for f in failures:
            flash(f"{f['original']}: {f['error']}", "danger")

        if request.accept_mimetypes.accept_html:
            return redirect(url_for("artwork.artworks"))
        return json.dumps(results), 200, {"Content-Type": "application/json"}
    return render_template("upload.html", menu=utils.get_menu())


@bp.route("/artworks")
def artworks():
    processed, processed_names = utils.list_processed_artworks()
    ready = utils.list_ready_to_analyze(processed_names)
    finalised = utils.list_finalised_artworks()
    return render_template(
        "artworks.html",
        ready_artworks=ready,
        processed_artworks=processed,
        finalised_artworks=finalised,
        menu=utils.get_menu(),
    )


@bp.route("/select", methods=["GET", "POST"])
def select():
    if "slots" not in session or request.args.get("reset") == "1":
        utils.init_slots()
    slots = session["slots"]
    options = utils.compute_options(slots)
    zipped = list(zip(slots, options))
    return render_template("mockup_selector.html", zipped=zipped, menu=utils.get_menu())


@bp.route("/regenerate", methods=["POST"])
def regenerate():
    slot_idx = int(request.form["slot"])
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        cat = slots[slot_idx]["category"]
        slots[slot_idx]["image"] = utils.random_image(cat)
        session["slots"] = slots
    return redirect(url_for("artwork.select"))


@bp.route("/swap", methods=["POST"])
def swap():
    slot_idx = int(request.form["slot"])
    new_cat = request.form["new_category"]
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        slots[slot_idx]["category"] = new_cat
        slots[slot_idx]["image"] = utils.random_image(new_cat)
        session["slots"] = slots
    return redirect(url_for("artwork.select"))


@bp.route("/proceed", methods=["POST"])
def proceed():
    slots = session.get("slots", [])
    if not slots:
        flash("No mockups selected!", "danger")
        return redirect(url_for("artwork.select"))
    utils.SELECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    selection_id = str(uuid.uuid4())
    selection_file = utils.SELECTIONS_DIR / f"{selection_id}.json"
    with open(selection_file, "w") as f:
        json.dump(slots, f, indent=2)
    log_file = utils.LOGS_DIR / f"composites_{selection_id}.log"
    try:
        result = subprocess.run(
            ["python3", str(utils.GENERATE_SCRIPT_PATH), str(selection_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=utils.BASE_DIR,
        )
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode == 0:
            flash("Composites generated successfully!", "success")
        else:
            flash("Composite generation failed. See logs for details.", "danger")
    except Exception as e:
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash("Error running the composite generator.", "danger")

    latest = utils.latest_composite_folder()
    if latest:
        session["latest_seo_folder"] = latest
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    return redirect(url_for("artwork.composites_preview"))


@bp.route("/analyze/<aspect>/<filename>", methods=["POST"], endpoint="analyze_artwork")
def analyze_artwork_route(aspect, filename):
    artwork_path = utils.ARTWORKS_DIR / aspect / filename
    _write_analysis_status("starting", 0, filename)
    if not artwork_path.exists():
        try:
            fallback_folder = utils.find_seo_folder_from_filename(aspect, filename)
            for base in (utils.ARTWORK_PROCESSED_DIR, utils.FINALISED_DIR):
                candidate = base / fallback_folder / f"{fallback_folder}.jpg"
                if candidate.exists():
                    artwork_path = candidate
                    break
        except FileNotFoundError:
            pass
    log_id = str(uuid.uuid4())
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"
    try:
        cmd = ["python3", str(utils.ANALYZE_SCRIPT_PATH), str(artwork_path)]
        _write_analysis_status("openai_call", 20, filename)
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash(
                f"❌ Analysis failed for {filename}: {result.stderr}",
                "danger",
            )
            _write_analysis_status("failed", 100, filename)
    except Exception as e:
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash(f"❌ Error running analysis: {str(e)}", "danger")
        _write_analysis_status("failed", 100, filename)

    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash(
            f"Analysis complete, but no SEO folder/listing found for {filename} ({aspect}).",
            "warning",
        )
        return redirect(url_for("artwork.artworks"))

    listing_path = (
        utils.ARTWORK_PROCESSED_DIR
        / seo_folder
        / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_folder)
    )
    new_filename = f"{seo_folder}.jpg"
    try:
        with open(listing_path, "r", encoding="utf-8") as lf:
            listing_data = json.load(lf)
            new_filename = listing_data.get("seo_filename", new_filename)
    except Exception:
        pass

    try:
        cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
        _write_analysis_status("generating", 60, filename)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=utils.BASE_DIR, timeout=600)
        composite_log_file = utils.LOGS_DIR / f"composite_gen_{log_id}.log"
        with open(composite_log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash("Artwork analyzed, but mockup generation failed. See logs.", "danger")
    except Exception as e:
        flash(f"Composites generation error: {e}", "danger")
    
    _write_analysis_status("done", 100, filename)
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=new_filename))


@bp.post("/analyze-upload/<base>")
def analyze_upload(base):
    """Analyze an uploaded image from the temporary folder."""
    qc_path = config.UPLOADS_TEMP_DIR / f"{base}.qc.json"
    if not qc_path.exists():
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    try:
        with open(qc_path, "r", encoding="utf-8") as f:
            qc = json.load(f)
    except Exception:
        flash("Invalid QC data", "danger")
        return redirect(url_for("artwork.artworks"))

    ext = qc.get("extension", "jpg")
    orig_path = config.UPLOADS_TEMP_DIR / f"{base}.{ext}"
    processed_root = ARTWORKS_PROCESSED_DIR
    log_id = uuid.uuid4().hex
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"
    _write_analysis_status("starting", 0, orig_path.name)
    try:
        cmd = ["python3", str(utils.ANALYZE_SCRIPT_PATH), str(orig_path)]
        _write_analysis_status("openai_call", 20, orig_path.name)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash(f"❌ Analysis failed: {result.stderr}", "danger")
            _write_analysis_status("failed", 100, orig_path.name)
            return redirect(url_for("artwork.artworks"))
    except Exception as e:  # noqa: BLE001
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash(f"❌ Error running analysis: {e}", "danger")
        _write_analysis_status("failed", 100, orig_path.name)
        return redirect(url_for("artwork.artworks"))

    try:
        seo_folder = utils.find_seo_folder_from_filename(qc.get("aspect_ratio", ""), orig_path.name)
    except FileNotFoundError:
        flash(
            f"Analysis complete, but no SEO folder/listing found for {orig_path.name} ({qc.get('aspect_ratio','')}).",
            "warning",
        )
        return redirect(url_for("artwork.artworks"))

    listing_data = None
    listing_path = (
        utils.ARTWORK_PROCESSED_DIR
        / seo_folder
        / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_folder)
    )
    if listing_path.exists():
        try:
            with open(listing_path, "r", encoding="utf-8") as lf:
                listing_data = json.load(lf)
        except Exception:
            listing_data = None

    for suffix in [f".{ext}", "-thumb.jpg", "-analyse.jpg", ".qc.json"]:
        temp_file = config.UPLOADS_TEMP_DIR / f"{base}{suffix}"
        if not temp_file.exists():
            continue
        template_key = (
            "analyse" if suffix == "-analyse.jpg" else "thumbnail" if suffix == "-thumb.jpg" else "qc_json" if suffix.endswith(".qc.json") else "artwork"
        )
        dest = processed_root / seo_folder / config.FILENAME_TEMPLATES.get(template_key).format(seo_slug=seo_folder)
        if suffix == "-analyse.jpg" and dest.exists():
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            dest = dest.with_name(f"{dest.stem}-{ts}{dest.suffix}")
        shutil.move(str(temp_file), dest)

    try:
        cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
        _write_analysis_status("generating", 60, orig_path.name)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=utils.BASE_DIR, timeout=600)
        composite_log = utils.LOGS_DIR / f"composite_gen_{log_id}.log"
        with open(composite_log, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash("Artwork analyzed, but mockup generation failed.", "danger")
    except Exception as e:  # noqa: BLE001
        flash(f"Composites generation error: {e}", "danger")

    aspect = listing_data.get("aspect_ratio", qc.get("aspect_ratio", "")) if listing_data else qc.get("aspect_ratio", "")
    new_filename = f"{seo_folder}.jpg"
    if listing_data:
        new_filename = listing_data.get("seo_filename", new_filename)
    _write_analysis_status("done", 100, orig_path.name)
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=new_filename))


@bp.route("/review/<aspect>/<filename>")
def review_artwork(aspect, filename):
    """Legacy URL – redirect to the new edit/review page."""
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/review/<aspect>/<filename>/regenerate/<int:slot_idx>", methods=["POST"])
def review_regenerate_mockup(aspect, filename, slot_idx):
    seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    utils.regenerate_one_mockup(seo_folder, slot_idx)
    return redirect(url_for("artwork.finalised_gallery"))

@bp.route("/review/<seo_folder>/swap/<int:slot_idx>", methods=["POST"])
def review_swap_mockup(seo_folder, slot_idx):
    new_cat = request.form["new_category"]
    if not utils.swap_one_mockup(seo_folder, slot_idx, new_cat):
        flash("Failed to swap mockup", "danger")

    info = utils.find_aspect_filename_from_seo_folder(seo_folder)
    if info:
        aspect, filename = info
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))

    flash(
        "Could not locate the correct artwork for editing after swap. Please check the gallery.",
        "warning",
    )
    return redirect(url_for("artwork.finalised_gallery"))

@bp.route("/edit-listing/<aspect>/<filename>", methods=["GET", "POST"])
def edit_listing(aspect, filename):
    """Display and update a processed or finalised artwork listing."""

    try:
        seo_folder, folder, listing_path, finalised = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))

    try:
        with open(listing_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        flash(f"Error loading listing: {e}", "danger")
        return redirect(url_for("artwork.artworks"))

    generic_text = read_generic_text(aspect)
    if generic_text:
        data["generic_text"] = generic_text

    openai_info = data.get("openai_analysis")

    if request.method == "POST":
        action = request.form.get("action", "save")

        seo_field = request.form.get("seo_filename", data.get("seo_filename", f"{seo_folder}.jpg")).strip()
        # SKU comes exclusively from the listing JSON; users cannot edit it
        sku_val = str(data.get("sku", "")).strip()
        inferred = infer_sku_from_filename(seo_field) or ""
        if sku_val and inferred and sku_val != inferred:
            sku_val = inferred
            flash("SKU updated to match SEO filename", "info")
        elif not sku_val:
            sku_val = inferred
        seo_val = sync_filename_with_sku(seo_field, sku_val)

        form_data = {
            "title": request.form.get("title", data.get("title", "")).strip(),
            "description": request.form.get("description", data.get("description", "")).strip(),
            "tags": parse_csv_list(request.form.get("tags", "")),
            "materials": parse_csv_list(request.form.get("materials", "")),
            "primary_colour": request.form.get("primary_colour", data.get("primary_colour", "")).strip(),
            "secondary_colour": request.form.get("secondary_colour", data.get("secondary_colour", "")).strip(),
            "seo_filename": seo_val,
            "price": request.form.get("price", data.get("price", "17.88")).strip(),
            "sku": sku_val,
            "images": [i.strip() for i in request.form.get("images", "").splitlines() if i.strip()],
        }

        form_data["tags"], cleaned_tags = clean_terms(form_data["tags"])
        form_data["materials"], cleaned_mats = clean_terms(form_data["materials"])
        if cleaned_tags:
            flash(f"Cleaned tags: {join_csv_list(form_data['tags'])}", "success")
        if cleaned_mats:
            flash(f"Cleaned materials: {join_csv_list(form_data['materials'])}", "success")

        if action == "delete":
            shutil.rmtree(utils.ARTWORK_PROCESSED_DIR / seo_folder, ignore_errors=True)
            shutil.rmtree(utils.FINALISED_DIR / seo_folder, ignore_errors=True)
            try:
                os.remove(utils.ARTWORKS_DIR / aspect / filename)
            except Exception:
                pass
            flash("Artwork deleted", "success")
            return redirect(url_for("artwork.artworks"))

        folder.mkdir(parents=True, exist_ok=True)
        img_files = [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        form_data["images"] = [relative_to_base(p) for p in sorted(img_files)]

        errors = validate_listing_fields(form_data, generic_text)
        if errors:
            form_data["images"] = "\n".join(form_data.get("images", []))
            form_data["tags"] = join_csv_list(form_data.get("tags", []))
            form_data["materials"] = join_csv_list(form_data.get("materials", []))
            mockups = []
            for idx, mp in enumerate(data.get("mockups", [])):
                if isinstance(mp, dict):
                    out = folder / mp.get("composite", "")
                    cat = mp.get("category", "")
                else:
                    p = Path(mp)
                    out = folder / f"{seo_folder}-{p.stem}.jpg"
                    cat = p.parent.name
                mockups.append({"path": out, "category": cat, "exists": out.exists(), "index": idx})
            return render_template(
                "edit_listing.html",
                artwork=form_data,
                errors=errors,
                aspect=aspect,
                filename=filename,
                seo_folder=seo_folder,
                mockups=mockups,
                menu=utils.get_menu(),
                colour_options=get_allowed_colours(),
                categories=utils.get_categories(),
                finalised=finalised,
                locked=data.get("locked", False),
                editable=not data.get("locked", False),
                openai_analysis=openai_info,
                generic_text=generic_text,
            )

        data.update(form_data)
        data["generic_text"] = generic_text

        full_desc = re.sub(r"\s+$", "", form_data["description"])
        gen = generic_text.strip()
        if gen and not full_desc.endswith(gen):
            full_desc = re.sub(r"\n{3,}", "\n\n", full_desc.rstrip()) + "\n\n" + gen
        data["description"] = full_desc.strip()

        with open(listing_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        flash("Listing updated", "success")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))

    raw_ai = data.get("ai_listing")
    ai = {}
    fallback_ai: dict = {}

    def parse_fallback(text: str) -> dict:
        match = re.search(r"```json\s*({.*?})\s*```", text, re.DOTALL)
        if not match:
            match = re.search(r"({.*})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                return {}
        return {}

    if isinstance(raw_ai, dict):
        ai = raw_ai
        if isinstance(raw_ai.get("fallback_text"), str):
            fallback_ai.update(parse_fallback(raw_ai.get("fallback_text")))
    elif isinstance(raw_ai, str):
        try:
            ai = json.loads(raw_ai)
        except Exception:
            fallback_ai.update(parse_fallback(raw_ai))

    if isinstance(data.get("fallback_text"), str):
        fallback_ai.update(parse_fallback(data["fallback_text"]))

    price = data.get("price") or ai.get("price") or fallback_ai.get("price") or "17.88"
    sku = (
        data.get("sku")
        or ai.get("sku")
        or fallback_ai.get("sku")
        or infer_sku_from_filename(data.get("seo_filename", ""))
        or ""
    )
    primary = data.get("primary_colour") or ai.get("primary_colour") or fallback_ai.get("primary_colour", "")
    secondary = data.get("secondary_colour") or ai.get("secondary_colour") or fallback_ai.get("secondary_colour", "")

    images = data.get("images")
    if not images:
        imgs = [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        images = [relative_to_base(p) for p in sorted(imgs)]
    else:
        images = [relative_to_base(Path(p)) for p in images]

    artwork = {
        "title": data.get("title") or ai.get("title") or fallback_ai.get("title", ""),
        "description": data.get("description") or ai.get("description") or fallback_ai.get("description", ""),
        "tags": join_csv_list(data.get("tags") or ai.get("tags") or fallback_ai.get("tags", [])),
        "materials": join_csv_list(data.get("materials") or ai.get("materials") or fallback_ai.get("materials", [])),
        "primary_colour": primary,
        "secondary_colour": secondary,
        "seo_filename": data.get("seo_filename") or ai.get("seo_filename") or fallback_ai.get("seo_filename") or f"{seo_folder}.jpg",
        "price": price,
        "sku": sku,
        "images": "\n".join(images),
    }

    if not artwork.get("title"):
        artwork["title"] = seo_folder.replace("-", " ").title()
    if not artwork.get("description"):
        artwork["description"] = "(No description found. Try re-analyzing or check AI output.)"

    artwork["full_listing_text"] = utils.build_full_listing_text(
        artwork.get("description", ""), data.get("generic_text", "")
    )

    mockups = []
    for idx, mp in enumerate(data.get("mockups", [])):
        if isinstance(mp, dict):
            out = folder / mp.get("composite", "")
            cat = mp.get("category", "")
        else:
            p = Path(mp)
            out = folder / f"{seo_folder}-{p.stem}.jpg"
            cat = p.parent.name
        mockups.append({"path": out, "category": cat, "exists": out.exists(), "index": idx})
    return render_template(
        "edit_listing.html",
        artwork=artwork,
        aspect=aspect,
        filename=filename,
        seo_folder=seo_folder,
        mockups=mockups,
        menu=utils.get_menu(),
        errors=None,
        colour_options=get_allowed_colours(),
        categories=utils.get_categories(),
        finalised=finalised,
        locked=data.get("locked", False),
        editable=not data.get("locked", False),
        openai_analysis=openai_info,
        generic_text=data.get("generic_text", ""),
    )


_PROCESSED_REL = ARTWORKS_PROCESSED_DIR.relative_to(BASE_DIR).as_posix()
_FINALISED_REL = ARTWORKS_FINALISED_DIR.relative_to(BASE_DIR).as_posix()


@bp.route(f"/static/{_PROCESSED_REL}/<seo_folder>/<filename>")
def processed_image(seo_folder, filename):
    """Serve artwork images from processed or finalised folders."""
    final_folder = utils.FINALISED_DIR / seo_folder
    if (final_folder / filename).exists():
        folder = final_folder
    else:
        folder = utils.ARTWORK_PROCESSED_DIR / seo_folder
    return send_from_directory(folder, filename)


@bp.route(f"/static/{_FINALISED_REL}/<seo_folder>/<filename>")
def finalised_image(seo_folder, filename):
    """Serve images strictly from the finalised-artwork folder."""
    folder = utils.FINALISED_DIR / seo_folder
    return send_from_directory(folder, filename)


@bp.route("/artwork-img/<aspect>/<filename>")
def artwork_image(aspect, filename):
    folder = utils.ARTWORKS_DIR / aspect
    candidate = folder / filename
    if candidate.exists():
        return send_from_directory(str(folder.resolve()), filename)
    alt_folder = utils.ARTWORKS_DIR / f"{aspect}-artworks" / Path(filename).stem
    candidate = alt_folder / filename
    if candidate.exists():
        return send_from_directory(str(alt_folder.resolve()), filename)
    return "", 404


@bp.route("/temp-img/<filename>")
def temp_image(filename):
    """Serve images from the temporary upload directory."""
    return send_from_directory(config.UPLOADS_TEMP_DIR, filename)


@bp.route("/mockup-img/<category>/<filename>")
def mockup_img(category, filename):
    return send_from_directory(utils.MOCKUPS_DIR / category, filename)


@bp.route("/composite-img/<folder>/<filename>")
def composite_img(folder, filename):
    return send_from_directory(utils.COMPOSITES_DIR / folder, filename)


@bp.route("/composites")
def composites_preview():
    latest = utils.latest_composite_folder()
    if latest:
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    flash("No composites found", "warning")
    return redirect(url_for("artwork.artworks"))


@bp.route("/composites/<seo_folder>")
def composites_specific(seo_folder):
    folder = utils.ARTWORK_PROCESSED_DIR / seo_folder
    json_path = folder / f"{seo_folder}-listing.json"
    images = []
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as jf:
            listing = json.load(jf)
        for idx, mp in enumerate(listing.get("mockups", [])):
            if isinstance(mp, dict):
                out = folder / mp.get("composite", "")
                cat = mp.get("category", "")
            else:
                p = Path(mp)
                out = folder / f"{seo_folder}-{p.stem}.jpg"
                cat = p.parent.name
            images.append({"filename": out.name, "category": cat, "index": idx, "exists": out.exists()})
    else:
        for idx, img in enumerate(sorted(folder.glob(f"{seo_folder}-mockup-*.jpg"))):
            images.append({"filename": img.name, "category": None, "index": idx, "exists": True})
    return render_template("composites_preview.html", images=images, folder=seo_folder, menu=utils.get_menu())


@bp.route("/composites/<seo_folder>/regenerate/<int:slot_index>", methods=["POST"])
def regenerate_composite(seo_folder, slot_index):
    utils.regenerate_one_mockup(seo_folder, slot_index)
    return redirect(url_for("artwork.composites_specific", seo_folder=seo_folder))


@bp.route("/approve_composites/<seo_folder>", methods=["POST"])
def approve_composites(seo_folder):
    flash("Composites approved", "success")
    return redirect(url_for("artwork.composites_specific", seo_folder=seo_folder))


@bp.route("/finalise/<aspect>/<filename>", methods=["GET", "POST"])
def finalise_artwork(aspect, filename):
    """Move processed artwork to finalised location and update listing data."""
    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))

    processed_dir = utils.ARTWORK_PROCESSED_DIR / seo_folder
    final_dir = utils.FINALISED_DIR / seo_folder
    log_path = utils.LOGS_DIR / "finalise.log"

    # ------------------------------------------------------------------
    # Move processed artwork into the finalised location and update paths
    # ------------------------------------------------------------------
    try:
        if final_dir.exists():
            raise FileExistsError(f"{final_dir} already exists")

        shutil.move(str(processed_dir), str(final_dir))

        # Marker file indicating finalisation time
        (final_dir / "finalised.txt").write_text(
            datetime.datetime.now().isoformat(), encoding="utf-8"
        )

        # Remove original artwork from input directory if it still exists
        orig_input = utils.ARTWORKS_DIR / aspect / filename
        try:
            os.remove(orig_input)
        except FileNotFoundError:
            pass

        # Update any stored paths within the listing JSON
        listing_file = final_dir / f"{seo_folder}-listing.json"
        if listing_file.exists():
            # Always allocate a fresh SKU on finalisation
            utils.assign_or_get_sku(listing_file, config.SKU_TRACKER, force=True)
            with open(listing_file, "r", encoding="utf-8") as lf:
                listing_data = json.load(lf)
            listing_data.setdefault("locked", False)

            def _swap_path(p: str) -> str:
                return p.replace(
                    str(utils.ARTWORK_PROCESSED_DIR), str(utils.FINALISED_DIR)
                )

            for key in ("main_jpg_path", "orig_jpg_path", "thumb_jpg_path", "processed_folder"):
                if isinstance(listing_data.get(key), str):
                    listing_data[key] = _swap_path(listing_data[key])

            if isinstance(listing_data.get("images"), list):
                listing_data["images"] = [
                    _swap_path(img) if isinstance(img, str) else img
                    for img in listing_data["images"]
                ]

            imgs = [p for p in final_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
            listing_data["images"] = [utils.relative_to_base(p) for p in sorted(imgs)]

            with open(listing_file, "w", encoding="utf-8") as lf:
                json.dump(listing_data, lf, indent=2, ensure_ascii=False)

        with open(log_path, "a", encoding="utf-8") as log:
            user = session.get("user", "anonymous")
            log.write(f"{datetime.datetime.now().isoformat()} - {seo_folder} by {user}\n")

        flash("Artwork finalised", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Failed to finalise artwork: {e}", "danger")

    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/finalised")
def finalised_gallery():
    """Display all finalised artworks in a gallery view."""
    artworks = []
    if utils.FINALISED_DIR.exists():
        for folder in utils.FINALISED_DIR.iterdir():
            if not folder.is_dir():
                continue
            listing_file = folder / f"{folder.name}-listing.json"
            if not listing_file.exists():
                continue
            try:
                with open(listing_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            entry = {
                "seo_folder": folder.name,
                "title": data.get("title") or utils.prettify_slug(folder.name),
                "description": data.get("description", ""),
                "sku": data.get("sku", ""),
                "primary_colour": data.get("primary_colour", ""),
                "secondary_colour": data.get("secondary_colour", ""),
                "price": data.get("price", ""),
                "seo_filename": data.get("seo_filename", f"{folder.name}.jpg"),
                "tags": data.get("tags", []),
                "materials": data.get("materials", []),
                "aspect": data.get("aspect_ratio", ""),
                "filename": data.get("filename", f"{folder.name}.jpg"),
                "locked": data.get("locked", False),
                "mockups": [],
            }

            for mp in data.get("mockups", []):
                if isinstance(mp, dict):
                    out = folder / mp.get("composite", "")
                else:
                    p = Path(mp)
                    out = folder / f"{folder.name}-{p.stem}.jpg"
                if out.exists():
                    entry["mockups"].append({"filename": out.name})

            # Filter images that actually exist on disk
            images = []
            for img in data.get("images", []):
                img_path = utils.BASE_DIR / img
                if img_path.exists():
                    images.append(img)
            entry["images"] = images

            ts = folder / "finalised.txt"
            entry["date"] = ts.stat().st_mtime if ts.exists() else listing_file.stat().st_mtime

            main_img = folder / f"{folder.name}.jpg"
            entry["main_image"] = main_img.name if main_img.exists() else None

            artworks.append(entry)
    artworks.sort(key=lambda x: x.get("date", 0), reverse=True)
    return render_template("finalised.html", artworks=artworks, menu=utils.get_menu())


@bp.route("/locked")
def locked_gallery():
    """Show gallery of locked artworks only."""
    locked_items = [a for a in utils.list_finalised_artworks_extended() if a.get("locked")]
    return render_template("locked.html", artworks=locked_items, menu=utils.get_menu())


@bp.post("/update-links/<aspect>/<filename>")
def update_links(aspect, filename):
    """Regenerate image URL list from disk for either processed or finalised artwork.

    If the request was sent via AJAX (accepting JSON or using the ``XMLHttpRequest``
    header) the refreshed list of image URLs is returned as JSON rather than
    performing a redirect. This allows the edit page to update the textarea in
    place without losing form state.
    """

    wants_json = "application/json" in request.headers.get("Accept", "") or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    try:
        seo_folder, folder, listing_file, _ = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        msg = "Artwork not found"
        if wants_json:
            return {"success": False, "message": msg, "images": []}, 404
        flash(msg, "danger")
        return redirect(url_for("artwork.artworks"))

    try:
        with open(listing_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        imgs = [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        data["images"] = [utils.relative_to_base(p) for p in sorted(imgs)]
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        msg = "Image links updated"
        if wants_json:
            return {"success": True, "message": msg, "images": data["images"]}
        flash(msg, "success")
    except Exception as e:  # noqa: BLE001
        msg = f"Failed to update links: {e}"
        if wants_json:
            return {"success": False, "message": msg, "images": []}, 500
        flash(msg, "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/finalise/delete/<aspect>/<filename>")
def delete_finalised(aspect, filename):
    """Delete a finalised artwork folder."""
    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.finalised_gallery"))
    folder = utils.FINALISED_DIR / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    locked = False
    if listing_file.exists():
        try:
            with open(listing_file, "r", encoding="utf-8") as f:
                info = json.load(f)
            locked = info.get("locked", False)
        except Exception:
            pass
    if locked and request.form.get("confirm") != "DELETE":
        flash("Type DELETE to confirm", "warning")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))
    try:
        shutil.rmtree(folder)
        flash("Finalised artwork deleted", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Delete failed: {e}", "danger")
    return redirect(url_for("artwork.finalised_gallery"))


@bp.post("/lock/<aspect>/<filename>")
def lock_listing(aspect, filename):
    """Mark a finalised artwork as locked."""
    try:
        seo, folder, listing, finalised = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    if not finalised:
        flash("Artwork must be finalised before locking", "danger")
        return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))
    try:
        with open(listing, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["locked"] = True
        with open(listing, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        flash("Artwork locked", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Failed to lock: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/unlock/<aspect>/<filename>")
def unlock_listing(aspect, filename):
    """Unlock a previously locked artwork."""
    try:
        seo, folder, listing, _ = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    try:
        with open(listing, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["locked"] = False
        with open(listing, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        flash("Artwork unlocked", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Failed to unlock: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/reset-sku/<aspect>/<filename>")
def reset_sku(aspect, filename):
    """Force reassign a new SKU for the given artwork."""
    try:
        seo, folder, listing, _ = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    try:
        utils.assign_or_get_sku(listing, config.SKU_TRACKER, force=True)
        flash("SKU reset", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Failed to reset SKU: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/finalise/push-sellbrite/<aspect>/<filename>")
def push_sellbrite_placeholder(aspect, filename):
    """Placeholder endpoint for future Sellbrite integration."""
    flash("Coming soon!", "info")
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/logs/openai")
@bp.route("/logs/openai/<date>")
def view_openai_logs(date: str | None = None):
    """Return the tail of the most recent OpenAI analysis log."""
    logs = sorted(
        config.LOGS_DIR.glob("analyze-openai-calls-*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not logs:
        return Response("No logs found", mimetype="text/plain")

    target = None
    if date:
        cand = config.LOGS_DIR / f"analyze-openai-calls-{date}.log"
        if cand.exists():
            target = cand
    if not target:
        target = logs[0]

    text = target.read_text(encoding="utf-8")
    lines = text.strip().splitlines()[-50:]
    return Response("\n".join(lines), mimetype="text/plain")


@bp.route("/next-sku")
def preview_next_sku():
    """Return the next SKU without reserving it."""
    next_sku = peek_next_sku(config.SKU_TRACKER)
    return Response(next_sku, mimetype="text/plain")


def _process_upload_file(file_storage):
    """Handle single uploaded file through QC, AI and relocation."""
    result = {"original": file_storage.filename, "success": False, "error": ""}
    filename = file_storage.filename
    if not filename:
        result["error"] = "No filename"
        return result
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_EXTENSIONS:
        result["error"] = "Invalid file type"
        return result
    data = file_storage.read()
    if len(data) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        result["error"] = "File too large"
        return result
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except Exception:
        result["error"] = "Corrupted image"
        return result

    safe = aa.slugify(Path(filename).stem)
    unique = uuid.uuid4().hex[:8]
    base = f"{safe}-{unique}"
    config.UPLOADS_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    orig_path = config.UPLOADS_TEMP_DIR / f"{base}.{ext}"
    with open(orig_path, "wb") as f:
        f.write(data)

    with Image.open(orig_path) as img:
        width, height = img.size
        thumb_path = config.UPLOADS_TEMP_DIR / f"{base}-thumb.jpg"
        thumb = img.copy()
        thumb.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
        thumb.save(thumb_path, "JPEG", quality=80)

    analyse_path = config.UPLOADS_TEMP_DIR / f"{base}-analyse.jpg"
    with Image.open(orig_path) as img:
        w, h = img.size
        scale = config.ANALYSE_MAX_DIM / max(w, h)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        img = img.convert("RGB")

        q = 85
        while True:
            img.save(analyse_path, "JPEG", quality=q, optimize=True)
            if analyse_path.stat().st_size <= config.ANALYSE_MAX_MB * 1024 * 1024 or q <= 60:
                break
            q -= 5

    aspect = aa.get_aspect_ratio(orig_path)

    qc_data = {
        "original_filename": filename,
        "extension": ext,
        "image_shape": [width, height],
        "filesize_bytes": len(data),
        "aspect_ratio": aspect,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    qc_path = config.UPLOADS_TEMP_DIR / f"{base}.qc.json"
    qc_path.write_text(json.dumps(qc_data, indent=2))

    result.update({"success": True, "base": base, "aspect": aspect})
    return result


```

---
## 📄 static/css/style.css

```css
/* ==============================
   CapitalArt Mockup Selector & Approval UI
   Full Style Sheet — Robbie Mode™
   ============================== */

/* --------- [ 0. Global Styles & Variables ] --------- */
:root {
  --main-bg: #f9f9f9;
  --main-txt: #222;
  --accent: #000000;
  --accent-dark: #414141;
  --border: #ddd;
  --card-bg: #fff;
  --shadow: 0 2px 6px rgba(0,0,0,0.06);
  --radius: 0px;
  --thumb-radius: 0px;
  --menu-height: 64px;
  --gallery-gap: 2em;
}

body {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  background: var(--main-bg);
  color: var(--main-txt);
  margin: 0;
  padding: 0;
  min-height: 100vh;
}

/* --------- [ 1. Header/Menu/Nav ] --------- */
header, nav, .main-nav {
  background: var(--accent);
  color: #fff;
  height: var(--menu-height);
  display: flex;
  align-items: center;
  padding: 0 2em;
  font-size: 1.08em;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  gap: 1.7em;
}
nav a, .main-nav a {
  color: #fff;
  text-decoration: none;
  margin-right: 2em;
  font-weight: 500;
  letter-spacing: 0.01em;
  transition: color 0.2s;
}
nav a:hover,
nav a.active,
.main-nav a:hover { color: #ffe873; }

.logo {
  font-size: 1.22em;
  font-weight: bold;
  margin-right: 2.5em;
  letter-spacing: 0.04em;
}

/* --------- [ 2. Main Layout ] --------- */
main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2.5em 1em 2em 1em;
}
@media (max-width: 700px) {
  main { padding: 1.1em 0.4em; }
}

/* === [RA.1] Review Artwork Grid Layout === */
.review-artwork-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 38px;
  justify-content: center;
  align-items: flex-start;
  max-width: 1400px;
  margin: 2.5em auto;
}
.mockup-col {
  flex: 1 1 0;
  min-width: 340px;
  max-width: 540px;
  display: block;
}
.main-thumb {
  text-align: center;
  margin-bottom: 1.5em;
}
.main-thumbnail-img {
  max-width: 300px;
  border-radius: 0px;
  box-shadow: 0 2px 12px #0002;
  cursor: pointer;
}
.thumb-note {
  font-size: 0.96em;
  color: #888;
  margin-top: 0.4em;
}

h3, .mockup-previews-title {
  margin: 0 0 18px 0;
  font-weight: 700;
  font-size: 1.23em;
}
.mockup-preview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
.mockup-card {
  background: #fff;
  border-radius: 0px;
  box-shadow: 0 2px 10px #0001;
  padding: 11px 7px;
  text-align: center;
}
.mockup-thumb-img {
  width: 100%;
  border-radius: 0px;
  margin-bottom: 6px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.09);
  background: #eee;
  cursor: pointer;
  transition: box-shadow 0.15s;
}
.mockup-thumb-img:focus { outline: 2.5px solid var(--accent); }
.mockup-number { font-size: 0.96em; margin-bottom: 6px; }
form { margin: 0.3em 0; display: inline; }
select {
  margin: 2px 0 0 0px;
  border-radius: 0px;
  padding: 2px 8px;
  font-size: 0.97em;
}
.btn, .btn-sm {
  padding: 4px 12px;
  border-radius: 0px;
  font-size: 1em;
  background: #f7f7f7;
  border: 1px solid #bbb;
  cursor: pointer;
  transition: background 0.18s, border 0.18s;
}
.btn-primary {
  background: var(--accent);
  color: #fff;
  border: none;
}

.btn-primary:hover,
.btn:hover { background: #d1f8da; }
.btn-primary:hover { background: var(--accent-dark); color: #ffe873; }
.btn-danger:hover { background: var(--accent-dark); color: #ff6868; }

/* === [CA.ARTY-BUTTONS] CapitalArt Black Button Style === */
.btn-black {
  background: #000 !important;
  color: #fff !important;
  border: none !important;
  border-radius: 0 !important;
  font-weight: bold;
  font-size: 1.06em;
  letter-spacing: 0.01em;
  padding: 0.8em 1.6em;
  display: inline-block;
  cursor: pointer;
  transition: background 0.16s, color 0.16s;
  margin: 0.2em 0;
  box-shadow: 0 1px 6px rgba(0,0,0,0.07);
  text-align: center;
  text-decoration: none;
}
.btn-black:hover, .btn-black:focus {
  background: #222 !important;
  color: #ffe873 !important;
  text-decoration: none;
}

.btn-black.btn-disabled, .btn-black[disabled] {
  pointer-events: none;
  opacity: 0.45;
  filter: grayscale(0.3);
}

.desc-col {
  flex: 1 1 0;
  min-width: 340px;
  max-width: 600px;
  display: block;
}
h1 { font-size: 2em; line-height: 1.3; text-align: center; margin-bottom: 0.9em; }
.desc-panel {
  margin-bottom: 1.7em;
  background: #fafbfc;
  border-radius: 0px;
  box-shadow: 0 1px 4px #0001;
  padding: 16px;
  overflow-x: auto;
}
.desc-panel h2 { margin-bottom: 10px; font-size: 1.13em; }
.desc-text {
  white-space: pre-wrap;
  background: #fafbfc;
  border-radius: 0px;
  box-shadow: 0 1px 4px #0001;
  padding: 16px;
  min-height: 110px;
  max-height: 350px;
  overflow-y: auto;
  font-size: 1.05em;
}
.desc-panel pre {
  white-space: pre-wrap;
  background: #fafbfc;
  border-radius: 0px;
  box-shadow: 0 1px 4px #0001;
  padding: 16px;
  min-height: 110px;
  max-height: 350px;
  overflow-y: auto;
  font-size: 1.05em;
}
.artist-bio {
  background: #fafbfc;
  border-radius: 0px;
  box-shadow: 0 1px 4px #0001;
  padding: 16px;
  white-space: pre-line;
  font-size: 1.05em;
  margin-bottom: 2em;
}
.colour-info-grid {
  display: flex;
  gap: 22px;
  justify-content: center;
  margin-bottom: 2.2em;
}
.colour-info-grid .label {
  font-weight: 600;
  font-size: 1.02em;
  margin-bottom: 5px;
}
.colour-box {
  background: #fcfcfc;
  border-radius: 0px;
  border: 1px solid #e2e4e8;
  min-height: 38px;
  padding: 7px 12px;
  font-size: 0.97em;
  white-space: pre-line;
  overflow-x: auto;
}
.reanalyse-label {
  margin-bottom: 10px;
  font-size: 1.07em;
  font-weight: 500;
}
textarea {
  width: 100%;
  max-width: 400px;
  padding: 10px;
  border-radius: 0px;
  border: 1px solid #ccd2da;
  resize: vertical;
  font-size: 1em;
  margin-bottom: 9px;
}
.back-link {
  text-align: center;
  margin-top: 1.4em;
}
.back-link a {
  font-size: 1em;
  color: #6c38b1;
  padding: 7px 18px;
  text-decoration: underline;
}
.card-img-top {
  max-width: 100%;
  max-height: 300px;
  object-fit: cover;
  object-position: center;
}

/* --------- [ 6. Modal/Fullscreen Image View — Borderless Edition ] --------- */
.modal-bg {
  display: none;
  position: fixed; z-index: 99;
  left: 0; top: 0; width: 100vw; height: 100vh;
  background: rgba(34,34,34,0.68);
  align-items: center; justify-content: center;
}
.modal-bg.active { display: flex !important; }

.modal-img {
  background: transparent !important;
  border-radius: 0 !important;
  padding: 0 !important;
  max-width: 94vw;
  max-height: 93vh;
  box-shadow: 0 5px 26px rgba(0,0,0,0.22);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-img img {
  max-width: 88vw;
  max-height: 80vh;
  border-radius: 0 !important;
  border: none !important;
  background: none !important;
  display: block;
  box-shadow: none !important;
}

.modal-close {
  position: absolute;
  top: 2.3vh;
  right: 2.6vw;
  font-size: 2em;
  color: #fff;
  background: none;
  border: none;
  cursor: pointer;
  z-index: 101;
  text-shadow: 0 2px 6px #000;
}
.modal-close:focus { outline: 2px solid #ffe873; }

/* --------- [ 7. Footer ] --------- */
footer, .gallery-footer {
  text-align: center;
  margin-top: 4em;
  padding: 1.2em 0;
  font-size: 1em;
  color: #777;
  background: #f2f2f2;
  border-top: 1px solid #ececec;
  letter-spacing: 0.01em;
}
footer a { color: var(--accent); text-decoration: underline; }
footer a:hover { color: var(--accent-dark); }

/* --------- [ 8. Light/Dark Mode Ready ] --------- */
body.dark, .dark main {
  background: #191e23 !important;
  color: #f1f1f1 !important;
}
body.dark header, body.dark nav {
  background: #14171a;
  color: #eee;
}
body.dark .item, body.dark .gallery-item,
body.dark .desc-panel, body.dark .modal-img {
  background: #252b30;
  color: #eaeaea;
  border-color: #444;
}
body.dark .desc-panel { box-shadow: 0 3px 10px rgba(0,0,0,0.33); }
body.dark .gallery-footer, body.dark footer {
  background: #1a1a1a;
  color: #bbb;
  border-top: 1px solid #252b30;
}

:focus-visible {
  outline: 2.2px solid #ffa52a;
  outline-offset: 1.5px;
}
@media print {
  header, nav, .composite-btn, .btn, button, select, .gallery-footer, footer { display: none !important; }
  .desc-panel { border: none !important; box-shadow: none !important; }
  body { background: #fff !important; color: #222 !important; }
  main { padding: 0 !important; }
}

/* --------- [ 10. Misc — Spacing, Inputs, Forms ] --------- */
label { display: inline-block; margin-bottom: 0.2em; font-weight: 500; }
input, textarea {
  border: 1px solid #bbb;
  border-radius: 0px;
  padding: 0.3em 0.55em;
  font-size: 1em;
  background: #fff;
  color: #232324;
}
input:focus, textarea:focus { border-color: var(--accent); }
::-webkit-scrollbar { width: 9px; background: #eee; border-radius: 5px; }
::-webkit-scrollbar-thumb { background: #ccc; border-radius: 0px; }
::-webkit-scrollbar-thumb:hover { background: #aaa; }

/* Responsive tweaks */
@media (max-width: 1200px) {
  .review-artwork-grid { max-width: 98vw; }
}
@media (max-width: 900px) {
  .review-artwork-grid { flex-direction: column; gap: 2em; }
  .mockup-col, .desc-col { max-width: 100%; min-width: 0; }
  .mockup-preview-grid { grid-template-columns: repeat(2,1fr); }
}
@media (max-width: 600px) {
  .mockup-preview-grid { grid-template-columns: 1fr; gap: 0.9em; }
  .review-artwork-grid { margin: 1.2em 0.2em; }
  .main-thumb { margin-bottom: 1em; }
  .desc-panel { padding: 1em 0.6em; }
}


/* ===============================
   [ CapitalArt Artwork Gallery Grid ]
   =============================== */
.gallery-section {
  margin: 2.5em auto 3.5em auto;
  max-width: 1250px;
  padding: 0 1em;
}
.artwork-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2.4em;
  margin-bottom: 2em;
}
.gallery-card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: box-shadow 0.18s, transform 0.12s;
  min-height: 365px;
  padding: 10px;
  overflow: hidden;
}
.gallery-card:hover {
  box-shadow: 0 4px 16px #0002;
  transform: translateY(-4px) scale(1.013);
}
.card-thumb {
  width: 100%;
  background: #f4f4f4;
  text-align: center;
  padding: 22px 0 7px 0;
}
.card-img-top {
  max-width: 94%;
  max-height: 210px;
  border-radius: var(--thumb-radius);
  object-fit: cover;
  box-shadow: 0 1px 7px #0001;
  background: #fafafa;
}
.card-details {
  flex: 1 1 auto;
  width: 100%;
  text-align: center;
  padding: 12px 13px 20px 13px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.card-title {
  font-size: 0.9em;
  font-weight: 400;
  margin-bottom: 7px;
  line-height: 1.2;
  color: var(--main-txt);
  min-height: 3em;
}
.btn, .btn-primary, .btn-secondary {
  margin-top: 7px;
  width: 90%;
  min-width: 90px;
  align-self: center;
}

.flash {
  background: #ffe6e6;
  border: 1px solid #f5b5b5;
  color: #740000;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 1.2em;
}
.flash ul { margin: 0; padding-left: 1.2em; }
@media (max-width: 800px) {
  .artwork-grid { gap: 1.3em; }
  .card-thumb { padding: 12px 0 4px 0; }
  .card-title { font-size: 1em; }
}

/* === Finalised Gallery === */
.finalised-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.6em;
  margin-top: 1.5em;
  justify-content: center;
}
.finalised-grid.list-view {
  display: block;
}
.finalised-grid.list-view .final-card {
  flex-direction: row;
  max-width: none;
  margin-bottom: 1em;
}
.finalised-grid.list-view .card-thumb {
  width: 150px;
  margin-right: 1em;
}
.final-card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 10px;
  display: flex;
  flex-direction: column;
  max-width: 350px;
  margin: 0 auto;
}
.final-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: auto;
}
.final-actions .btn {
  flex: 1 1 auto;
  min-width: 100px;
  width: auto;
  margin-top: 0;
}
.edit-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 1em;
}
.edit-actions .btn {
  flex: 1 1 auto;
  min-width: 100px;
  width: auto;
  margin-top: 0;
}
.finalised-badge {
  font-size: 0.9em;
  color: #d40000;
  align-self: center;
  padding: 4px 8px;
}
.view-toggle {
  margin-top: 0.5em;
}
.view-toggle button {
  margin-right: 0.5em;
}
.locked-badge {
  font-size: 0.9em;
  color: #0066aa;
  padding: 2px 6px;
  border: 1px solid #0066aa;
  margin-left: 6px;
}
.mini-mockup-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  margin-top: 6px;
}
.mini-mockup-grid img {
  width: 100%;
  max-height: 120px;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 1px 4px #0001;
}
.desc-snippet {
  font-size: 0.92em;
  margin: 4px 0 8px 0;
  line-height: 1.3;
}
@media (max-width: 800px) {
  .finalised-grid {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }
}

/* ===============================
   [ Edit Artwork Listing Page ]
   =============================== */
/* --- Edit Action Buttons Area --- */
.edit-listing-col {
  max-width: 540px;
  width: 100%;
}

.long-field {
  width: 100%;
  max-width: 540px;
  box-sizing: border-box;
  font-size: 1.05em;
  padding: 0.6em;
  margin-bottom: 1em;
  border-radius: 0 !important;   /* FORCE SQUARE */
}

.price-sku-row,
.row-inline {
  display: flex;
  gap: 1em;
}
.price-sku-row > div,
.row-inline > div {
  flex: 1;
}

.edit-actions-col {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.7em;
  margin: 2em 0 0 0;
  width: 100%;
  max-width: 540px;
}

.wide-btn {
  width: 100%;
  font-size: 1.12em;
  font-weight: bold;
  padding: 1em 0;
  border-radius: 0 !important;   /* FORCE SQUARE */
}

/* ====== SQUARE CORNERS: NO ROUNDING ANYWHERE ====== */
input,
textarea,
select,
button,
.mockup-thumb-img,
.main-thumbnail-img,
.mockup-card,
.swap-form,
.edit-listing-col,
.flash-error,
form,
.mockup-preview-grid,
.main-thumb {
  border-radius: 0 !important;
}

/* ====== SQUARE IMAGE THUMBNAILS ====== */
.mockup-thumb-img, .main-thumbnail-img {
  border-radius: 0 !important;
  border: 1px solid #eee;
  box-shadow: none;
  width: 100%;
  height: auto;
  display: block;
}

/* Other style fixes */
.flash-error {
  background: #fbeaea;
  color: #a60000;
  border-left: 5px solid #e10000;
  margin-bottom: 1.5em;
  padding: 1em;
  border-radius: 0 !important;
}
.status-line {
  font-weight: bold;
  font-size: 1.2em;
  margin-bottom: 1.1em;
}
.status-finalised { color: #c00; }
.status-pending { color: #ef7300; }

.missing-img {
  width: 100%;
  padding: 20px 0;
  background: #eee;
  color: #777;
  font-size: 0.9em;
  border-radius: 0 !important;
}
.empty-msg {
  text-align: center;
  margin: 2em 0;
  font-size: 1.2em;
  color: #555;
  border-radius: 0 !important;
}

/* Responsive - match what you want */
@media (max-width: 800px) {
  .edit-listing-col, .review-artwork-grid { padding: 1em; }
  .row-inline, .price-sku-row { flex-direction: column; gap: 0.5em; }
}

/* ===============================
   [ Upload Dropzone ]
   =============================== */
.upload-dropzone {
  border: 2px dashed #bbb;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  color: #666;
  transition: background 0.2s, border-color 0.2s;
}
.upload-dropzone.dragover {
  border-color: #333;
  background: #f9f9f9;
}

.upload-list {
  margin-top: 1em;
  list-style: none;
  padding: 0;
  font-size: 0.9rem;
}
.upload-list li {
  margin: 0.2em 0;
}
.upload-list li.success { color: green; }
.upload-list li.error { color: red; }

.upload-progress {
  position: relative;
  background: #eee;
  height: 8px;
  margin: 2px 0;
  width: 100%;
  overflow: hidden;
}
.upload-progress-bar {
  background: var(--accent);
  height: 100%;
  width: 0;
  transition: width 0.2s;
}
.upload-percent {
  margin-left: 4px;
  font-size: 0.8em;
}

/* --------- [ Workflow Step Grid ] --------- */
.workflow-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1em;
  margin: 2em 0;
}
.step-btn {
  display: block;
  padding: 0.8em;
  background: var(--accent);
  color: #fff;
  text-align: center;
  text-decoration: none;
  border-radius: var(--radius);
}
.step-btn.disabled {
  background: #ccc;
  pointer-events: none;
  color: #666;
}

/* --------- [ Analysis Progress Modal ] --------- */
.analysis-modal {
  display: none;
  position: fixed;
  z-index: 100;
  left: 0;
  top: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0,0,0,0.65);
  align-items: center;
  justify-content: center;
}
.analysis-modal.active { display: flex; }

.analysis-box {
  background: #fff;
  padding: 1em 1.2em;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
}
.analysis-log {
  font-family: monospace;
  background: #fafbfc;
  border: 1px solid #ddd;
  padding: 0.6em;
  max-height: 60vh;
  overflow-y: auto;
  white-space: pre-wrap;
  font-size: 0.92em;
}
.analysis-log .log-error { color: #b00; }
.analysis-log .latest { background: #eef; }

.analysis-progress {
  background: #eee;
  height: 10px;
  margin: 0.5em 0;
  width: 100%;
}
.analysis-progress-bar {
  background: var(--accent);
  height: 100%;
  width: 0;
  transition: width 0.3s ease;
}
.analysis-status {
  font-size: 0.9em;
  margin-bottom: 0.6em;
}
.analysis-friendly {
  text-align: center;
  font-size: 0.9em;
  margin-top: 0.6em;
  font-style: italic;
}

/* ===============================
   [ OpenAI Details Table ]
   =============================== */
.openai-details table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 2em;
  font-size: 0.8em;    /* smaller for both columns */
  table-layout: fixed;
}

.openai-details th,
.openai-details td {
  padding-bottom: 0.35em;
  vertical-align: top;
  word-break: break-word;
}

/* Make the first column (labels) nice and wide, second takes rest */
.openai-details th {
  width: 105px;    /* adjust as needed for your headings */
  min-width: 95px;
  font-weight: 600;
  text-align: left;
  font-size: 0.8em;
  white-space: nowrap;   /* keep all on one line */
  padding-bottom: 10px;
  padding-right: 1em;
}

.openai-details td {
  font-size: 0.8em;
}

@media (max-width: 650px) {
  .openai-details th {
    width: 110px;
    min-width: 90px;
    font-size: 0.8em;
  }
  .openai-details td {
    font-size: 0.8em;
  }
}

.openai-details table tr:nth-child(even) {
  background: #dddddd;
}

.openai-details th,
.openai-details td {
  padding: 0.33em 0.6em 0.33em 0.3em;
}

/* ===============================
   [ Sellbrite Exports ]
   =============================== */
.export-actions { margin-bottom: 1em; }
.exports-table { width: 100%; border-collapse: collapse; }
.exports-table th, .exports-table td { padding: 0.4em 0.6em; border-bottom: 1px solid #ddd; }
.exports-table tr:nth-child(even) { background: #f5f5f5; }
.export-log { background: #f5f5f5; padding: 1em; white-space: pre-wrap; }
```

---
## 📄 static/js/upload.js

```js
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const list = document.getElementById('upload-list');

function createRow(file) {
  const li = document.createElement('li');
  li.textContent = file.name + ' ';
  const barWrap = document.createElement('div');
  barWrap.className = 'upload-progress';
  const bar = document.createElement('div');
  bar.className = 'upload-progress-bar';
  barWrap.appendChild(bar);
  const txt = document.createElement('span');
  txt.className = 'upload-percent';
  li.appendChild(barWrap);
  li.appendChild(txt);
  list.appendChild(li);
  return {li, bar, txt};
}

function uploadFile(file) {
  return new Promise((resolve) => {
    const {li, bar, txt} = createRow(file);
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('images', file);
    xhr.open('POST', '/upload');
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const p = Math.round(e.loaded / e.total * 100);
        bar.style.width = p + '%';
        txt.textContent = p + '%';
      }
    };
    xhr.onload = () => {
      if (xhr.status === 200) {
        const res = JSON.parse(xhr.responseText)[0];
        if (res.success) {
          li.classList.add('success');
          txt.textContent = 'Uploaded!';
        } else {
          li.classList.add('error');
          txt.textContent = res.error;
        }
      } else {
        li.classList.add('error');
        txt.textContent = 'Error ' + xhr.status;
      }
      resolve();
    };
    xhr.onerror = () => { li.classList.add('error'); txt.textContent = 'Failed'; resolve(); };
    xhr.send(formData);
  });
}

async function uploadFiles(files) {
  if (!files || !files.length) return;
  list.innerHTML = '';
  for (const f of Array.from(files)) {
    await uploadFile(f);
  }
  if (list.querySelector('li.success')) {
    window.location.href = '/artworks';
  }
}

if (dropzone) {
  ['dragenter','dragover'].forEach(evt => {
    dropzone.addEventListener(evt, e => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });
  ['dragleave','drop'].forEach(evt => {
    dropzone.addEventListener(evt, () => {
      dropzone.classList.remove('dragover');
    });
  });
  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    uploadFiles(e.dataTransfer.files);
  });
  dropzone.addEventListener('click', () => fileInput.click());
}

if (fileInput) {
  fileInput.addEventListener('change', () => uploadFiles(fileInput.files));
}

```

---
## 📄 static/js/main.js

```js
const themeToggle = document.getElementById('theme-toggle');
const sunIcon = document.getElementById('icon-sun');
const moonIcon = document.getElementById('icon-moon');

function updateThemeIcons(theme) {
  if (theme === 'dark') {
    sunIcon.style.display = 'none';
    moonIcon.style.display = 'inline';
  } else {
    sunIcon.style.display = 'inline';
    moonIcon.style.display = 'none';
  }
}

themeToggle.addEventListener('click', () => {
  // Swap theme logic here (not shown for brevity)
  // Then update icons:
  const theme = document.documentElement.getAttribute('data-theme');
  updateThemeIcons(theme === 'dark' ? 'light' : 'dark');
});
```

---
## 📄 mnt/data/Full-Rundown.txt

```txt
🎨 DreamArtMachine / ArtNarrator — Master System Overview
By Robin “Robbie” Custance | Updated July 2025 | For Codex Reference

1. Project Vision & Core Philosophy
DreamArtMachine (now evolving as ArtNarrator) is a next-gen, self-hosted, modular art business suite purpose-built for digital artists, especially those working at scale. It automates everything from art upload and AI-powered description writing, to bulk mockup generation, export-ready listings, and deep quality control.
The system is specifically crafted for Australian and Aboriginal art workflows, with a focus on authentic storytelling, cultural sensitivity, and pro-level curation.
End Game: Empower artists to control, scale, and monetize their art—without losing their voice, values, or sanity.

Key Ethos:

Keep the artist at the centre (no soulless automation).

Scale, but never at the expense of quality or culture.

Every artwork gets world-class treatment, from visual curation to written narrative.

2. Tech Stack & Architecture
Core: Python 3.11+, FastAPI backend, Jinja2 templates for admin UI.

AI: OpenAI GPT-4 Vision (with future Gemini/Mistral/Claude plug-in support).

DB: SQLite (migratable to Postgres). ORM: SQLAlchemy + Pydantic.

Image Ops: Pillow, pathlib.

File I/O: Strict folder conventions. All files versioned, named, and logged.

Export: Native CSV (Etsy, Nembol), JSON, partner ZIPs.

Security: Passlib, session management, role-based auth.

Automation: Shell scripts, cron jobs, code snapshots, QA bots.

Hosting: Google Cloud VM (Linux), ready for Docker/cloud.

3. Project Goals & Differentiators
Fully Automated Pipeline: From upload to export, every repetitive step is automated.

AI-Driven Listings: Generates 400+ word, Pulitzer-worthy, SEO-optimized, culturally aware listings using custom prompt templates and reusable content blocks.

Mockup Automation: Generates, manages, and enforces naming/filing rules for mockups and their variants.

Strict Data Integrity: Every move, rename, export is logged. Orphaned files/records are flagged.

Cultural Intelligence: Aboriginal art and Aussie nature profiles ensure all content is respectful, authentic, and on-brand.

Zero CSV Headaches: Exports are always ready for upload—no manual Excel cleanups.

Deep QA: Every step (file, DB, listing) gets QC checked, with reports/audit logs.

4. Core Workflows
A. Upload & Ingestion:

User uploads high-res artwork.

System assigns temp-processing folder and extracts metadata.

DB entry created: tracks file, user, status, etc.

B. AI Analysis:

Triggers OpenAI Vision for visual breakdown (style, colour, subject, texture, method).

Runs custom prompt for long-form listing—adheres to “Robbie Mode™” (fun, warm, pro curation, culturally aware, strict CTAs).

Stores AI results (title, desc, analysis) in DB.

C. Mockup Generation:

Batch creates mockups from curated templates (room types, orientations).

Strict naming ({seo_filename}-MU-01.jpg etc.) and filing rules.

All mockups, thumbs, openai-variants stored per artwork.

D. Review & Finalization:

User reviews/selects best mockups in dashboard UI.

On finalize: moves assets to /finalised-artwork/{seo_folder}/, updates DB, cleans temp, enforces names.

E. Export & Publishing:

Exports listings for Etsy, Nembol, or partner (CSV, JSON, ZIP).

Exports always pass pre-flight QA (missing images, titles, tag count etc.).

F. Quality Assurance:

Scripts/UI run health checks for file/DB mismatches, broken links, naming issues.

Every critical action is timestamped and logged for traceability.

5. Data & File Structure
Upload: /art-uploads/temp-processing/{uuid}/

Final Artworks: /finalised-artwork/{seo_folder}/

Mockups: /mockup-generator/Input/Mockups/{aspect}/{category}/

Exports: /exports/Composites/

Naming:

Main: {seo_filename}.jpg

Mockups: {seo_filename}-MU-01.jpg ... -MU-10.jpg

Thumb: {seo_filename}-thumb.jpg

AI Variant: {seo_filename}-openai.jpg

DB:

Tracks artwork, mockup, user, export, status, file paths.

6. AI & Content Generation
Profiles: Supports multiple art/listing profiles (Aboriginal Dot Art, Australian Nature, etc.)—prompt blocks and templates are modular (editable in settings.json, etsy_master_template.txt).

Strict Prompting: No “realistic”/“immerse yourself”, includes aspect/technique, pro art curation, EEAT, and local Aussie flair.

Audit Logs: Every AI call (input/output, user, timing, version) is logged for debugging and review.

7. Security, Permissions, & Auth
User roles: Admin (full), Curator, Mockup, Exporter.

Strong password, session, optional 2FA.

Audit trail: Every login, edit, export logged (tamper-evident).

Privacy: No personal info in exports; all secrets in .env.

8. Integrations & Extensibility
Print-on-Demand: Gelato.com (ready for full API/CSV), future: Printful, others.

Marketplace: Etsy/Nembol CSVs, JSON for B2B, direct partner export (ZIPs).

WordPress: Gallery sync (planned via REST API or folder polling).

DevOps: All scripts, health checks, and deploys are versioned (nightly backups, dependency audits, etc.).

9. Coding Standards (“Robbie Mode™”)
All files fully sectioned, sub-sectioned, and labelled with unique codes (e.g. analyze-routes-py-1a).

Full table of contents (ToC) at the top of every major code file.

Comprehensive docstrings and inline comments.

No partial rewrites: Full files or well-defined sections only—never lose functionality.

Ask for clarification if anything is unclear—never guess.

New features are modular and backward compatible.

When updating/rewriting: never break existing workflows, QA, or naming conventions.

Scripts (Python, shell) start with a plain English summary, usage, dependencies.

10. Limitations & Roadmap
Manual review still needed for certain listings and mockups.

Admin UI: Functional but basic—mobile/responsive planned.

Bulk actions possible, but may slow with 10k+ artworks (scaling in progress).

Integrations: Full API connection for PODs, live sync with WordPress in development.

Advanced analytics/partner dashboard on roadmap.

Future: Automated listing QA bots, cultural compliance checks, team workflows, full SaaS version for trusted artist community.

11. Sample Workflow (From Artist POV)
Upload artwork →

AI analyzes, generates title/desc →

Batch generate mockups →

Review and finalize best mockups →

System renames/files everything into neat folders, logs everything in DB →

Export listing with all images, CSV, ready for Etsy/Nembol/POD/partners →

All actions logged and quality checked—easy to fix or retry.

12. Why This System is Different
Built by an artist, for artists—actual real-world curation and workflow, not “one size fits none”.

AI is a creative partner, not a replacement—your stories, your voice, your culture.

Designed for easy onboarding—whether you’re a dev, AI, or future team member, the docs, code, and practices are all here and crystal clear.

Can grow with you: from solo artist to collective, from Etsy to global partners.

For Codex/AI:
When writing or editing code, always reference this doc and enforce all section, naming, and workflow conventions. No quick hacks—only production-grade, well-commented, fully ToC’d code accepted.

If you’re a new developer, AI assistant, or future Robbie, read this top to bottom before you touch the code. Ask questions. Build awesome. And always keep the art (and a bit of Aussie heart) at the centre.
```

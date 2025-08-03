# routes/utils.py
"""
Central utility functions for the ArtNarrator Flask application.

This module provides helpers for data manipulation, image processing, and
interacting with the application's file-based data stores. It is designed
to be imported by the main route files and does not depend on them,
preventing circular imports.

Table of Contents (ToC)
-----------------------
[utils-py-1] Imports & Initialisation
    [utils-py-1a] Imports
    [utils-py-1b] Constants & Globals

[utils-py-2] Path & URL Utilities
    [utils-py-2a] relative_to_base
    [utils-py-2b] is_finalised_image
    [utils-py-2c] resolve_image_url

[utils-py-3] Template & UI Helpers
    [utils-py-3a] get_menu
    [utils-py-3b] populate_artwork_data_from_json
    [utils-py-3c] get_mockup_details_for_template

[utils-py-4] Image Processing Utilities
    [utils-py-4a] resize_image_for_long_edge
    [utils-py-4b] resize_for_analysis
    [utils-py-4c] apply_perspective_transform

[utils-py-5] Artwork Data Retrieval
    [utils-py-5a] get_all_artworks
    [utils-py-5b] list_processed_artworks
    [utils-py-5c] list_finalised_artworks
    [utils-py-5d] list_ready_to_analyze
    [utils-py-5e] latest_analyzed_artwork
    [utils-py-5f] latest_composite_folder

[utils-py-6] Mockup Management Utilities
    [utils-py-6a] get_mockup_categories
    [utils-py-6b] random_image
    [utils-py-6c] init_slots
    [utils-py-6d] compute_options
    [utils-py-6e] get_mockups
    [utils-py-6f] swap_one_mockup

[utils-py-7] Text & String Manipulation
    [utils-py-7a] prettify_slug
    [utils-py-7b] read_generic_text
    [utils-py-7c] clean_terms
    [utils-py-7d] get_allowed_colours

[utils-py-8] SKU Management
    [utils-py-8a] infer_sku_from_filename
    [utils-py-8b] sync_filename_with_sku
    [utils-py-8c] assign_or_get_sku
    [utils-py-8d] validate_all_skus

[utils-py-9] Listing File Path Management
    [utils-py-9a] update_listing_paths

[utils-py-10] Legacy Registry Management
    [utils-py-10a] _load_registry
    [utils-py-10b] _save_registry
    [utils-py-10c] register_new_artwork
    [utils-py-10d] move_and_log
    [utils-py-10e] update_status
    [utils-py-10f] get_record_by_base
    [utils-py-10g] get_record_by_seo_filename
    [utils-py-10h] remove_record_from_registry
"""

# === [ Section 1: Imports & Initialisation | utils-py-1 ] ===
# Handles all necessary library imports and sets up global constants for the module.
# Cross-references: config.py, helpers/listing_utils.py
# ---------------------------------------------------------------------------------

# --- [ 1a: Imports | utils-py-1a ] ---
from __future__ import annotations
import time
import os
import json
import random
import re
import logging
import shutil
import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from flask import session, url_for
from PIL import Image
try:
    import cv2
except ImportError:
    cv2 = None # OpenCV is an optional dependency for perspective transforms
import numpy as np

import config
from utils.sku_assigner import get_next_sku
# FIX: Import helpers from the correct module to break the circular dependency
from helpers.listing_utils import resolve_listing_paths, load_json_file_safe


# --- [ 1b: Constants & Globals | utils-py-1b ] ---
Image.MAX_IMAGE_PIXELS = None
logger = logging.getLogger(__name__)

# Expose a LOGS_DIR constant so tests and other modules can monkeypatch or
# reference the application's log directory without importing ``config``
# directly.  Falling back to a temporary path keeps this module safe during
# isolated unit tests where ``config.LOGS_DIR`` may not exist.
LOGS_DIR = getattr(config, "LOGS_DIR", Path("/tmp/logs"))

ALLOWED_COLOURS = sorted(config.ETSY_COLOURS.keys())
ALLOWED_COLOURS_LOWER = {c.lower(): c for c in ALLOWED_COLOURS}


# === [ Section 2: Path & URL Utilities | utils-py-2 ] ===
# A collection of helper functions for manipulating and resolving file paths and URLs.
# ---------------------------------------------------------------------------------

# --- [ 2a: relative_to_base | utils-py-2a ] ---
def relative_to_base(path: Path | str) -> str:
    """
    Converts an absolute filesystem path to a path string relative to the project's base directory.

    Args:
        path: The absolute Path object or string to convert.

    Returns:
        A string representing the path relative to the project root (e.g., "static/img/logo.png").
    """
    return str(Path(path).resolve().relative_to(config.BASE_DIR))


# --- [ 2b: is_finalised_image | utils-py-2b ] ---
def is_finalised_image(path: str | Path) -> bool:
    """
    Checks if a given file path exists within either the 'finalised-artwork' or 'artwork-vault' directories.

    Args:
        path: The file path string or Path object to check.

    Returns:
        True if the path is within a finalised or locked directory, False otherwise.
    """
    p = Path(path).resolve()
    try:
        p.relative_to(config.FINALISED_ROOT)
        return True
    except ValueError:
        try:
            p.relative_to(config.ARTWORK_VAULT_ROOT)
            return True
        except ValueError:
            return False


# --- [ 2c: resolve_image_url | utils-py-2c ] ---
def resolve_image_url(path: Path) -> str:
    """Convert a filesystem path to an absolute public URL.

    Args:
        path: Absolute :class:`Path` to an image on disk.

    Returns:
        Fully-qualified URL pointing to the image using the configured
        ``BASE_URL`` and project ``BASE_DIR``.
    """
    relative_path = path.relative_to(config.BASE_DIR).as_posix()
    return f"{config.BASE_URL}/{relative_path}"


# === [ Section 3: Template & UI Helpers | utils-py-3 ] ===
# Functions that provide data and context specifically for rendering Jinja2 templates.
# ---------------------------------------------------------------------------------

# --- [ 3a: get_menu | utils-py-3a ] ---
def get_menu() -> List[Dict[str, str | None]]:
    """
    Generates the dynamic navigation menu items for the main layout template.
    Includes a link to the most recently analyzed artwork for quick access.

    Returns:
        A list of dictionaries, where each dictionary represents a menu item.
    """
    menu = [
        {"name": "Home", "url": url_for("artwork.home")},
        {"name": "Artwork Gallery", "url": url_for("artwork.artworks")},
        {"name": "Finalised", "url": url_for("artwork.finalised_gallery")},
    ]
    latest = latest_analyzed_artwork()
    if latest and latest.get("aspect") and latest.get("filename"):
        try:
            menu.append({
                "name": "Review Latest Listing",
                "url": url_for("artwork.edit_listing", aspect=latest["aspect"], filename=latest["filename"]),
            })
        except Exception:
             menu.append({"name": "Review Latest Listing", "url": None})
    else:
        menu.append({"name": "Review Latest Listing", "url": None})
    return menu


# --- [ 3b: populate_artwork_data_from_json | utils-py-3b ] ---
def populate_artwork_data_from_json(data: dict, seo_folder: str) -> dict:
    """
    Populates a dictionary with artwork details from a listing JSON for the edit page form.

    Args:
        data: The dictionary loaded from the artwork's -listing.json file.
        seo_folder: The name of the artwork's parent folder.

    Returns:
        A dictionary formatted for easy use in the Jinja2 template.
    """
    tags_list = data.get("tags", [])
    materials_list = data.get("materials", [])
    artwork = {
        "title": data.get("title", prettify_slug(seo_folder)),
        "description": data.get("description", ""),
        "tags": tags_list,
        "tags_str": ", ".join(tags_list),
        "materials": materials_list,
        "materials_str": ", ".join(materials_list),
        "dimensions": data.get("dimensions", ""),
        "size": data.get("size", ""),
        "primary_colour": data.get("primary_colour", ""),
        "secondary_colour": data.get("secondary_colour", ""),
        "seo_filename": data.get("seo_filename", f"{seo_folder}.jpg"),
        "seo_slug": seo_folder,
        "price": data.get("price", "18.27"),
        "sku": data.get("sku", ""),
        "images": "\n".join(data.get("images", [])),
        "generic_text": read_generic_text(data.get("aspect_ratio", ""))
    }
    return artwork


# --- [ 3c: get_mockup_details_for_template | utils-py-3c ] ---
def get_mockup_details_for_template(mockups_data: list, folder: Path, seo_folder: str, aspect: str) -> list:
    """
    Processes mockup data from a listing file for use in the edit_listing template.

    Args:
        mockups_data: The 'mockups' list from the listing JSON.
        folder: The absolute path to the artwork's parent directory.
        seo_folder: The name of the artwork's parent folder.
        aspect: The aspect ratio of the artwork (e.g., '4x5').

    Returns:
        A list of dictionaries, each representing a mockup with its associated paths and metadata.
    """
    mockups = []
    for idx, mp in enumerate(mockups_data):
        composite_name = mp.get("composite", "")
        thumb_name = mp.get("thumbnail", "")
        category = mp.get("category", "")

        out_path = folder / composite_name if composite_name else Path()
        thumb_path = folder / config.THUMB_SUBDIR / thumb_name if thumb_name else Path()
        
        path_rel = f"{seo_folder}/{composite_name}" if composite_name else ""
        thumb_rel_path = f"{seo_folder}/{config.THUMB_SUBDIR}/{thumb_name}" if thumb_name else ""
        
        mockups.append({
            "path": out_path,
            "category": category,
            "exists": out_path.exists(),
            "index": idx,
            "thumb": thumb_path,
            "thumb_exists": thumb_path.exists(),
            "path_rel": path_rel,
            "thumb_rel": thumb_rel_path,
        })
    return mockups


# === [ Section 4: Image Processing Utilities | utils-py-4 ] ===
# Functions for handling image manipulations like resizing and transformations.
# ---------------------------------------------------------------------------------

# --- [ 4a: resize_image_for_long_edge | utils-py-4a ] ---
def resize_image_for_long_edge(image: Image.Image, target_long_edge: int = 2000) -> Image.Image:
    """Resizes an image to have its longest edge match the target size, preserving aspect ratio."""
    width, height = image.size
    scale = target_long_edge / max(width, height)
    if scale < 1.0:
        new_width = int(width * scale)
        new_height = int(height * scale)
        return image.resize((new_width, new_height), Image.LANCZOS)
    return image.copy()


# --- [ 4b: resize_for_analysis | utils-py-4b ] ---
def resize_for_analysis(image: Image.Image, dest_path: Path):
    """
    Resizes and saves an image to be compliant with AI analysis size and filetype limits.
    It iteratively reduces JPEG quality to ensure the file is under the max size.
    """
    w, h = image.size
    scale = config.ANALYSE_MAX_DIM / max(w, h)
    if scale < 1.0:
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    
    image = image.convert("RGB")
    q = 85
    while True:
        image.save(dest_path, "JPEG", quality=q, optimize=True)
        if dest_path.stat().st_size <= config.ANALYSE_MAX_MB * 1024 * 1024 or q <= 60:
            break
        q -= 5


# --- [ 4c: apply_perspective_transform | utils-py-4c ] ---
def apply_perspective_transform(art_img: Image.Image, mockup_img: Image.Image, dst_coords: list) -> Image.Image:
    """Overlays artwork onto a mockup using perspective transform, handling RGBA transparency."""
    if cv2 is None:
        raise RuntimeError("OpenCV (cv2) library is required for perspective transform.")
    w, h = art_img.size
    src_points = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    dst_points = np.float32([[c['x'], c['y']] for c in dst_coords])
    
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    art_np = np.array(art_img.convert("RGBA"))
    
    warped = cv2.warpPerspective(art_np, matrix, (mockup_img.width, mockup_img.height))
    warped_pil = Image.fromarray(warped)
    
    final_image = Image.alpha_composite(mockup_img.convert("RGBA"), warped_pil)
    return final_image


# === [ Section 5: Artwork Data Retrieval | utils-py-5 ] ===
# Functions for scanning the filesystem and retrieving lists of artworks in various states.
# ---------------------------------------------------------------------------------

# --- [ 5a: get_all_artworks | utils-py-5a ] ---
def get_all_artworks() -> List[Dict]:
    """Scans all artwork locations (processed, finalised, locked) and returns a unified list."""
    items: List[Dict] = []
    
    def process_directory(directory: Path, status: str):
        if not directory.exists(): return
        for folder in directory.iterdir():
            if not folder.is_dir(): continue
            
            slug = folder.name.replace("LOCKED-", "")
            listing_file = folder / f"{slug}-listing.json"
            if not listing_file.exists(): continue

            try:
                data = load_json_file_safe(listing_file)
                thumb_img = folder / config.FILENAME_TEMPLATES["thumbnail"].format(seo_slug=slug)
                
                item = {
                    "status": status,
                    "seo_folder": folder.name,
                    "title": data.get("title") or prettify_slug(slug),
                    "filename": data.get("filename", f"{slug}.jpg"),
                    "thumb": thumb_img.name if thumb_img.exists() else f"{slug}-THUMB.jpg",
                    "aspect": data.get("aspect_ratio", ""),
                    "locked": data.get("locked", False),
                }
                items.append(item)
            except Exception as e:
                logging.error(f"Failed to process listing in {folder.name}: {e}")
                continue

    process_directory(config.PROCESSED_ROOT, "processed")
    process_directory(config.FINALISED_ROOT, "finalised")
    process_directory(config.ARTWORK_VAULT_ROOT, "locked")
    
    items.sort(key=lambda x: x["title"].lower())
    return items


# --- [ 5b: list_processed_artworks | utils-py-5b ] ---
def list_processed_artworks() -> Tuple[List[Dict], set]:
    """Returns a list of artworks in the 'processed' state and a set of their filenames."""
    processed_artworks = [a for a in get_all_artworks() if a['status'] == 'processed']
    processed_filenames = {a['filename'] for a in processed_artworks}
    return processed_artworks, processed_filenames


# --- [ 5c: list_finalised_artworks | utils-py-5c ] ---
def list_finalised_artworks() -> List[Dict]:
    """Returns a list of artworks in the 'finalised' state."""
    return [a for a in get_all_artworks() if a['status'] == 'finalised']


# --- [ 5d: list_ready_to_analyze | utils-py-5d ] ---
def list_ready_to_analyze(processed_filenames: set) -> List[Dict]:
    """Returns artworks from the unanalysed folder that are not yet processed."""
    ready: List[Dict] = []
    for qc_path in config.UNANALYSED_ROOT.glob("**/*.qc.json"):
        base = qc_path.name.replace(".qc.json", "")
        try:
            qc_data = load_json_file_safe(qc_path)
            original_filename = qc_data.get("original_filename")
            if original_filename and original_filename in processed_filenames:
                continue
            
            ext = qc_data.get("extension", "jpg")
            title = prettify_slug(Path(original_filename or base).stem)
            
            ready.append({
                "aspect": qc_data.get("aspect_ratio", ""),
                "filename": f"{base}.{ext}",
                "title": title,
                "thumb": f"{base}-thumb.jpg",
                "base": base,
            })
        except Exception as e:
            logging.error(f"Error processing QC file {qc_path}: {e}")
            continue
            
    ready.sort(key=lambda x: x["title"].lower())
    return ready


# --- [ 5e: latest_analyzed_artwork | utils-py-5e ] ---
def latest_analyzed_artwork() -> Optional[Dict[str, str]]:
    """Finds the most recently modified artwork in the 'processed' directory."""
    latest_time = 0
    latest_info = None
    if not config.PROCESSED_ROOT.exists():
        return None
    for folder in config.PROCESSED_ROOT.iterdir():
        if not folder.is_dir(): continue
        listing_path = next(folder.glob("*-listing.json"), None)
        if not listing_path: continue
        
        mtime = listing_path.stat().st_mtime
        if mtime > latest_time:
            latest_time = mtime
            data = load_json_file_safe(listing_path)
            latest_info = { "aspect": data.get("aspect_ratio"), "filename": data.get("seo_filename") }
    return latest_info


# --- [ 5f: latest_composite_folder | utils-py-5f ] ---
def latest_composite_folder() -> str | None:
    """Returns the name of the most recently modified folder in PROCESSED_ROOT."""
    processed_dir = config.PROCESSED_ROOT
    if not processed_dir.exists():
        return None

    sub_folders = [d for d in processed_dir.iterdir() if d.is_dir()]
    if not sub_folders:
        return None

    latest_folder = max(sub_folders, key=lambda d: d.stat().st_mtime)
    return latest_folder.name


# === [ Section 6: Mockup Management Utilities | utils-py-6 ] ===
# Functions related to the interactive mockup selection workflow.
# ---------------------------------------------------------------------------------

# --- [ 6a: get_mockup_categories | utils-py-6a ] ---
def get_mockup_categories(aspect_folder: Path | str) -> List[str]:
    """Return sorted list of category folder names under a specific aspect folder."""
    folder = Path(aspect_folder)
    if not folder.exists(): return []
    return sorted(f.name for f in folder.iterdir() if f.is_dir() and not f.name.startswith("."))


# --- [ 6b: random_image | utils-py-6b ] ---
def random_image(category: str, aspect: str) -> Optional[str]:
    """Return a random image filename for a given category and aspect."""
    cat_dir = config.MOCKUPS_CATEGORISED_DIR / aspect / category
    if not cat_dir.exists(): return None
    images = [f.name for f in cat_dir.glob("*.png")]
    return random.choice(images) if images else None


# --- [ 6c: init_slots | utils-py-6c ] ---
def init_slots() -> None:
    """Initialise mockup slot selections in the user's session."""
    aspect = "4x5"
    cats = get_mockup_categories(config.MOCKUPS_CATEGORISED_DIR / aspect)
    session["slots"] = [{"category": c, "image": random_image(c, aspect)} for c in cats]


# --- [ 6d: compute_options | utils-py-6d ] ---
def compute_options(slots) -> List[List[str]]:
    """Return category options for each slot in the mockup selector."""
    aspect = "4x5"
    cats = get_mockup_categories(config.MOCKUPS_CATEGORISED_DIR / aspect)
    return [cats for _ in slots]


# --- [ 6e: get_mockups | utils-py-6e ] ---
def get_mockups(seo_folder: str) -> list:
    """Return mockup entries from an artwork's listing JSON."""
    try:
        _, _, listing_file, _ = resolve_listing_paths("", seo_folder, allow_locked=True)
        data = load_json_file_safe(listing_file)
        return data.get("mockups", [])
    except Exception as exc:
        logger.error(f"Failed reading mockups for {seo_folder}: {exc}")
        return []


# --- [ 6f: swap_one_mockup | utils-py-6f ] ---
def swap_one_mockup(seo_folder: str, slot_idx: int, new_category: str, current_mockup_src: str | None = None) -> tuple[bool, str, str]:
    """Swaps a single mockup to a new category and regenerates the composite image."""
    try:
        _, folder, listing_file, _ = resolve_listing_paths("", seo_folder, allow_locked=True)
    except FileNotFoundError:
        return False, "", ""
            
    with open(listing_file, "r", encoding="utf-8") as f: data = json.load(f)
    mockups = data.get("mockups", [])
    if not (0 <= slot_idx < len(mockups)): return False, "", ""

    aspect = data.get("aspect_ratio")
    mockup_root = config.MOCKUPS_CATEGORISED_DIR / aspect / new_category
    mockup_files = list(mockup_root.glob("*.png"))
    
    current_mockup_name = None
    if isinstance(mockups[slot_idx], dict):
        composite_name = mockups[slot_idx].get("composite", "")
        match = re.search(r'-([^-]+-\d+)(?:-\d+)?\.jpg$', composite_name)
        if match: current_mockup_name = f"{match.group(1)}.png"
    
    choices = [f for f in mockup_files if f.name != current_mockup_name]
    if not choices: choices = mockup_files
    if not choices: return False, "", ""
    new_mockup = random.choice(choices)
    
    timestamp = int(time.time())
    
    coords_path = config.COORDS_DIR / aspect / new_category / f"{new_mockup.stem}.json"
    slug = seo_folder.replace("LOCKED-", "")
    art_path = folder / f"{slug}.jpg"
    
    output_filename = f"{slug}-{new_mockup.stem}-{timestamp}.jpg"
    output_path = folder / output_filename

    try:
        old = mockups[slot_idx]
        if isinstance(old, dict):
            if old.get("composite"): (folder / old["composite"]).unlink(missing_ok=True)
            if old.get("thumbnail"): (folder / "THUMBS" / old["thumbnail"]).unlink(missing_ok=True)

        with open(coords_path, "r", encoding="utf-8") as cf: c = json.load(cf)["corners"]
        dst = [[c[0]["x"], c[0]["y"]], [c[1]["x"], c[1]["y"]], [c[3]["x"], c[3]["y"]], [c[2]["x"], c[2]["y"]]]
        with Image.open(art_path) as art_img, Image.open(new_mockup) as mock_img:
            art_img = resize_image_for_long_edge(art_img.convert("RGBA"))
            composite = apply_perspective_transform(art_img, mock_img.convert("RGBA"), dst)
        composite.convert("RGB").save(output_path, "JPEG", quality=85)

        thumb_dir = folder / "THUMBS"; thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_name = f"{slug}-{new_mockup.stem}-thumb-{timestamp}.jpg"
        thumb_path = thumb_dir / thumb_name
        with composite.copy() as thumb_img:
            thumb_img.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
            thumb_img.convert("RGB").save(thumb_path, "JPEG", quality=85)
            
        data.setdefault("mockups", [])[slot_idx] = {
            "category": new_category,
            "source": str(new_mockup.relative_to(config.MOCKUPS_INPUT_DIR)),
            "composite": output_path.name,
            "thumbnail": thumb_name,
        }
        with open(listing_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
        return True, output_path.name, thumb_name
    except Exception as e:
        logging.getLogger(__name__).error(f"Swap error: {e}")
        return False, "", ""


# === [ Section 7: Text & String Manipulation | utils-py-7 ] ===
# Helpers for cleaning, formatting, and manipulating strings.
# ---------------------------------------------------------------------------------

# --- [ 7a: prettify_slug | utils-py-7a ] ---
def prettify_slug(slug: str) -> str:
    """Converts a filename-safe slug into a human-readable title."""
    name = os.path.splitext(slug)[0].replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", name).title()


# --- [ 7b: read_generic_text | utils-py-7b ] ---
def read_generic_text(aspect: str) -> str:
    """Reads the generic boilerplate text block for a given aspect ratio."""
    path = config.GENERIC_TEXTS_DIR / f"{aspect}.txt"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        logger.warning(f"Generic text for {aspect} not found at {path}")
        return ""


# --- [ 7c: clean_terms | utils-py-7c ] ---
def clean_terms(items: List[str]) -> Tuple[List[str], bool]:
    """Removes invalid characters from a list of strings (e.g., tags)."""
    cleaned: List[str] = []
    changed = False
    for item in items:
        new = re.sub(r"[^A-Za-z0-9 ,]", "", item).replace("-", "").strip()
        new = re.sub(r"\s+", " ", new)
        if new != item.strip(): changed = True
        if new: cleaned.append(new)
    return cleaned, changed


# --- [ 7d: get_allowed_colours | utils-py-7d ] ---
def get_allowed_colours() -> List[str]:
    """Returns a copy of the list of Etsy-allowed color names."""
    return ALLOWED_COLOURS.copy()


# === [ Section 8: SKU Management | utils-py-8 ] ===
# Functions for handling Stock Keeping Units (SKUs).
# ---------------------------------------------------------------------------------

# --- [ 8a: infer_sku_from_filename | utils-py-8a ] ---
def infer_sku_from_filename(filename: str) -> Optional[str]:
    """Extracts a SKU from a filename string."""
    m = re.search(r"RJC-([A-Za-z0-9-]+)(?:\.jpg)?$", filename or "")
    return f"RJC-{m.group(1)}" if m else None


# --- [ 8b: sync_filename_with_sku | utils-py-8b ] ---
def sync_filename_with_sku(seo_filename: str, sku: str) -> str:
    """Replaces the SKU portion of a filename with a new SKU."""
    if not seo_filename or not sku: return seo_filename
    return re.sub(r"RJC-[A-Za-z0-9-]+(?=\.jpg$)", sku, seo_filename)


# --- [ 8c: assign_or_get_sku | utils-py-8c ] ---
def assign_or_get_sku(listing_json_path: Path, tracker_path: Path, *, force: bool = False) -> str:
    """Retrieves an existing SKU from a listing file or assigns a new one."""
    data = load_json_file_safe(listing_json_path)
    if not force and data.get("sku"): return data["sku"]
    sku = get_next_sku(tracker_path)
    data["sku"] = sku
    if data.get("seo_filename"):
        data["seo_filename"] = sync_filename_with_sku(data["seo_filename"], sku)
    with open(listing_json_path, "w") as f: json.dump(data, f, indent=2)
    return sku


# --- [ 8d: validate_all_skus | utils-py-8d ] ---
def validate_all_skus(entries: List[dict], tracker_path: Path) -> List[str]:
    """Validates SKUs for format, duplicates, and gaps in a list of entries."""
    seen = set()
    errors = []
    sku_numbers = []

    for entry in entries:
        sku = entry.get("sku", "").strip()
        if not sku or not sku.startswith("RJC-"):
            errors.append(f"Invalid SKU format: {sku}")
            continue
        
        if sku in seen:
            errors.append(f"Duplicate SKU found: {sku}")
        seen.add(sku)
        
        try:
            num = int(sku.split('-')[-1])
            sku_numbers.append(num)
        except (ValueError, IndexError):
            errors.append(f"Could not parse SKU number: {sku}")

    if sku_numbers:
        sku_numbers.sort()
        for i in range(len(sku_numbers) - 1):
            if sku_numbers[i+1] != sku_numbers[i] + 1:
                errors.append(f"Gap detected in SKUs between {sku_numbers[i]} and {sku_numbers[i+1]}")
                break

    return errors


# === [ Section 9: Listing File Path Management | utils-py-9 ] ===
# Contains the critical function for updating paths within a listing.json file.
# ---------------------------------------------------------------------------------

# --- [ 9a: update_listing_paths | utils-py-9a ] ---
def update_listing_paths(listing_file: Path, old_root: Path, new_root: Path) -> None:
    """
    Updates all file paths within a listing JSON file when its parent folder is moved.
    This function is critical for the "Finalise" step to prevent broken image links.

    Args:
        listing_file: The path to the listing's JSON file.
        old_root: The old base directory (e.g., config.PROCESSED_ROOT).
        new_root: The new base directory (e.g., config.FINALISED_ROOT).
    """
    if not listing_file.exists():
        logger.warning(f"update_listing_paths was called but file not found: {listing_file}")
        return

    data = load_json_file_safe(listing_file)
    
    str_old_root = str(old_root)
    str_new_root = str(new_root)

    old_url_rel = old_root.relative_to(config.BASE_DIR).as_posix()
    new_url_rel = new_root.relative_to(config.BASE_DIR).as_posix()
    old_url_abs = config.resolve_image_url(old_root)
    new_url_abs = config.resolve_image_url(new_root)

    def _replace_all(text: str) -> str:
        for o, n in (
            (str_old_root, str_new_root),
            (old_url_rel, new_url_rel),
            (old_url_abs, new_url_abs),
        ):
            text = text.replace(o, n)
        return text

    # Update single-path keys
    for key in ["main_jpg_path", "thumb_jpg_path", "analyse_jpg_path", "processed_folder"]:
        if key in data and isinstance(data[key], str):
            data[key] = _replace_all(data[key])

    # Update list of image paths
    if "images" in data and isinstance(data["images"], list):
        data["images"] = [_replace_all(path) for path in data["images"]]
    
    with open(listing_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Updated all paths in {listing_file.name} from {old_root.name} to {new_root.name}.")


# === [ Section 10: Legacy Registry Management | utils-py-10 ] ===
# Functions for interacting with the old master-artwork-paths.json registry.
# These are kept for backward compatibility but may be phased out.
# ---------------------------------------------------------------------------------

# --- [ 10a: _load_registry | utils-py-10a ] ---
def _load_registry() -> dict:
    """Loads the master artwork JSON registry file."""
    return load_json_file_safe(config.OUTPUT_JSON)


# --- [ 10b: _save_registry | utils-py-10b ] ---
def _save_registry(reg: dict) -> None:
    """Writes data to the master artwork JSON registry atomically."""
    tmp = config.OUTPUT_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, config.OUTPUT_JSON)


# --- [ 10c: register_new_artwork | utils-py-10c ] ---
def register_new_artwork(uid: str, filename: str, folder: Path, assets: list, status: str, base: str):
    """Add a new artwork record to the legacy registry."""
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reg = _load_registry()
    reg[uid] = {
        "seo_filename": filename,
        "base": base,
        "current_folder": str(folder),
        "assets": assets,
        "status": status,
        "history": [{"status": status, "folder": str(folder), "timestamp": ts}],
        "upload_date": ts,
    }
    _save_registry(reg)


# --- [ 10d: move_and_log | utils-py-10d ] ---
def move_and_log(src: Path, dest: Path, uid: str, status: str):
    """Move a file and update its record in the legacy registry."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    reg = _load_registry()
    rec = reg.get(uid, {})
    rec.setdefault("history", []).append({
        "status": status,
        "folder": str(dest.parent),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    rec["current_folder"] = str(dest.parent)
    rec["status"] = status
    assets = set(rec.get("assets", []))
    assets.add(dest.name)
    rec["assets"] = sorted(assets)
    reg[uid] = rec
    _save_registry(reg)


# --- [ 10e: update_status | utils-py-10e ] ---
def update_status(uid: str, folder: Path, status: str):
    """Update the status of an artwork in the legacy registry."""
    reg = _load_registry()
    rec = reg.get(uid)
    if not rec: return
    rec.setdefault("history", []).append({
        "status": status,
        "folder": str(folder),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    rec["current_folder"] = str(folder)
    rec["status"] = status
    reg[uid] = rec
    _save_registry(reg)


# --- [ 10f: get_record_by_base | utils-py-10f ] ---
def get_record_by_base(base: str) -> tuple[str | None, dict | None]:
    """Find a legacy registry record by its unique base name."""
    reg = _load_registry()
    for uid, rec in reg.items():
        if rec.get("base") == base:
            return uid, rec
    return None, None


# --- [ 10g: get_record_by_seo_filename | utils-py-10g ] ---
def get_record_by_seo_filename(filename: str) -> tuple[str | None, dict | None]:
    """Find a legacy registry record by its SEO filename."""
    reg = _load_registry()
    for uid, rec in reg.items():
        if rec.get("seo_filename") == filename:
            return uid, rec
    return None, None


# --- [ 10h: remove_record_from_registry | utils-py-10h ] ---
def remove_record_from_registry(uid: str) -> bool:
    """Safely remove a record from the legacy JSON registry by its UID."""
    if not uid: return False
    reg = _load_registry()
    if uid in reg:
        del reg[uid]
        _save_registry(reg)
        logger.info(f"Removed record {uid} from registry.")
        return True
    return False
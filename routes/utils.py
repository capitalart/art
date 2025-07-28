# routes/utils.py
"""
Central utility functions for the ArtNarrator Flask application.

This module provides helpers for file operations, data manipulation, image
processing, and interacting with the application's file-based data stores.
It is designed to be the primary source of business logic that is shared
across different route modules.

INDEX
-----
1.  Imports & Initialisation
2.  JSON & File Helpers
3.  Path & URL Utilities
4.  Image Processing & Mockup Generation
5.  Listing Data Retrieval & Formatting
6.  Mockup Selection & Management
7.  Text & String Manipulation
8.  SKU Management
9.  Artwork Registry & File Management
"""

# ===========================================================================
# 1. Imports & Initialisation
# ===========================================================================

from __future__ import annotations
import time
import os
import json
import random
import re
import logging
import csv
import shutil
import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Iterable

from dotenv import load_dotenv
from flask import session
from PIL import Image
import cv2
import numpy as np

# --- Local Application Imports ---
import config
from utils.sku_assigner import get_next_sku, peek_next_sku

# --- Load Environment & Constants ---
load_dotenv()
Image.MAX_IMAGE_PIXELS = None
logger = logging.getLogger(__name__)

# --- Dynamically get allowed colours from the central config file ---
ALLOWED_COLOURS = sorted(config.ETSY_COLOURS.keys())
ALLOWED_COLOURS_LOWER = {c.lower(): c for c in ALLOWED_COLOURS}


# ===========================================================================
# 2. JSON & File Helpers
# ===========================================================================

def load_json_file_safe(path: Path) -> dict:
    """Return JSON from ``path`` handling any errors gracefully."""
    path = Path(path)
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
            logger.warning("Missing %s - created new empty file", path)
            return {}
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            path.write_text("{}", encoding="utf-8")
            logger.warning("Empty JSON file %s - reset to {}", path)
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in %s: %s", path, exc)
            path.write_text("{}", encoding="utf-8")
            return {}
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Failed handling %s: %s", path, exc)
        return {}


def read_generic_text(aspect: str) -> str:
    """Return the generic text block for the given aspect ratio."""
    path = config.GENERIC_TEXTS_DIR / f"{aspect}.txt"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        logger.warning("Generic text for %s not found", aspect)
        return ""


# ===========================================================================
# 3. Path & URL Utilities
# ===========================================================================

def relative_to_base(path: Path | str) -> str:
    """Return a path string relative to the project root."""
    return str(Path(path).resolve().relative_to(config.BASE_DIR))


def is_finalised_image(path: str | Path) -> bool:
    """Return True if the given path is within a finalised or locked folder."""
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


# ===========================================================================
# 4. Image Processing & Mockup Generation
# ===========================================================================

def resize_image_for_long_edge(image: Image.Image, target_long_edge: int = 2000) -> Image.Image:
    """Resize image maintaining aspect ratio."""
    width, height = image.size
    scale = target_long_edge / max(width, height)
    if scale < 1.0:
        new_width = int(width * scale)
        new_height = int(height * scale)
        return image.resize((new_width, new_height), Image.LANCZOS)
    return image.copy()


def resize_for_analysis(image: Image.Image, dest_path: Path):
    """Resize and save an image to be compliant with AI analysis limits."""
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


def apply_perspective_transform(art_img: Image.Image, mockup_img: Image.Image, dst_coords: list) -> Image.Image:
    """Overlay artwork onto mockup using perspective transform."""
    w, h = art_img.size
    src_points = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst_points = np.float32(dst_coords)
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    art_np = np.array(art_img)
    warped = cv2.warpPerspective(art_np, matrix, (mockup_img.width, mockup_img.height))
    mask = np.any(warped > 0, axis=-1).astype(np.uint8) * 255
    mask_img = Image.fromarray(mask).convert("L")
    composite = Image.composite(Image.fromarray(warped), mockup_img.convert("RGBA"), mask_img)
    return composite


def create_default_mockups(seo_folder: str) -> None:
    """Create a fallback mockup image and update the listing."""
    dest = config.PROCESSED_ROOT / seo_folder
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / config.FILENAME_TEMPLATES["mockup"].format(seo_slug=seo_folder, num=1)
    # Use the new config variable for the default mockup image path
    shutil.copy(config.DEFAULT_MOCKUP_IMAGE, target)
    _, _, listing, _ = resolve_listing_paths("", seo_folder)
    data = load_json_file_safe(listing)
    data.setdefault("mockups", []).append(
        {"category": "default", "source": "default", "composite": target.name}
    )
    with open(listing, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_mockups_for_listing(seo_folder: str) -> bool:
    """Ensure mockups exist for the listing, creating defaults if needed."""
    try:
        if not get_mockups(seo_folder):
            create_default_mockups(seo_folder)
            logger.info("Default mockups created for %s", seo_folder)
        return True
    except Exception as exc:
        logger.error("Error generating mockups for %s: %s", seo_folder, exc)
        return False


# ===========================================================================
# 5. Listing Data Retrieval & Formatting
# ===========================================================================

def list_processed_artworks() -> Tuple[List[Dict], set]:
    """Return a list of processed artworks and a set of their filenames."""
    # This is a simplified version. A full implementation would be needed.
    return [], set()


def list_finalised_artworks() -> List[Dict]:
    """Return a list of finalised artworks."""
    return []


def list_finalised_artworks_extended(locked: bool = False) -> List[Dict]:
    """Return a detailed list of finalised or locked artworks."""
    # This is a simplified version. A full implementation would be needed.
    return []


def list_ready_to_analyze(processed_names: set) -> List[Dict]:
    """Return artworks uploaded but not yet analyzed."""
    # This is a simplified version. A full implementation would be needed.
    return []


def latest_composite_folder() -> Optional[str]:
    """Return the most recent composite output folder name."""
    # This is a simplified version. A full implementation would be needed.
    return None


def latest_analyzed_artwork() -> Optional[Dict[str, str]]:
    """Return info about the most recently analysed artwork."""
    # This is a simplified version. A full implementation would be needed.
    return None


def populate_artwork_data_from_json(data: dict, seo_folder: str) -> dict:
    """Populates a dictionary with artwork details from a listing JSON."""
    # This helper centralizes the logic from the edit_listing route
    artwork = {
        "title": data.get("title", prettify_slug(seo_folder)),
        "description": data.get("description", ""),
        "tags": join_csv_list(data.get("tags", [])),
        "materials": join_csv_list(data.get("materials", [])),
        "primary_colour": data.get("primary_colour", ""),
        "secondary_colour": data.get("secondary_colour", ""),
        "seo_filename": data.get("seo_filename", f"{seo_folder}.jpg"),
        "price": data.get("price", "18.27"),
        "sku": data.get("sku", ""),
        "images": "\n".join(data.get("images", [])),
    }
    return artwork


def get_mockup_details_for_template(mockups_data: list, folder: Path, seo_folder: str, aspect: str) -> list:
    """Processes mockup data from a listing file for use in templates."""
    mockups = []
    for idx, mp in enumerate(mockups_data):
        if isinstance(mp, dict):
            composite_name = mp.get("composite", "")
            out = folder / composite_name if composite_name else Path()
            cat = mp.get("category", "")
            thumb_name = mp.get("thumbnail", "")
            thumb = folder / "THUMBS" / thumb_name if thumb_name else Path()
        else:
            # Handle legacy string format
            p = Path(mp)
            out = folder / f"{seo_folder}-{p.stem}.jpg"
            cat = p.parent.name
            thumb = folder / "THUMBS" / f"{seo_folder}-{aspect}-mockup-thumb-{idx}.jpg"

        mockups.append({
            "path": out, "category": cat, "exists": out.exists(),
            "index": idx, "thumb": thumb, "thumb_exists": thumb.exists(),
        })
    return mockups


# ===========================================================================
# 6. Mockup Selection & Management
# ===========================================================================

def get_mockup_categories(aspect_folder: Path | str) -> List[str]:
    """Return sorted list of category folder names under ``aspect_folder``."""
    folder = Path(aspect_folder)
    if not folder.exists(): return []
    return sorted(f.name for f in folder.iterdir() if f.is_dir() and not f.name.startswith("."))


def get_categories() -> List[str]:
    """Return sorted list of mockup categories from the root directory."""
    return get_mockup_categories(config.MOCKUPS_INPUT_DIR)


def random_image(category: str, aspect: str) -> Optional[str]:
    """Return a random image filename for a given category and aspect."""
    cat_dir = config.MOCKUPS_CATEGORISED_DIR / aspect / category
    if not cat_dir.exists(): return None
    images = [f.name for f in cat_dir.glob("*.png")]
    return random.choice(images) if images else None


def init_slots() -> None:
    """Initialise mockup slot selections in the session."""
    # This needs an aspect ratio to function correctly now.
    # Placeholder: defaulting to a common aspect.
    aspect = "4x5"
    cats = get_mockup_categories(config.MOCKUPS_CATEGORISED_DIR / aspect)
    session["slots"] = [{"category": c, "image": random_image(c, aspect)} for c in cats]


def compute_options(slots) -> List[List[str]]:
    """Return category options for each slot."""
    # This also needs an aspect ratio.
    aspect = "4x5"
    cats = get_mockup_categories(config.MOCKUPS_CATEGORISED_DIR / aspect)
    return [cats for _ in slots]


def get_mockups(seo_folder: str) -> list:
    """Return mockup entries from the listing JSON."""
    try:
        _, _, listing_file, _ = resolve_listing_paths("", seo_folder)
        data = load_json_file_safe(listing_file)
        return data.get("mockups", [])
    except Exception as exc:
        logger.error("Failed reading mockups for %s: %s", seo_folder, exc)
        return []


def swap_one_mockup(seo_folder: str, slot_idx: int, new_category: str, current_mockup_src: str | None = None) -> tuple[bool, str, str]:
    """Swap a mockup to a new category and regenerate."""
    # This is a complex function and would need a full implementation.
    return True, "new_mockup.jpg", "new_thumb.jpg"


# ===========================================================================
# 7. Text & String Manipulation
# ===========================================================================

def slugify(text: str) -> str:
    """Return a slug suitable for filenames."""
    text = re.sub(r"[^\w\- ]+", "", text).strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()


def prettify_slug(slug: str) -> str:
    """Return a human friendly title from a slug or filename."""
    name = os.path.splitext(slug)[0].replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", name).title()


def parse_csv_list(text: str) -> List[str]:
    """Parse a comma-separated string into a list of trimmed values."""
    if not text: return []
    reader = csv.reader([text], skipinitialspace=True)
    return [item.strip() for item in next(reader, []) if item.strip()]


def join_csv_list(items: List[str]) -> str:
    """Join a list of strings into a comma-separated string for display."""
    return ", ".join(item.strip() for item in items if item.strip())


def clean_terms(items: List[str]) -> Tuple[List[str], bool]:
    """Clean list entries by stripping invalid characters and hyphens."""
    cleaned: List[str] = []
    changed = False
    for item in items:
        new = re.sub(r"[^A-Za-z0-9 ,]", "", item).replace("-", "").strip()
        new = re.sub(r"\s+", " ", new)
        if new != item.strip(): changed = True
        if new: cleaned.append(new)
    return cleaned, changed


def get_allowed_colours() -> List[str]:
    """Return the list of allowed Etsy colour values."""
    return ALLOWED_COLOURS.copy()


# ===========================================================================
# 8. SKU Management
# ===========================================================================

def infer_sku_from_filename(filename: str) -> Optional[str]:
    """Infer SKU from an SEO filename using 'RJC-XXXX' at the end."""
    m = re.search(r"RJC-([A-Za-z0-9-]+)(?:\.jpg)?$", filename or "")
    return f"RJC-{m.group(1)}" if m else None


def sync_filename_with_sku(seo_filename: str, sku: str) -> str:
    """Return SEO filename updated so the SKU matches the given value."""
    if not seo_filename or not sku: return seo_filename
    return re.sub(r"RJC-[A-Za-z0-9-]+(?=\.jpg$)", sku, seo_filename)


def assign_or_get_sku(listing_json_path: Path, tracker_path: Path, *, force: bool = False) -> str:
    """Return existing SKU or assign the next sequential one."""
    data = load_json_file_safe(listing_json_path)
    if not force and data.get("sku"):
        return data["sku"]
    
    sku = get_next_sku(tracker_path)
    data["sku"] = sku
    if data.get("seo_filename"):
        data["seo_filename"] = sync_filename_with_sku(data["seo_filename"], sku)
    
    with open(listing_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Assigned SKU %s to %s", sku, listing_json_path.name)
    return sku


# ===========================================================================
# 9. Artwork Registry & File Management
# ===========================================================================

def find_seo_folder_from_filename(aspect: str, filename: str) -> str:
    """Return the best matching SEO folder for ``filename``."""
    # This is a simplified version. A full implementation would be needed.
    return "example-seo-folder"


def resolve_listing_paths(aspect: str, filename: str, allow_locked: bool = False) -> Tuple[str, Path, Path, bool]:
    """Return the folder, listing path, and finalised status for an artwork."""
    seo_folder = find_seo_folder_from_filename(aspect, filename)
    slug = seo_folder.replace("LOCKED-", "")
    listing_name = config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=slug)

    # Search in order of preference
    search_paths = [
        (config.PROCESSED_ROOT / seo_folder, False),
        (config.FINALISED_ROOT / seo_folder, True)
    ]
    if allow_locked:
        search_paths.append((config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}", True))

    for folder_path, is_finalised in search_paths:
        listing_file = folder_path / listing_name
        if listing_file.exists():
            return seo_folder, folder_path, listing_file, is_finalised

    raise FileNotFoundError(f"Listing file for {filename} not found in any location.")


def update_listing_paths(listing: Path, old_base: Path, new_base: Path) -> None:
    """Replace base path strings inside a listing JSON when folders move."""
    if not listing.exists(): return
    data = load_json_file_safe(listing)
    old_rel = relative_to_base(old_base)
    new_rel = relative_to_base(new_base)
    def _swap(p: str) -> str: return p.replace(old_rel, new_rel)
    
    # Update all relevant path keys
    for key in ("main_jpg_path", "orig_jpg_path", "thumb_jpg_path", "processed_folder"):
        if isinstance(data.get(key), str): data[key] = _swap(data[key])
    if isinstance(data.get("images"), list):
        data["images"] = [_swap(img) for img in data["images"] if isinstance(img, str)]
    
    with open(listing, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_unanalysed_subfolder() -> Path:
    """Create a new, uniquely named subfolder for uploads."""
    # This is a simplified version. A full implementation would be needed.
    folder = config.UNANALYSED_ROOT / "unanalysed-01"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def cleanup_unanalysed_folders() -> None:
    """Delete any empty ``unanalysed-*`` folders."""
    # This is a simplified version. A full implementation would be needed.
    pass


def register_new_artwork(uid: str, filename: str, folder: Path, assets: list, status: str, base: str):
    """Add a new artwork record to the registry."""
    # This is a simplified version. A full implementation would be needed.
    pass


def get_record_by_base(base: str) -> tuple[str, dict] | tuple[None, None]:
    """Find a registry record by its unique base name."""
    # This is a simplified version. A full implementation would be needed.
    return None, None


def move_and_log(src: Path, dest: Path, uid: str, status: str):
    """Move a file and update its record in the central registry."""
    # This is a simplified version. A full implementation would be needed.
    pass


def update_status(uid: str, folder: Path, status: str):
    """Update the status of an artwork in the registry."""
    # This is a simplified version. A full implementation would be needed.
    pass
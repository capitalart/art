# routes/utils.py
"""
Central utility functions for the ArtNarrator Flask application.

This module provides helpers for file operations, data manipulation, image
processing, and interacting with the application's file-based data stores.

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
import time, os, json, random, re, logging, shutil, datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Iterable
from helpers.listing_utils import resolve_listing_paths

from dotenv import load_dotenv
from flask import session
from PIL import Image
try:
    import cv2
except Exception:  # pragma: no cover - optional dependency
    cv2 = None
import numpy as np

import config
from utils.sku_assigner import get_next_sku, peek_next_sku

load_dotenv()
Image.MAX_IMAGE_PIXELS = None
logger = logging.getLogger(__name__)
LOGS_DIR = getattr(config, "LOGS_DIR", Path("/tmp/logs"))

ALLOWED_COLOURS = sorted(config.ETSY_COLOURS.keys())
ALLOWED_COLOURS_LOWER = {c.lower(): c for c in ALLOWED_COLOURS}


# ===========================================================================
# 2. JSON & File Helpers
# ===========================================================================

def load_json_file_safe(path: Path) -> dict:
    """Return JSON from ``path`` handling any errors gracefully."""
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        logger.warning("created new empty file %s", path)
        return {}

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        path.write_text("{}", encoding="utf-8")
        logger.warning("reset to {} for %s", path)
        return {}

    try:
        return json.loads(text)
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Invalid JSON in %s: %s", path, exc)
        path.write_text("{}", encoding="utf-8")
        return {}


def read_generic_text(aspect: str) -> str:
    """Return the generic text block for the given aspect ratio."""
    path = config.GENERIC_TEXTS_DIR / f"{aspect}.txt"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        logger.warning(f"Generic text for {aspect} not found at {path}")
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
    if cv2 is None:
        raise RuntimeError("cv2 library is required for perspective transform")
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

def get_all_artworks() -> List[Dict]:
    """Scans all artwork locations and returns a unified list of artwork dictionaries."""
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

def list_processed_artworks() -> Tuple[List[Dict], set]:
    processed_artworks = [a for a in get_all_artworks() if a['status'] == 'processed']
    processed_filenames = {a['filename'] for a in processed_artworks}
    return processed_artworks, processed_filenames

def list_finalised_artworks() -> List[Dict]:
    return [a for a in get_all_artworks() if a['status'] == 'finalised']

def list_ready_to_analyze(processed_filenames: set) -> List[Dict]:
    """Return artworks uploaded but not yet analyzed."""
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

def latest_analyzed_artwork() -> Optional[Dict[str, str]]:
    """Return info about the most recently analysed artwork."""
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


def latest_composite_folder() -> str | None:
    """Return the name of the most recently modified folder in PROCESSED_ROOT."""
    processed_dir = config.PROCESSED_ROOT
    if not processed_dir.exists():
        return None

    sub_folders = [d for d in processed_dir.iterdir() if d.is_dir()]
    if not sub_folders:
        return None

    latest_folder = max(sub_folders, key=lambda d: d.stat().st_mtime)
    return latest_folder.name


def find_aspect_filename_from_seo_folder(seo_folder: str) -> Optional[Tuple[str, str]]:
    """Return aspect ratio and filename for a given SEO folder."""
    for base in (config.PROCESSED_ROOT, config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT):
        folder = base / seo_folder
        listing = folder / f"{seo_folder}-listing.json"
        aspect = ""
        filename = ""
        if listing.exists():
            try:
                data = json.loads(listing.read_text())
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
            except Exception as exc:  # pragma: no cover - unexpected IO
                logging.error("Failed reading listing for %s: %s", seo_folder, exc)

        if folder.exists() and not filename:
            for p in folder.iterdir():
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"} and p.stem.lower() == seo_folder.lower():
                    filename = p.name
                    break

        if filename:
            if not filename.lower().endswith(".jpg"):
                filename = f"{Path(filename).stem}.jpg"
            disk_file = folder / filename
            if not disk_file.exists():
                stem = Path(filename).stem.lower()
                for p in folder.iterdir():
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png"} and p.stem.lower() == stem:
                        filename = p.name
                        break
            return aspect, filename
    return None

def populate_artwork_data_from_json(data: dict, seo_folder: str) -> dict:
    """Populates a dictionary with artwork details from a listing JSON."""
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
        "generic_text": read_generic_text(data.get("aspect_ratio", ""))
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
    aspect = "4x5"  # Default aspect for selector, can be made dynamic later
    cats = get_mockup_categories(config.MOCKUPS_CATEGORISED_DIR / aspect)
    session["slots"] = [{"category": c, "image": random_image(c, aspect)} for c in cats]

def compute_options(slots) -> List[List[str]]:
    """Return category options for each slot."""
    aspect = "4x5"  # Default aspect for selector
    cats = get_mockup_categories(config.MOCKUPS_CATEGORISED_DIR / aspect)
    return [cats for _ in slots]

def get_mockups(seo_folder: str) -> list:
    """Return mockup entries from the listing JSON."""
    try:
        _, _, listing_file, _ = resolve_listing_paths("", seo_folder, allow_locked=True)
        data = load_json_file_safe(listing_file)
        return data.get("mockups", [])
    except Exception as exc:
        logger.error(f"Failed reading mockups for {seo_folder}: {exc}")
        return []

def swap_one_mockup(seo_folder: str, slot_idx: int, new_category: str, current_mockup_src: str | None = None) -> tuple[bool, str, str]:
    """Swap a mockup to a new category and regenerate."""
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


# ===========================================================================
# 7. Text & String Manipulation
# ===========================================================================
def slugify(text: str) -> str:
    text = re.sub(r"[^\w\- ]+", "", text).strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()

def prettify_slug(slug: str) -> str:
    name = os.path.splitext(slug)[0].replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", name).title()

def parse_csv_list(text: str) -> List[str]:
    if not text: return []
    reader = csv.reader([text], skipinitialspace=True)
    return [item.strip() for item in next(reader, []) if item.strip()]

def join_csv_list(items: List[str]) -> str:
    return ", ".join(item.strip() for item in items if item.strip())

def clean_terms(items: List[str]) -> Tuple[List[str], bool]:
    cleaned: List[str] = []
    changed = False
    for item in items:
        new = re.sub(r"[^A-Za-z0-9 ,]", "", item).replace("-", "").strip()
        new = re.sub(r"\s+", " ", new)
        if new != item.strip(): changed = True
        if new: cleaned.append(new)
    return cleaned, changed

def get_allowed_colours() -> List[str]:
    return ALLOWED_COLOURS.copy()


# ===========================================================================
# 8. SKU Management
# ===========================================================================
def infer_sku_from_filename(filename: str) -> Optional[str]:
    m = re.search(r"RJC-([A-Za-z0-9-]+)(?:\.jpg)?$", filename or "")
    return f"RJC-{m.group(1)}" if m else None

def sync_filename_with_sku(seo_filename: str, sku: str) -> str:
    if not seo_filename or not sku: return seo_filename
    return re.sub(r"RJC-[A-Za-z0-9-]+(?=\.jpg$)", sku, seo_filename)

def assign_or_get_sku(listing_json_path: Path, tracker_path: Path, *, force: bool = False) -> str:
    data = load_json_file_safe(listing_json_path)
    if not force and data.get("sku"): return data["sku"]
    sku = get_next_sku(tracker_path)
    data["sku"] = sku
    if data.get("seo_filename"):
        data["seo_filename"] = sync_filename_with_sku(data["seo_filename"], sku)
    with open(listing_json_path, "w") as f: json.dump(data, f, indent=2)
    return sku

# ===========================================================================
# 8.1. SKU Validation Helper for Testing
# ===========================================================================
def validate_all_skus(entries: List[dict], tracker_path: Path) -> List[str]:
    """
    Validate SKUs for format, duplicates, and gaps.
    """
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
            # Extract number for gap detection
            num = int(sku.split('-')[-1])
            sku_numbers.append(num)
        except (ValueError, IndexError):
            errors.append(f"Could not parse SKU number: {sku}")

    # Check for gaps
    if sku_numbers:
        sku_numbers.sort()
        for i in range(len(sku_numbers) - 1):
            if sku_numbers[i+1] != sku_numbers[i] + 1:
                errors.append(f"Gap detected in SKUs between {sku_numbers[i]} and {sku_numbers[i+1]}")
                break # Only report the first gap

    return errors


# ===========================================================================
# 9. Artwork Registry & File Management
# ===========================================================================

def _load_registry() -> dict:
    """Loads the master artwork JSON registry file."""
    return load_json_file_safe(config.OUTPUT_JSON)

def _save_registry(reg: dict) -> None:
    """Writes data to the master artwork JSON registry atomically."""
    tmp = config.OUTPUT_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, config.OUTPUT_JSON)

def register_new_artwork(uid: str, filename: str, folder: Path, assets: list, status: str, base: str):
    """Add a new artwork record to the registry."""
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

def move_and_log(src: Path, dest: Path, uid: str, status: str):
    """Move a file and update its record in the central registry."""
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

def update_status(uid: str, folder: Path, status: str):
    """Update the status of an artwork in the registry."""
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

def get_record_by_base(base: str) -> tuple[str | None, dict | None]:
    """Find a registry record by its unique base name."""
    reg = _load_registry()
    for uid, rec in reg.items():
        if rec.get("base") == base:
            return uid, rec
    return None, None

def get_record_by_seo_filename(filename: str) -> tuple[str | None, dict | None]:
    """Find a registry record by its SEO filename."""
    reg = _load_registry()
    for uid, rec in reg.items():
        if rec.get("seo_filename") == filename:
            return uid, rec
    return None, None

def remove_record_from_registry(uid: str) -> bool:
    """Safely remove a record from the master JSON registry by its UID."""
    if not uid: return False
    reg = _load_registry()
    if uid in reg:
        del reg[uid]
        _save_registry(reg)
        logger.info(f"Removed record {uid} from registry.")
        return True
    return False

def find_seo_folder_from_filename(aspect: str, filename: str) -> str:
    """Return the best matching SEO folder for ``filename``."""
    basename = Path(filename).stem.lower().replace('-thumb', '').replace('-analyse', '')
    candidates: list[tuple[float, str]] = []
    for base in (config.PROCESSED_ROOT, config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT):
        if not base.exists(): continue
        for folder in base.iterdir():
            if not folder.is_dir(): continue
            slug = folder.name.replace("LOCKED-", "")
            listing_file = folder / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=slug)
            if listing_file.exists():
                data = load_json_file_safe(listing_file)
                stems_to_check = { Path(data.get(k, "")).stem.lower() for k in ("filename", "seo_filename")} | {slug.lower()}
                if basename in stems_to_check:
                    candidates.append((listing_file.stat().st_mtime, slug))
    if not candidates: raise FileNotFoundError(f"SEO folder not found for {filename}")
    return max(candidates, key=lambda x: x[0])[1]

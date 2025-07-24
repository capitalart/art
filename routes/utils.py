# This file now references all path, directory, and filename variables strictly from config.py. No local or hardcoded path constants remain.
import os
import json
import random
import re
import logging
import csv
import fcntl
import shutil
import datetime
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
    UNANALYSED_ROOT,
    PROCESSED_ROOT,
    SELECTIONS_DIR,
    COMPOSITES_DIR,
    FINALISED_ROOT,
    ARTWORK_VAULT_ROOT,
    LOGS_DIR,
    MOCKUPS_INPUT_DIR,
    ANALYSE_MAX_DIM,
    GENERIC_TEXTS_DIR,
    COORDS_DIR,
    ANALYZE_SCRIPT_PATH,
    GENERATE_SCRIPT_PATH,
    FILENAME_TEMPLATES,
    OUTPUT_JSON,
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
    UNANALYSED_ROOT,
    MOCKUPS_INPUT_DIR,
    PROCESSED_ROOT,
    SELECTIONS_DIR,
    COMPOSITES_DIR,
    FINALISED_ROOT,
    LOGS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# JSON File Helpers
# ============================================================================

def load_json_file_safe(path: Path) -> dict:
    """Return JSON from ``path`` handling any errors gracefully."""

    logger = logging.getLogger(__name__)
    path = Path(path)

    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
            logger.warning("Missing %s - created new empty file", path)
            return {}

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            path.write_text("{}")
            logger.warning("Empty JSON file %s - reset to {}", path)
            return {}

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in %s: %s", path, exc)
            path.write_text("{}")
            return {}
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Failed handling %s: %s", path, exc)
        return {}

# ==============================
# Utility Helpers
# ==============================

def get_mockup_categories(aspect_folder: Path | str) -> List[str]:
    """Return sorted list of category folder names under ``aspect_folder``.

    Hidden folders and files are ignored.
    """
    folder = Path(aspect_folder)
    if not folder.exists():
        return []
    return sorted(
        f.name
        for f in folder.iterdir()
        if f.is_dir() and not f.name.startswith(".")
    )


def get_categories() -> List[str]:
    """Return sorted list of mockup categories from the root directory."""
    return get_mockup_categories(MOCKUPS_INPUT_DIR)


def random_image(category: str) -> Optional[str]:
    """Return a random image filename for the given category."""
    cat_dir = MOCKUPS_INPUT_DIR / category
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
    for folder in PROCESSED_ROOT.iterdir():
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
    for folder in PROCESSED_ROOT.iterdir():
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
    for folder in PROCESSED_ROOT.iterdir():
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
    for qc_path in UNANALYSED_ROOT.glob("**/*.qc.json"):
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
    if FINALISED_ROOT.exists():
        for folder in FINALISED_ROOT.iterdir():
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
    for base in (FINALISED_ROOT, ARTWORK_VAULT_ROOT):
        if not base.exists():
            continue
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            slug = folder.name.removeprefix("LOCKED-")
            listing_file = folder / f"{slug}-listing.json"
            if not listing_file.exists():
                continue
            try:
                with open(listing_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            main_img = folder / f"{slug}.jpg"
            thumb_img = folder / f"{slug}-THUMB.jpg"
            items.append(
                {
                    "seo_folder": folder.name,
                    "title": data.get("title") or prettify_slug(slug),
                    "description": data.get("description", ""),
                    "sku": data.get("sku", ""),
                    "primary_colour": data.get("primary_colour", ""),
                    "secondary_colour": data.get("secondary_colour", ""),
                    "price": data.get("price", ""),
                    "seo_filename": data.get("seo_filename", f"{slug}.jpg"),
                    "tags": data.get("tags", []),
                    "materials": data.get("materials", []),
                    "aspect": data.get("aspect_ratio", ""),
                    "filename": data.get("filename", f"{slug}.jpg"),
                    "locked": data.get("locked", False),
                    "main_image": main_img.name if main_img.exists() else None,
                    "thumb": thumb_img.name if thumb_img.exists() else None,
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

    for base in (PROCESSED_ROOT, FINALISED_ROOT, ARTWORK_VAULT_ROOT):
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            slug = folder.name.removeprefix("LOCKED-")
            listing_file = folder / FILENAME_TEMPLATES["listing_json"].format(seo_slug=slug)
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
                slug.lower(),
                folder.name.lower(),
                slugify(Path(data.get("filename", "")).stem),
                slugify(Path(data.get("seo_filename", "")).stem),
                slugify(slug),
            }

            if basename in stems or slug_base in stems:
                candidates.append((listing_file.stat().st_mtime, slug))

    if not candidates:
        raise FileNotFoundError(f"SEO folder not found for {filename}")

    return max(candidates, key=lambda x: x[0])[1]


def regenerate_one_mockup(seo_folder: str, slot_idx: int) -> bool:
    """Regenerate a single mockup in-place."""
    folder = PROCESSED_ROOT / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    if not listing_file.exists():
        folder = FINALISED_ROOT / seo_folder
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
    aspect = data.get("aspect_ratio")
    mockup_root = MOCKUPS_INPUT_DIR / f"{aspect}-categorised"
    mockup_files = list((mockup_root / category).glob("*.png"))
    if not mockup_files:
        return False
    new_mockup = random.choice(mockup_files)
    coords_path = COORDS_DIR / aspect / f"{new_mockup.stem}.json"
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
    folder = PROCESSED_ROOT / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    if not listing_file.exists():
        folder = FINALISED_ROOT / seo_folder
        listing_file = folder / f"{seo_folder}-listing.json"
        if not listing_file.exists():
            return False
    with open(listing_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    mockups = data.get("mockups", [])
    if slot_idx < 0 or slot_idx >= len(mockups):
        return False
    aspect = data.get("aspect_ratio")
    mockup_root = MOCKUPS_INPUT_DIR / f"{aspect}-categorised"
    mockup_files = list((mockup_root / new_category).glob("*.png"))
    if not mockup_files:
        return False
    new_mockup = random.choice(mockup_files)
    coords_path = COORDS_DIR / aspect / f"{new_mockup.stem}.json"
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


def _listing_json_path(seo_folder: str) -> Path:
    """Return the listing JSON path for a SEO folder if it exists."""
    for base in (PROCESSED_ROOT, FINALISED_ROOT, ARTWORK_VAULT_ROOT):
        path = base / seo_folder / f"{seo_folder}-listing.json"
        if path.exists():
            return path
    raise FileNotFoundError(f"Listing file for {seo_folder} not found")


def get_mockups(seo_folder: str) -> list:
    """Return mockup entries from the listing JSON."""
    try:
        listing = _listing_json_path(seo_folder)
        with open(listing, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("mockups", [])
    except Exception as exc:  # noqa: BLE001
        logging.error("Failed reading mockups for %s: %s", seo_folder, exc)
        return []


def create_default_mockups(seo_folder: str) -> None:
    """Create a fallback mockup image and update the listing."""
    dest = PROCESSED_ROOT / seo_folder
    dest.mkdir(parents=True, exist_ok=True)
    default_src = config.STATIC_DIR / "img" / "default-mockup.jpg"
    target = dest / FILENAME_TEMPLATES["mockup"].format(seo_slug=seo_folder, num=1)
    shutil.copy(default_src, target)
    listing = _listing_json_path(seo_folder)
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
            logging.info("Default mockups created for %s", seo_folder)
        return True
    except Exception as exc:  # noqa: BLE001
        logging.error("Error generating mockups for %s: %s", seo_folder, exc)
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
    """Return True if the given path is within a finalised or locked folder."""
    p = Path(path).resolve()
    try:
        p.relative_to(FINALISED_ROOT)
        return True
    except Exception:
        pass
    try:
        p.relative_to(ARTWORK_VAULT_ROOT)
        return True
    except Exception:
        return False


def update_listing_paths(listing: Path, old_base: Path, new_base: Path) -> None:
    """Replace base path strings inside a listing JSON when folders move."""
    if not listing.exists():
        return
    try:
        with open(listing, "r", encoding="utf-8") as lf:
            data = json.load(lf)
    except Exception:
        return

    old_rel = relative_to_base(old_base)
    new_rel = relative_to_base(new_base)

    def _swap(p: str) -> str:
        return p.replace(old_rel, new_rel)

    for key in ("main_jpg_path", "orig_jpg_path", "thumb_jpg_path", "processed_folder"):
        if isinstance(data.get(key), str):
            data[key] = _swap(data[key])

    if isinstance(data.get("images"), list):
        data["images"] = [_swap(img) if isinstance(img, str) else img for img in data["images"]]

    with open(listing, "w", encoding="utf-8") as lf:
        json.dump(data, lf, indent=2, ensure_ascii=False)


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
    processed_dir = PROCESSED_ROOT / seo_folder
    final_dir = FINALISED_ROOT / seo_folder
    locked_dir = ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}"

    listing = processed_dir / f"{seo_folder}-listing.json"
    if listing.exists():
        return seo_folder, processed_dir, listing, False

    listing = final_dir / f"{seo_folder}-listing.json"
    if listing.exists():
        return seo_folder, final_dir, listing, True

    listing = locked_dir / f"{seo_folder}-listing.json"
    if listing.exists():
        return seo_folder, locked_dir, listing, True

    raise FileNotFoundError(f"Listing file for {filename} not found")


def find_aspect_filename_from_seo_folder(seo_folder: str) -> Optional[Tuple[str, str]]:
    """Return the aspect ratio and main filename for a given SEO folder.

    The lookup checks both processed and finalised folders. Information is
    primarily loaded from the listing JSON, but if fields are missing the
    filename is inferred from disk contents. Filenames are normalised to use a
    ``.jpg`` extension and to match the actual casing on disk when possible.
    """

    for base in (PROCESSED_ROOT, FINALISED_ROOT, ARTWORK_VAULT_ROOT):
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


# ---------------------------------------------------------------------------
# Artwork Registry & File Move Helpers
# ---------------------------------------------------------------------------

REGISTRY_PATH = OUTPUT_JSON


def _load_registry() -> dict:
    """Return registry JSON as a dictionary, resetting invalid data."""

    if not REGISTRY_PATH.exists():
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text("{}")

    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as rf:
            data = json.load(rf)
    except Exception:  # pragma: no cover - unexpected IO
        return {}

    # Historical versions stored a list which breaks ``dict`` usage.
    if not isinstance(data, dict):
        logging.getLogger(__name__).warning(
            "Registry file not a dict, resetting: %s", REGISTRY_PATH
        )
        return {}

    return data


def _save_registry(reg: dict) -> None:
    """Write the registry ``reg`` to disk atomically."""

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as tf:
        json.dump(reg, tf, indent=2, ensure_ascii=False)
    os.replace(tmp, REGISTRY_PATH)


def create_unanalysed_subfolder() -> Path:
    UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    existing = [p for p in UNANALYSED_ROOT.iterdir() if p.is_dir() and p.name.startswith("unanalysed-")]
    nums = [int(p.name.split("-")[-1]) for p in existing if p.name.split("-")[-1].isdigit()]
    next_num = max(nums, default=0) + 1
    folder = UNANALYSED_ROOT / f"unanalysed-{next_num:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def cleanup_unanalysed_folders() -> None:
    """Delete any empty ``unanalysed-*`` folders under :data:`UNANALYSED_ROOT`."""

    root = UNANALYSED_ROOT.resolve()
    for folder in root.glob("unanalysed-*"):
        if not folder.is_dir():
            continue
        try:
            folder_resolved = folder.resolve()
            if folder_resolved.is_relative_to(root) and not any(folder_resolved.iterdir()):
                shutil.rmtree(folder_resolved, ignore_errors=True)
        except Exception as exc:  # pragma: no cover - unexpected IO
            logging.getLogger(__name__).error("Failed cleaning %s: %s", folder, exc)


def move_and_log(src: Path, dest: Path, uid: str, status: str) -> None:
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


def update_status(uid: str, folder: Path, status: str) -> None:
    reg = _load_registry()
    rec = reg.get(uid)
    if not rec:
        return
    rec.setdefault("history", []).append({
        "status": status,
        "folder": str(folder),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    rec["current_folder"] = str(folder)
    rec["status"] = status
    reg[uid] = rec
    _save_registry(reg)


def register_new_artwork(uid: str, seo_filename: str, folder: Path, asset_files: list[str], status: str, base: str | None = None) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reg = _load_registry()
    reg[uid] = {
        "seo_filename": seo_filename,
        "base": base,
        "current_folder": str(folder),
        "assets": asset_files,
        "status": status,
        "history": [{"status": status, "folder": str(folder), "timestamp": ts}],
        "upload_date": ts,
    }
    _save_registry(reg)


def get_record_by_base(base: str) -> tuple[str, dict] | tuple[None, None]:
    reg = _load_registry()
    for uid, rec in reg.items():
        if rec.get("base") == base:
            return uid, rec
    return None, None


def get_record_by_seo_filename(seo_filename: str) -> tuple[str, dict] | tuple[None, None]:
    reg = _load_registry()
    for uid, rec in reg.items():
        if rec.get("seo_filename") == seo_filename:
            return uid, rec
    return None, None


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


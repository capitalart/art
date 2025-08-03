# helpers/listing_utils.py
"""
Utility functions specifically for handling artwork listing data, file paths,
and the creation of unanalysed artwork folders. This is a self-contained
module with no dependencies on the main Flask routes.

INDEX
-----
1.  Imports & Initialisation
2.  JSON & File Helpers
3.  Path Resolution & Folder Management
4.  Guided Description Writing System (GDWS) Helpers
"""

# ===========================================================================
# 1. Imports & Initialisation
# ===========================================================================
from __future__ import annotations
import logging
import json
from pathlib import Path
import re
import uuid

# Local application imports
import config

logger = logging.getLogger(__name__)


# ===========================================================================
# 2. JSON & File Helpers
# ===========================================================================

def load_json_file_safe(path: Path) -> dict:
    """
    Return JSON from ``path``, handling file-not-found and decoding errors gracefully.
    If the file doesn't exist or is empty/invalid, it creates a new empty JSON file.
    """
    path = Path(path)
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
            logger.warning(f"Created new empty JSON file at {path}")
        except OSError as e:
            logger.error(f"Failed to create directory or file at {path}: {e}")
            return {}
        return {}

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {path}, returning empty dict. Error: {e}")
        return {}


# ===========================================================================
# 3. Path Resolution & Folder Management
# ===========================================================================

def find_seo_folder_from_filename(aspect: str, filename: str) -> str:
    """
    Return the best matching SEO folder name for a given artwork filename.
    Scans processed, finalised, and locked directories to find a match.
    """
    basename = Path(filename).stem.lower().replace('-thumb', '').replace('-analyse', '')
    candidates: list[tuple[float, str]] = []

    for base in (config.PROCESSED_ROOT, config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT):
        if not base.exists():
            continue
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            
            slug = folder.name.replace("LOCKED-", "")
            listing_file = folder / f"{slug}-listing.json"
            
            if listing_file.exists():
                data = load_json_file_safe(listing_file)
                stems_to_check = { Path(data.get(k, "")).stem.lower() for k in ("filename", "seo_filename")} | {slug.lower()}
                if basename in stems_to_check:
                    candidates.append((listing_file.stat().st_mtime, slug))

    if not candidates:
        raise FileNotFoundError(f"Could not find a matching SEO folder for filename: {filename}")

    return max(candidates, key=lambda x: x[0])[1]


def resolve_listing_paths(
    aspect: str, filename: str, allow_locked: bool = False
) -> tuple[str, Path, Path, bool]:
    """
    Finds the correct paths for an artwork's folder and its listing.json file.
    This is the primary function for locating an artwork's assets regardless of its state.
    """
    try:
        seo_folder = find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        logger.warning(f"Could not resolve SEO folder for filename: {filename}")
        raise

    search_dirs = [config.PROCESSED_ROOT, config.FINALISED_ROOT]
    if allow_locked:
        search_dirs.append(config.ARTWORK_VAULT_ROOT)

    for base_dir in search_dirs:
        potential_folder = base_dir / seo_folder
        
        if base_dir == config.ARTWORK_VAULT_ROOT and not potential_folder.exists():
            potential_folder = base_dir / f"LOCKED-{seo_folder}"

        if potential_folder.exists():
            finalised = (base_dir == config.FINALISED_ROOT or base_dir == config.ARTWORK_VAULT_ROOT)
            listing_path = potential_folder / f"{seo_folder}-listing.json"

            if listing_path and listing_path.exists():
                return seo_folder, potential_folder, listing_path, finalised
            
    logger.error(f"Found folder for '{filename}' but missing its -listing.json file.")
    raise FileNotFoundError(f"Could not find listing JSON for artwork: {filename}")


def create_unanalysed_subfolder(original_filename: str) -> Path:
    """Creates a unique subfolder in the unanalysed directory for a new upload."""
    safe_base = re.sub(r'[^\w\-]+', '', Path(original_filename).stem).strip()
    unique_id = uuid.uuid4().hex[:8]
    folder_name = f"{safe_base}-{unique_id}"
    folder_path = config.UNANALYSED_ROOT / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


def cleanup_unanalysed_folders():
    """Removes empty subfolders from the unanalysed artwork directory."""
    for item in config.UNANALYSED_ROOT.iterdir():
        if item.is_dir() and not any(item.iterdir()):
            try:
                item.rmdir()
                logger.info(f"Cleaned up empty unanalysed folder: {item.name}")
            except OSError as e:
                logger.warning(f"Could not remove empty folder {item.name}: {e}")


# ===========================================================================
# 4. Guided Description Writing System (GDWS) Helpers | helpers-listing-utils-py-4
# ===========================================================================
# FIX: Added the missing assemble_gdws_description function.

def assemble_gdws_description(aspect_ratio: str) -> str:
    """
    Assembles a full artwork description from the GDWS content blocks.
    It respects the pinned and custom order of paragraphs.

    Args:
        aspect_ratio: The aspect ratio folder to read from (e.g., '4x5').

    Returns:
        A single string containing the fully assembled description, or an
        empty string if no content is found.
    """
    aspect_path = config.GDWS_CONTENT_DIR / aspect_ratio
    if not aspect_path.exists():
        logger.warning(f"GDWS content directory not found for aspect ratio: {aspect_ratio}")
        return ""

    all_blocks = {}
    for folder_path in [p for p in aspect_path.iterdir() if p.is_dir()]:
        base_file = folder_path / "base.json"
        if base_file.exists():
            try:
                data = load_json_file_safe(base_file)
                all_blocks[data['title']] = data
            except Exception as e:
                logger.error(f"Error loading GDWS base file {base_file}: {e}")

    pinned_start = config.GDWS_CONFIG["PINNED_START_TITLES"]
    pinned_end = config.GDWS_CONFIG["PINNED_END_TITLES"]
    order_file = aspect_path / "order.json"

    # Build the final ordered list of titles
    final_order = [title for title in pinned_start if title in all_blocks]
    
    middle_order = []
    if order_file.exists():
        try:
            middle_order = load_json_file_safe(order_file)
        except Exception:
            logger.error(f"Could not read or parse order.json for {aspect_ratio}")
    
    # Add ordered middle blocks
    final_order.extend([title for title in middle_order if title in all_blocks and title not in final_order])
    
    # Add any remaining (unpinned, unordered) blocks
    remaining = [title for title in all_blocks if title not in final_order and title not in pinned_end]
    final_order.extend(sorted(remaining)) # Sort alphabetically for consistency
    
    # Add pinned end blocks
    final_order.extend([title for title in pinned_end if title in all_blocks])

    # Assemble the description string
    description_parts = []
    for title in final_order:
        block = all_blocks.get(title)
        if block:
            description_parts.append(f"{block['title']}\n\n{block['content']}")

    # Join with the standard separator
    return "\n\n---\n\n".join(description_parts)
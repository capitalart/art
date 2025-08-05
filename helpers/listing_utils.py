# helpers/listing_utils.py
"""
Utility functions specifically for managing artwork listings, including
file operations, path resolution, and data manipulation that are shared
across different routes and scripts.

Table of Contents (ToC)
-----------------------
[listing-utils-py-1] Imports
[listing-utils-py-2] JSON & State Management
    [listing-utils-py-2a] Safely Load JSON File
    [listing-utils-py-2b] Update Artwork Registry (Placeholder)
    [listing-utils-py-2c] Remove Artwork from Registry (Placeholder)

[listing-utils-py-3] Path & File Operations
    [listing-utils-py-3a] Resolve Listing Paths
    [listing-utils-py-3b] Create Unanalysed Subfolder
    [listing-utils-py-3c] Cleanup Empty Unanalysed Folders
    [listing-utils-py-3d] Delete Artwork (All Stages)

[listing-utils-py-4] Data Generation
    [listing-utils-py-4a] Assemble GDWS Description
    [listing-utils-py-4b] Resolve Artwork Stage
    [listing-utils-py-4c] Generate Public Image URLs
"""

# === [ Section 1: Imports | listing-utils-py-1 ] ===
# Handles all necessary library imports for the module.
# ---------------------------------------------------------------------------------
from __future__ import annotations
import json
import logging
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
import re
import datetime

import config

logger = logging.getLogger(__name__)


# === [ Section 2: JSON & State Management | listing-utils-py-2 ] ===
# Contains functions for safely reading and writing to JSON files that
# manage the application's state, such as listing data.
# ---------------------------------------------------------------------------------

# --- [ 2a: Safely Load JSON File | listing-utils-py-2a ] ---
def load_json_file_safe(file_path: Path) -> dict:
    """Safely loads a JSON file, returning an empty dict if it's missing, empty, or invalid."""
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}. Creating new empty JSON file.")
        file_path.write_text("{}", encoding="utf-8")
        return {}
    try:
        content = file_path.read_text(encoding="utf-8").strip()
        if not content:
            logger.warning(f"File is empty: {file_path}. Resetting to {{}}.")
            file_path.write_text("{}", encoding="utf-8")
            return {}
        return json.loads(content)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {file_path}. Backing up and resetting.")
        backup_path = file_path.with_suffix(f"{file_path.suffix}.bak")
        shutil.copy(file_path, backup_path)
        file_path.write_text("{}", encoding="utf-8")
        return {}

# --- [ 2b: Update Artwork Registry (Placeholder) | listing-utils-py-2b ] ---
def update_artwork_registry(seo_folder: str, new_path: Path, new_status: str):
    """Placeholder for updating a central artwork state registry."""
    logger.info(f"Registry updated for '{seo_folder}': status='{new_status}', path='{new_path}'")

# --- [ 2c: Remove Artwork from Registry (Placeholder) | listing-utils-py-2c ] ---
def remove_artwork_from_registry(seo_folder: str):
    """Placeholder for removing an artwork from a central state registry."""
    logger.info(f"Registry record removed for '{seo_folder}'")


# === [ Section 3: Path & File Operations | listing-utils-py-3 ] ===
# Core functions for handling the filesystem, including finding, creating,
# and deleting artwork folders and files across all workflow stages.
# ---------------------------------------------------------------------------------

# --- [ 3a: Resolve Listing Paths | listing-utils-py-3a ] ---
def resolve_listing_paths(aspect: str, filename: str, allow_locked: bool = False) -> Tuple[str, Path, Path, bool]:
    """Finds an artwork's folder and listing.json across all possible directories."""
    base_name = Path(filename).stem
    search_dirs = [config.PROCESSED_ROOT, config.FINALISED_ROOT]
    if allow_locked:
        search_dirs.append(config.ARTWORK_VAULT_ROOT)

    for directory in search_dirs:
        folder_name = f"LOCKED-{base_name}" if directory == config.ARTWORK_VAULT_ROOT else base_name
        folder_path = directory / folder_name
        
        if folder_path.is_dir():
            listing_path = folder_path / f"{base_name}-listing.json"
            if listing_path.exists():
                is_finalised = directory in [config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT]
                return base_name, folder_path, listing_path, is_finalised
                
    raise FileNotFoundError(f"Could not find listing folder or JSON for '{filename}'")

# --- [ 3b: Create Unanalysed Subfolder | listing-utils-py-3b ] ---
def create_unanalysed_subfolder(original_filename: str) -> Path:
    """Creates a unique subfolder in the unanalysed directory for a new upload."""
    safe_base = re.sub(r"[^\w\-.]+", "", Path(original_filename).stem).strip().lower()
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    folder_name = f"{safe_base}-{timestamp}"
    folder_path = config.UNANALYSED_ROOT / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path

# --- [ 3c: Cleanup Empty Unanalysed Folders | listing-utils-py-3c ] ---
def cleanup_unanalysed_folders():
    """Removes any empty subfolders from the unanalysed artwork directory."""
    for item in config.UNANALYSED_ROOT.iterdir():
        if item.is_dir() and not any(item.iterdir()):
            shutil.rmtree(item)
            logger.info(f"Cleaned up empty unanalysed folder: {item.name}")

# --- [ 3d: Delete Artwork (All Stages) | listing-utils-py-3d ] ---
def delete_artwork(seo_folder: str) -> bool:
    """Deletes all versions of an artwork (unanalysed, processed, finalised, and locked)."""
    found_and_deleted = False
    
    # Define paths for all possible stages
    unanalysed_path = config.UNANALYSED_ROOT / seo_folder 
    processed_path = config.PROCESSED_ROOT / seo_folder
    finalised_path = config.FINALISED_ROOT / seo_folder
    locked_path = config.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}"

    for path in [unanalysed_path, processed_path, finalised_path, locked_path]:
        if path.exists() and path.is_dir():
            try:
                shutil.rmtree(path)
                logger.info(f"Successfully deleted artwork folder: {path}")
                found_and_deleted = True
            except OSError as e:
                logger.error(f"Error deleting folder {path}: {e}")
                return False # Stop immediately on error

    if found_and_deleted:
        remove_artwork_from_registry(seo_folder)
        
    return found_and_deleted


# === [ Section 4: Data Generation | listing-utils-py-4 ] ===
# Functions responsible for creating or assembling data, such as descriptions
# from fragments or generating lists of public-facing URLs.
# ---------------------------------------------------------------------------------

# --- [ 4a: Assemble GDWS Description | listing-utils-py-4a ] ---
def assemble_gdws_description(aspect_ratio: str) -> str:
    """Assembles a full product description from GDWS content blocks."""
    aspect_path = config.GDWS_CONTENT_DIR / aspect_ratio
    if not aspect_path.exists():
        return "Standard product description."

    all_blocks = {}
    for folder_path in aspect_path.iterdir():
        if folder_path.is_dir():
            base_file = folder_path / "base.json"
            if base_file.exists():
                try:
                    data = json.loads(base_file.read_text(encoding='utf-8'))
                    all_blocks[data['title']] = data['content']
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Could not parse GDWS block {base_file}: {e}")

    pinned_start = config.GDWS_CONFIG["PINNED_START_TITLES"]
    pinned_end = config.GDWS_CONFIG["PINNED_END_TITLES"]
    start_content = [all_blocks.pop(title, '') for title in pinned_start]
    end_content = [all_blocks.pop(title, '') for title in pinned_end]

    middle_content = []
    order_file = aspect_path / "order.json"
    if order_file.exists():
        try:
            order = json.loads(order_file.read_text(encoding='utf-8'))
            for title in order:
                if title in all_blocks:
                    middle_content.append(all_blocks.pop(title))
        except json.JSONDecodeError:
            logger.error(f"Could not parse order.json for {aspect_ratio}")
    
    middle_content.extend(all_blocks.values())
    full_description = "\n\n---\n\n".join(filter(None, start_content + middle_content + end_content))
    return full_description

# --- [ 4b: Resolve Artwork Stage | listing-utils-py-4b ] ---
def resolve_artwork_stage(seo_folder: str) -> Tuple[Optional[str], Optional[Path]]:
    """Determines the current stage (e.g., 'processed') and path of an artwork."""
    clean_folder = seo_folder.replace("LOCKED-", "")
    if (p := config.PROCESSED_ROOT / clean_folder).exists(): return "processed", p
    if (p := config.FINALISED_ROOT / clean_folder).exists(): return "finalised", p
    if (p := config.ARTWORK_VAULT_ROOT / f"LOCKED-{clean_folder}").exists(): return "vault", p
    if (p := config.UNANALYSED_ROOT / clean_folder).exists(): return "unanalysed", p
    return None, None

# --- [ 4c: Generate Public Image URLs | listing-utils-py-4c ] ---
def generate_public_image_urls(seo_folder: str, stage: str) -> List[str]:
    """
    Generates a specific, ordered list of 11 public image URLs for a listing.
    Order: 1 Main Artwork, 9 Mockups, 1 Main Thumbnail.
    """
    stage_map = {"processed": config.PROCESSED_ROOT, "finalised": config.FINALISED_ROOT, "vault": config.ARTWORK_VAULT_ROOT}
    base_dir = stage_map.get(stage)
    if not base_dir: return []

    folder_name = f"LOCKED-{seo_folder}" if stage == "vault" else seo_folder
    folder_path = base_dir / folder_name
    if not folder_path.exists(): return []

    all_jpgs = sorted(list(folder_path.glob("*.jpg")))
    
    main_image = None
    main_thumb = None
    mockups = []
    
    for jpg in all_jpgs:
        if "-MU-" in jpg.name:
            mockups.append(jpg)
        elif jpg.name.endswith("-THUMB.jpg"):
            main_thumb = jpg
        elif not jpg.name.endswith("-ANALYSE.jpg"):
            main_image = jpg
    
    final_urls = []
    if main_image:
        final_urls.append(config.resolve_image_url(main_image))
    
    final_urls.extend([config.resolve_image_url(m) for m in sorted(mockups)[:9]])

    if main_thumb:
        final_urls.append(config.resolve_image_url(main_thumb))
            
    return final_urls
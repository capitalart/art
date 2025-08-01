"""Listing workflow helper functions.

This module centralises small utilities used across the
Flask routes and CLI scripts. Keeping them here avoids
circular imports and duplication between modules.

INDEX
-----
1.  Imports & Initialisation
2.  Unanalysed Folder Helpers
3.  Listing Path Resolution
4.  GDWS Description Assembly
"""

# ===========================================================================
# 1. Imports & Initialisation
# ===========================================================================
from __future__ import annotations
import json
import logging
import random
import re
import shutil
import uuid
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# ===========================================================================
# 2. Unanalysed Folder Helpers
# ===========================================================================

def slugify(text: str) -> str:
    """Return a slug suitable for filenames."""
    text = re.sub(r"[^\w\- ]+", "", text).strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()


def create_unanalysed_subfolder(filename: str) -> Path:
    """Create and return a new subfolder in unanalysed-artwork based on the filename."""
    root = config.UNANALYSED_ROOT
    root.mkdir(parents=True, exist_ok=True)
    
    # Create a safe folder name from the original filename + a unique ID
    safe_name = slugify(Path(filename).stem)
    unique_id = uuid.uuid4().hex[:8]
    folder_name = f"{safe_name}-{unique_id}"
    
    folder = root / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def cleanup_unanalysed_folders() -> None:
    """Remove any empty ``unanalysed-*`` folders."""
    root = config.UNANALYSED_ROOT.resolve()
    for folder in root.iterdir():
        if folder.is_dir() and not any(folder.iterdir()):
            shutil.rmtree(folder, ignore_errors=True)

# ===========================================================================
# 3. Listing Path Resolution
# ===========================================================================

def resolve_listing_paths(aspect: str, filename: str, allow_locked: bool = False) -> tuple[str, Path, Path, bool]:
    """
    Directly resolves artwork paths based on the filename stem, which is assumed
    to be the unique folder name. This is a fast and direct lookup.
    """
    if not filename:
        raise FileNotFoundError("Filename cannot be empty.")

    # The folder name is simply the filename without the '.jpg' extension.
    seo_folder = Path(filename).stem
    
    # Define the potential locations for the folder
    potential_dirs = {
        "processed": config.PROCESSED_ROOT / seo_folder,
        "finalised": config.FINALISED_ROOT / seo_folder,
        "locked": config.ARTWORK_VAULT_ROOT / seo_folder,
    }

    found_path = None
    state_finalised = False
    
    # Check each location in order
    if potential_dirs["processed"].exists():
        found_path = potential_dirs["processed"]
    elif potential_dirs["finalised"].exists():
        found_path = potential_dirs["finalised"]
        state_finalised = True
    elif allow_locked and potential_dirs["locked"].exists():
        found_path = potential_dirs["locked"]
        state_finalised = True
    
    if not found_path:
        raise FileNotFoundError(f"Could not find artwork folder for: {seo_folder}")

    # The listing JSON name is also based on the folder name
    listing_path = found_path / f"{seo_folder}-listing.json"
    if not listing_path.exists():
        raise FileNotFoundError(f"Listing JSON not found in {found_path}")

    # The main image path is also derived from the folder name
    image_path = found_path / f"{seo_folder}.jpg"

    return seo_folder, found_path, listing_path, state_finalised

# ===========================================================================
# 4. GDWS Description Assembly
# ===========================================================================

def assemble_gdws_description(aspect_ratio: str) -> str:
    """Build a full description from the Guided Description Writing System (GDWS)."""
    description_parts: list[str] = []
    aspect_path = config.GDWS_CONTENT_DIR / aspect_ratio
    if not aspect_path.exists():
        logger.warning("GDWS content directory for '%s' not found.", aspect_ratio)
        return ""

    paragraph_folders = sorted([p for p in aspect_path.iterdir() if p.is_dir()])
    for folder_path in paragraph_folders:
        variations = list(folder_path.glob("*.json"))
        if not variations:
            continue
        chosen_variation_path = random.choice(variations)
        try:
            data = json.loads(chosen_variation_path.read_text(encoding="utf-8"))
            if data.get("content"):
                description_parts.append(data["content"])
        except Exception as exc:
            logger.error("Failed to load GDWS variation %s: %s", chosen_variation_path, exc)

    logger.info(
        "Assembled description from %d GDWS paragraphs for '%s'.",
        len(description_parts),
        aspect_ratio,
    )
    return "\n\n".join(description_parts)
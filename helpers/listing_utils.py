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
import shutil
import re
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
    for folder in root.iterdir(): # Check all folders, not just numbered ones
        if folder.is_dir() and not any(folder.iterdir()):
            shutil.rmtree(folder, ignore_errors=True)

# ===========================================================================
# 3. Listing Path Resolution
# ===========================================================================

def resolve_listing_paths(aspect: str, seo_folder: str, allow_locked: bool = False) -> tuple:
    """Return root, folder, listing JSON path and image path for ``seo_folder``."""
    slug = seo_folder.replace("LOCKED-", "")
    roots = [config.PROCESSED_ROOT, config.FINALISED_ROOT]
    if allow_locked:
        roots.append(config.ARTWORK_VAULT_ROOT)

    for root in roots:
        folder = root / seo_folder
        if folder.exists():
            listing_file = folder / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=slug)
            image_file = folder / f"{slug}.jpg"
            return root, folder, listing_file, image_file
    raise FileNotFoundError(
        f"Cannot resolve paths for folder '{seo_folder}' (allow_locked={allow_locked})"
    )

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
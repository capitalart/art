"""Path utilities for DreamArtMachine.

This module centralises listing path resolution logic so
other modules can import it without causing circular dependencies.
"""
from __future__ import annotations
from pathlib import Path
import config


def resolve_listing_paths(aspect: str, seo_folder: str, allow_locked: bool = False) -> tuple:
    """Return folder, listing JSON path and image path for ``seo_folder``.

    Parameters
    ----------
    aspect: str
        Aspect ratio (unused but kept for backward compatibility).
    seo_folder: str
        The folder name containing the listing.
    allow_locked: bool, optional
        If ``True`` search finalised and locked folders in addition to processed.
    """
    slug = seo_folder.replace("LOCKED-", "")
    roots = [config.PROCESSED_ROOT]
    if allow_locked:
        roots += [config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT]

    for root in roots:
        folder = root / seo_folder
        if folder.exists():
            listing_file = folder / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=slug)
            image_file = folder / f"{slug}.jpg"
            return root, folder, listing_file, image_file
    raise FileNotFoundError(
        f"Cannot resolve paths for folder '{seo_folder}' (allow_locked={allow_locked})"
    )


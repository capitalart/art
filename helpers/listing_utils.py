"""
Listing & File Management Utilities for ArtNarrator
===================================================
Provides robust, centralised functions for handling JSON files, resolving
artwork paths across different processing stages, and managing the artwork
lifecycle, including creation, moving, and deletion.

INDEX
-----
1.  Imports & Initialisation
2.  JSON & File Helpers
3.  Path Resolution & Folder Management
4.  Artwork Lifecycle Management
5.  Guided Description Writing System (GDWS) Helpers
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
import shutil
import threading
from datetime import datetime

# Local application imports are moved inside functions to prevent circular dependencies
# import config # <-- REMOVED FROM TOP LEVEL

logger = logging.getLogger(__name__)
# A lock to prevent race conditions when updating the master JSON file
master_json_lock = threading.Lock()


# ===========================================================================
# 2. JSON & File Helpers
# ===========================================================================

def load_json_file_safe(path: Path) -> dict:
    """Return JSON data from ``path`` with defensive error handling."""
    path = Path(path)
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
            logger.warning(f"Created new empty JSON file at {path}")
        except OSError as e:
            logger.error(f"Failed to create directory or file at {path}: {e}")
        return {}

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        path.write_text("{}", encoding="utf-8")
        logger.warning(f"File at {path} was empty; reset to {{}}")
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        path.write_text("{}", encoding="utf-8")
        logger.error(f"Invalid JSON in {path}, reset to {{}}. Error: {e}")
        return {}


# ===========================================================================
# 3. Path Resolution & Folder Management
# ===========================================================================

def resolve_artwork_stage(seo_folder: str) -> tuple[str, Path] | tuple[None, None]:
    """Determine the current workflow stage for ``seo_folder``."""
    import config
    search_paths = {
        "unanalysed": config.UNANALYSED_ROOT, "processed": config.PROCESSED_ROOT,
        "finalised": config.FINALISED_ROOT, "vault": config.ARTWORK_VAULT_ROOT,
    }
    for stage, root in search_paths.items():
        if not root or not root.exists():
            continue
        candidate = root / seo_folder
        if stage == "vault" and not candidate.exists():
            candidate = root / f"LOCKED-{seo_folder}"
        if candidate.exists() and candidate.is_dir():
            return stage, candidate
    return None, None

def generate_public_image_urls(seo_folder: str, stage: str) -> list[str]:
    """Return absolute, public URLs for all images of an artwork."""
    import config
    stage_root_map = {
        "unanalysed": config.UNANALYSED_ROOT,
        "processed": config.PROCESSED_ROOT,
        "finalised": config.FINALISED_ROOT,
        "vault": config.ARTWORK_VAULT_ROOT,
    }
    root = stage_root_map.get(stage)
    if not root:
        return []

    folder_path = root / seo_folder
    if stage == "vault" and not folder_path.exists():
        folder_path = root / f"LOCKED-{seo_folder}"
    if not folder_path.exists():
        return []

    return [config.resolve_image_url(img) for img in sorted(folder_path.glob("*.jpg"))]

def find_seo_folder_from_filename(aspect: str, filename: str) -> str:
    """Return the best matching SEO folder name for a given artwork filename."""
    import config
    basename = Path(filename).stem.lower().replace('-thumb', '').replace('-analyse', '')
    candidates: list[tuple[float, str]] = []
    for base in (config.PROCESSED_ROOT, config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT):
        if not base or not base.exists():
            continue
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            slug = folder.name.replace("LOCKED-", "")
            listing_file = folder / f"{slug}-listing.json"
            if listing_file.exists():
                data = load_json_file_safe(listing_file)
                stems = {Path(data.get(k, "")).stem.lower() for k in ("filename", "seo_filename")} | {slug.lower()}
                if basename in stems:
                    candidates.append((listing_file.stat().st_mtime, slug))
    if not candidates:
        raise FileNotFoundError(f"Could not find a matching SEO folder for filename: {filename}")
    return max(candidates, key=lambda x: x[0])[1]

def resolve_listing_paths(aspect: str, filename: str, allow_locked: bool = False) -> tuple[str, Path, Path, bool]:
    """Finds the correct paths for an artwork's folder and its listing.json file."""
    seo_folder = find_seo_folder_from_filename(aspect, filename)
    stage_info = resolve_artwork_stage(seo_folder)
    if not stage_info:
        raise FileNotFoundError(f"Artwork '{seo_folder}' not found in any stage")
    
    stage, folder_path = stage_info
    
    if not allow_locked and stage == "vault":
        raise PermissionError(f"Attempted to access locked artwork '{seo_folder}' without permission.")

    listing_path = folder_path / f"{seo_folder}-listing.json"
    if not listing_path.exists():
        raise FileNotFoundError(f"Found folder for '{seo_folder}' but missing its -listing.json file.")
    
    is_finalised = stage in ["finalised", "vault"]
    return seo_folder, folder_path, listing_path, is_finalised


# ===========================================================================
# 4. Artwork Lifecycle Management
# ===========================================================================

def create_unanalysed_subfolder(original_filename: str) -> Path:
    """Creates a unique subfolder in the unanalysed directory for a new upload."""
    import config
    safe_base = re.sub(r'[^\w\-]+', '', Path(original_filename).stem).strip()
    unique_id = uuid.uuid4().hex[:8]
    folder_name = f"{safe_base}-{unique_id}"
    folder_path = config.UNANALYSED_ROOT / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path

def cleanup_unanalysed_folders():
    """Removes empty subfolders from the unanalysed artwork directory."""
    import config
    for item in config.UNANALYSED_ROOT.iterdir():
        if item.is_dir() and not any(item.iterdir()):
            try:
                item.rmdir()
                logger.info(f"Cleaned up empty unanalysed folder: {item.name}")
            except OSError as e:
                logger.warning(f"Could not remove empty folder {item.name}: {e}")

def update_artwork_registry(seo_folder: str, new_path: Path, new_status: str) -> None:
    """Update the master registry entry for ``seo_folder``.

    Args:
        seo_folder: Artwork identifier.
        new_path: Filesystem path to the artwork's new location.
        new_status: Workflow status (e.g. ``processed`` or ``locked``).
    """
    import config
    registry = Path(config.OUTPUT_JSON)
    with master_json_lock:
        data = load_json_file_safe(registry)
        key = next((k for k, v in data.items() if v.get("base") == seo_folder), None)
        if not key:
            return
        entry = data[key]
        entry["current_folder"] = str(new_path)
        entry["status"] = new_status
        entry.setdefault("history", []).append({
            "status": new_status,
            "folder": str(new_path),
            "timestamp": datetime.utcnow().isoformat(),
        })
        registry.write_text(json.dumps(data, indent=2), encoding="utf-8")

def remove_artwork_from_registry(seo_folder: str, registry_path: Path | None = None) -> bool:
    """Remove any entry referencing ``seo_folder`` from the master registry JSON."""
    import config
    registry = Path(registry_path or config.OUTPUT_JSON)
    if not registry.exists():
        return True
    with master_json_lock:
        try:
            data = load_json_file_safe(registry)
            key_to_delete = next(
                (k for k, v in data.items() if v.get("base") == seo_folder),
                None,
            )
            if key_to_delete:
                del data[key_to_delete]
                registry.write_text(json.dumps(data, indent=2), encoding="utf-8")
                logger.info(f"Removed '{seo_folder}' from {registry.name}")
            return True
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error updating registry JSON file: {e}")
            return False

def delete_artwork(seo_folder: str) -> bool:
    """Delete an artwork's directory and registry entry, if present."""
    logger.info(f"Initiating deletion for artwork: '{seo_folder}'")
    stage_info = resolve_artwork_stage(seo_folder)

    if stage_info:
        _stage, folder_path = stage_info
    else:
        import config
        registry = load_json_file_safe(config.OUTPUT_JSON)
        entry = next((v for v in registry.values() if v.get("base") == seo_folder), None)
        folder_path = Path(entry.get("current_folder", "")) if entry else None

    if folder_path and folder_path.exists():
        try:
            shutil.rmtree(folder_path)
            logger.info(f"Successfully deleted directory: {folder_path}")
        except OSError as e:
            logger.error(f"Failed to delete directory for '{seo_folder}': {e}")
            return False
    else:
        logger.warning(f"Could not find folder for '{seo_folder}'. It may have been already deleted.")

    if not remove_artwork_from_registry(seo_folder):
        logger.error(
            f"Deleted folder (or it was already gone) for '{seo_folder}' but FAILED to update master JSON."
        )
        return False

    logger.info(f"Successfully completed deletion for artwork: '{seo_folder}'")
    return True


# ===========================================================================
# 5. Guided Description Writing System (GDWS) Helpers
# ===========================================================================

def assemble_gdws_description(aspect_ratio: str) -> str:
    """Assembles a full artwork description from the GDWS content blocks."""
    import config
    aspect_path = config.GDWS_CONTENT_DIR / aspect_ratio
    if not aspect_path.exists():
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
    
    pinned_start = config.GDWS_CONFIG.get("PINNED_START_TITLES", [])
    pinned_end = config.GDWS_CONFIG.get("PINNED_END_TITLES", [])
    order_file = aspect_path / "order.json"
    
    final_order = [title for title in pinned_start if title in all_blocks]
    middle_order = load_json_file_safe(order_file).get("order", []) if order_file.exists() else []
    
    final_order.extend([t for t in middle_order if t in all_blocks and t not in final_order])
    remaining = [t for t in all_blocks if t not in final_order and t not in pinned_end]
    final_order.extend(sorted(remaining))
    final_order.extend([t for t in pinned_end if t in all_blocks])

    description_parts = [f"{all_blocks[t]['title']}\n\n{all_blocks[t]['content']}" for t in final_order if t in all_blocks]
    return "\n\n---\n\n".join(description_parts)

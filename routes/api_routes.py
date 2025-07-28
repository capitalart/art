# routes/api_routes.py
"""
General-purpose API routes for direct artwork analysis and file management.

These endpoints are designed to be called by external services or advanced
UI components that need direct access to core functionalities.

INDEX
-----
1.  Imports
2.  Blueprint Setup
3.  API Routes
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import uuid
import shutil
from pathlib import Path
import logging

from flask import Blueprint, request, jsonify

import config
from routes.artwork_routes import _run_ai_analysis

logger = logging.getLogger(__name__)

# ===========================================================================
# 2. Blueprint Setup
# ===========================================================================
bp = Blueprint("api", __name__, url_prefix="/api")


# ===========================================================================
# 3. API Routes
# ===========================================================================

@bp.post("/analyze-artwork")
def analyze_artwork_api():
    """
    Analyzes an uploaded image with a specified provider.
    This is a stateless endpoint that creates and cleans up its own temp folder.
    """
    provider = request.form.get("provider")
    if provider not in {"openai", "google"}:
        return jsonify({"success": False, "error": "Provider must be 'openai' or 'google'."}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"success": False, "error": "No image file provided in 'file' field."}), 400

    temp_id = uuid.uuid4().hex[:8]
    # Use the UNANALYSED_ROOT from config for the base path
    temp_dir = config.UNANALYSED_ROOT / f"api-temp-{temp_id}"
    
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        image_path = temp_dir / file.filename
        file.save(image_path)
        logger.info(f"API analyze-artwork call: Saved temporary file to {image_path}")

        entry = _run_ai_analysis(image_path, provider)
        logger.info(f"API analyze-artwork call: Successfully analyzed {image_path} with {provider}.")
        return jsonify({"success": True, "result": entry})

    except Exception as exc:
        logger.error(f"API analyze-artwork error: {exc}", exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500
        
    finally:
        # Ensure the temporary directory is always cleaned up
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"API analyze-artwork call: Cleaned up temporary directory {temp_dir}")


@bp.post("/delete-upload-folder")
def delete_upload_folder():
    """
    Deletes a specified subfolder within the unanalysed artwork directory.
    Includes a security check to prevent traversal outside the target directory.
    """
    folder_path_str = request.json.get("folder") if request.is_json else None
    
    if not folder_path_str:
        return jsonify({"success": False, "error": "Invalid request. 'folder' path is required."}), 400

    # Security check: Ensure the path is within the allowed directory
    unanalysed_root_str = str(config.UNANALYSED_ROOT)
    full_path = Path(folder_path_str).resolve()

    if not str(full_path).startswith(unanalysed_root_str):
        logger.warning(f"API delete-upload-folder blocked attempt to delete outside target directory: {folder_path_str}")
        return jsonify({"success": False, "error": "Invalid folder path. Deletion is restricted."}), 400
        
    try:
        shutil.rmtree(full_path, ignore_errors=True)
        logger.info(f"API successfully deleted folder: {full_path}")
        return jsonify({"success": True, "message": f"Folder '{full_path.name}' deleted."})
    except Exception as exc:
        logger.error(f"API delete-upload-folder failed for path {full_path}: {exc}", exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500
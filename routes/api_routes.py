"""API routes for direct artwork analysis and file management."""

from __future__ import annotations

import uuid
import shutil
from pathlib import Path
import logging

from flask import Blueprint, request, jsonify

from .artwork_routes import _run_ai_analysis

bp = Blueprint("api", __name__)


@bp.post("/api/analyze-artwork")
def analyze_artwork_api():
    """Analyze an uploaded image with the requested provider."""
    provider = request.form.get("provider")
    if provider not in {"openai", "google"}:
        return (
            jsonify({"success": False, "error": "Provider must be openai or google."}),
            400,
        )

    file = request.files.get("file")
    if not file:
        return jsonify({"success": False, "error": "No image file uploaded."}), 400

    temp_id = uuid.uuid4().hex[:8]
    temp_dir = Path("art-processing/unanalysed-artwork") / f"unanalysed-{temp_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    image_path = temp_dir / file.filename
    file.save(image_path)

    try:
        entry = _run_ai_analysis(image_path, provider)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"success": True, "result": entry})
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(temp_dir, ignore_errors=True)
        logging.getLogger(__name__).error("Analysis error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.post("/api/delete-upload-folder")
def delete_upload_folder():
    """Delete an uploaded unanalysed folder."""
    folder = request.json.get("folder") if request.is_json else None
    if (
        not folder
        or not folder.startswith("art-processing/unanalysed-artwork/")
    ):
        return jsonify({"success": False, "error": "Invalid folder path."}), 400
    try:
        shutil.rmtree(folder, ignore_errors=True)
        return jsonify({"success": True})
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).error("Folder delete failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


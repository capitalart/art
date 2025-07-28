# routes/coordinate_admin_routes.py
"""
Admin dashboard for managing and generating mockup coordinates.

This module provides the user interface and backend logic for scanning
mockups that are missing coordinate files and for running the automated
coordinate generation script.

INDEX
-----
1.  Imports
2.  Blueprint Setup
3.  Admin Dashboard Route
4.  API & Asynchronous Routes
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import logging
import subprocess
import time

from flask import (
    Blueprint, render_template, jsonify, Response, stream_with_context
)

import config
from routes.utils import get_menu

logger = logging.getLogger(__name__)

# ===========================================================================
# 2. Blueprint Setup
# ===========================================================================
bp = Blueprint("coordinate_admin", __name__, url_prefix="/admin/coordinates")


# ===========================================================================
# 3. Admin Dashboard Route
# ===========================================================================
@bp.route("/")
def dashboard():
    """Display the coordinate management dashboard."""
    return render_template("admin/coordinates.html", menu=get_menu())


# ===========================================================================
# 4. API & Asynchronous Routes
# ===========================================================================
@bp.route("/scan")
def scan_for_missing_coordinates():
    """Scans all categorized mockups and reports which are missing coordinate files."""
    logger.info("Admin triggered a scan for missing coordinate files.")
    missing_files = []
    
    try:
        for aspect_dir in config.MOCKUPS_CATEGORISED_DIR.iterdir():
            if not aspect_dir.is_dir(): continue
            
            aspect_name = aspect_dir.name
            coord_aspect_dir = config.COORDS_DIR / aspect_name

            for category_dir in aspect_dir.iterdir():
                if not category_dir.is_dir(): continue
                
                for mockup_file in category_dir.glob("*.png"):
                    coord_file = coord_aspect_dir / category_dir.name / f"{mockup_file.stem}.json"
                    if not coord_file.exists():
                        missing_files.append(str(mockup_file.relative_to(config.BASE_DIR)))
                        
        logger.info(f"Scan complete. Found {len(missing_files)} mockups missing coordinates.")
        return jsonify({"missing_files": sorted(missing_files)})
    except Exception as e:
        logger.error(f"An error occurred during coordinate scan: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred during the scan."}), 500


@bp.route("/run-generator")
def run_generator():
    """Runs the coordinate generator script and streams its output with a heartbeat."""
    logger.info("Admin triggered the coordinate generator script.")
    # Use the new config variable for the script path
    script_path = config.COORDINATE_GENERATOR_SCRIPT_PATH
    
    def generate_output():
        try:
            process = subprocess.Popen(
                ["python3", str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Combine stdout and stderr
                text=True,
                bufsize=1
            )
            
            # Stream the output line by line
            for line in iter(process.stdout.readline, ''):
                yield f"data: {line.strip()}\n\n"
            
            process.stdout.close()
            return_code = process.wait()
            
            if return_code == 0:
                logger.info("Coordinate generator script finished successfully.")
                yield "data: ---SCRIPT FINISHED SUCCESSFULLY---\n\n"
            else:
                logger.error(f"Coordinate generator script finished with error code {return_code}.")
                yield f"data: ---SCRIPT FINISHED WITH ERROR (Code: {return_code})---\n\n"

        except Exception as e:
            logger.error(f"Failed to execute coordinate generator script: {e}", exc_info=True)
            yield f"data: ---ERROR: Failed to start the script: {e}---\n\n"

    headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no', # Disable buffering for Nginx
    }
    return Response(stream_with_context(generate_output()), headers=headers)
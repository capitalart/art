"""Admin dashboard for managing and generating mockup coordinates."""

from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context
from pathlib import Path
import subprocess
import time
import config
from routes.utils import get_menu

bp = Blueprint("coordinate_admin", __name__, url_prefix="/admin/coordinates")

@bp.route("/")
def dashboard():
    """Display the coordinate management dashboard."""
    return render_template("admin/coordinates.html", menu=get_menu())

@bp.route("/scan")
def scan_for_missing_coordinates():
    """Scans all categorized mockups and reports which are missing coordinate files."""
    missing_files = []
    
    for aspect_dir in config.MOCKUPS_CATEGORISED_DIR.iterdir():
        if not aspect_dir.is_dir(): continue
            
        aspect_name = aspect_dir.name.replace("-categorised", "")
        coord_aspect_dir = config.COORDS_DIR / aspect_name

        for category_dir in aspect_dir.iterdir():
            if not category_dir.is_dir(): continue
            
            for mockup_file in category_dir.glob("*.png"):
                coord_file = coord_aspect_dir / category_dir.name / f"{mockup_file.stem}.json"
                if not coord_file.exists():
                    missing_files.append(str(mockup_file.relative_to(config.BASE_DIR)))
                    
    return jsonify({"missing_files": sorted(missing_files)})

@bp.route("/run-generator")
def run_generator():
    """Runs the coordinate generator script and streams its output with a heartbeat."""
    script_path = config.SCRIPTS_DIR / "generate_coordinates.py"
    
    def generate_output():
        process = subprocess.Popen(
            ["python3", str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, 
            text=True,
            bufsize=1
        )
        
        # Keep sending heartbeats while the process is running
        while process.poll() is None:
            yield "event: ping\ndata: heartbeat\n\n"
            time.sleep(2) # Send a heartbeat every 2 seconds
        
        # After the process finishes, stream its output
        for line in iter(process.stdout.readline, ''):
            yield f"data: {line.strip()}\n\n"
        
        process.stdout.close()
        process.wait()
        yield "data: ---SCRIPT FINISHED---\n\n"

    headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no', # Important for Nginx buffering
    }
    return Response(stream_with_context(generate_output()), headers=headers)
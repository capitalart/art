# FULL CODE STACK (SAT-26-JULY-2025-08-12-PM)


---
## app.py
---
"""ArtNarrator application entrypoint."""

from __future__ import annotations
import logging
from flask import Flask, render_template, request, redirect, url_for, session
import db
from pathlib import Path
from utils import security, session_tracker
from werkzeug.routing import BuildError
from datetime import datetime
import config

# Ensure logs directory and session registry files exist before logging
LOGS_DIR = config.LOGS_DIR
LOGS_DIR.mkdir(parents=True, exist_ok=True)
registry_json = LOGS_DIR / "session_registry.json"
registry_tmp = LOGS_DIR / "session_registry.tmp"
if not registry_json.exists():
    registry_json.write_text("{}")
if not registry_tmp.exists():
    registry_tmp.write_text("{}")

# ---- Modular Imports ----
from routes import utils
from routes.artwork_routes import bp as artwork_bp
from routes.sellbrite_service import bp as sellbrite_bp
from routes.export_routes import bp as exports_bp
from routes.auth_routes import bp as auth_bp
from routes.admin_security import bp as admin_bp
from routes.mockup_admin_routes import bp as mockup_admin_bp
from routes.coordinate_admin_routes import bp as coordinate_admin_bp
from routes.gdws_admin_routes import bp as gdws_admin_bp
from routes.test_routes import test_bp
from routes.api_routes import bp as api_bp

# ---- Initialize Flask App ----
app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY
db.init_db()

# ---- Set API Key Config Flags (using config.py variables) ----
app.config["OPENAI_CONFIGURED"] = bool(config.OPENAI_API_KEY)
app.config["GOOGLE_CONFIGURED"] = bool(getattr(config, "GOOGLE_API_KEY", None))
if not app.config["OPENAI_CONFIGURED"]:
    logging.warning("OPENAI_API_KEY not configured in environment/.env")
if not app.config["GOOGLE_CONFIGURED"]:
    logging.warning("GOOGLE_API_KEY not configured in environment/.env")

# ---- User Authentication & Security Section ----

@app.before_request
def require_login() -> None:
    """
    Enforce login for all routes except:
    - the login page,
    - static files,
    - health check endpoints (/health, /healthz).
    """
    # DEBUG LOG: Print path for troubleshooting (remove/comment out when working)
    # print(f"DEBUG: request.path is {request.path}, request.endpoint is {request.endpoint}")

    # Always allow health endpoints through (for toolkit and monitoring)
    if request.path == "/health" or request.path == "/healthz":
        return

    # Allow login page and static files without authentication
    if request.endpoint == "auth.login" or request.endpoint == "static" or request.endpoint is None:
        return

    # Block if not logged in (and login protection is enabled)
    if not session.get("logged_in"):
        if security.login_required_enabled():
            return redirect(url_for("auth.login", next=request.path))
        return

    # Validate session (touch session, ensure still valid)
    username = session.get("username")
    role = session.get("role")
    sid = session.get("session_id")
    if not session_tracker.touch_session(username, sid):
        session.clear()
        if security.login_required_enabled():
            return redirect(url_for("auth.login", next=request.path))
        return

    # Enforce role logic if login required is disabled but role is not admin
    if not security.login_required_enabled() and role != "admin":
        session.clear()
        return redirect(url_for("auth.login", next=request.path))

# ---- Logging Setup ----
logging.basicConfig(
    filename=config.LOGS_DIR / "composites-workflow.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

log_file = config.LOGS_DIR / "app_start_stop.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

@app.route("/<path:url>")
def dynamic_page(url):
    if len(url) > 30:
        app.logger.warning(f"URL exceeded max length: {url}")
        return render_template("404.html"), 404
    return f"You requested the URL: {url}"

# ---- Register Blueprints ----
app.register_blueprint(auth_bp)
app.register_blueprint(artwork_bp)
app.register_blueprint(sellbrite_bp)
app.register_blueprint(exports_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(mockup_admin_bp)
app.register_blueprint(coordinate_admin_bp)
app.register_blueprint(gdws_admin_bp)
app.register_blueprint(test_bp)
app.register_blueprint(api_bp)


@app.after_request
def apply_no_cache(response):
    """Attach no-cache headers when admin mode requires it."""
    if security.force_no_cache_enabled():
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

@app.context_processor
def inject_api_status():
    return dict(
        openai_configured=app.config.get("OPENAI_CONFIGURED", False),
        google_configured=app.config.get("GOOGLE_CONFIGURED", False),
    )

@app.errorhandler(BuildError)
def handle_build_error(err):
    app.logger.error("BuildError: %s", err)
    return render_template("missing_endpoint.html", error=err), 500

@app.errorhandler(404)
def page_not_found(e):
    app.logger.error(f"Page not found: {request.url}")
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"Internal Server Error: {e}")
    return render_template("500.html"), 500

@app.route("/healthz")
def healthz():
    return "OK"

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    logging.info(f"ArtNarrator app started at {datetime.now()}")
    port = config.PORT
    host = config.HOST
    debug = config.DEBUG
    if debug and host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Refusing to run debug mode on a public interface")
    print(f"\U0001f3a8 Starting ArtNarrator UI at http://{host}:{port}/ ...")
    try:
        app.run(debug=debug, host=host, port=port)
    finally:
        logging.info(f"ArtNarrator app stopped at {datetime.now()}")

def create_app() -> Flask:
    return app


---
## config.py
---
"""
config.py — ArtNarrator & DreamArtMachine (Robbie Mode™, July 2025)
Central config: All core folders, env vars, limits, AI models, templates.
All code must import config.py and reference only these values!
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Load .env file from project root ---
load_dotenv()

# === PROJECT ROOT ===
BASE_DIR = Path(__file__).resolve().parent

# -----------------------------------------------------------------------------
# 1. ENV/BRANDING/ADMIN
# -----------------------------------------------------------------------------
BRAND_NAME = os.getenv("BRAND_NAME", "Art Narrator")
BRAND_TAGLINE = os.getenv("BRAND_TAGLINE", "Create. Automate. Sell Art.")
BRAND_AUTHOR = os.getenv("BRAND_AUTHOR", "Robin Custance")
BRAND_DOMAIN = os.getenv("BRAND_DOMAIN", "artnarrator.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "robincustance@gmail.com")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "robbie")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "kangaroo123")
SERVER_PORT = int(os.getenv("SERVER_PORT", "7777"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
HOST = os.getenv("HOST", "127.0.0.1")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "supersecret-key-1234")
PORT = int(os.getenv("PORT", "7777"))

# -----------------------------------------------------------------------------
# 2. AI/PLATFORM/API MODELS
# -----------------------------------------------------------------------------
# --- OpenAI ---
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_MODEL_FALLBACK = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4-turbo")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")

# --- Google Cloud ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", "art-narrator")
GOOGLE_VISION_MODEL_NAME = os.getenv("GOOGLE_VISION_MODEL_NAME", "builtin/stable")
GOOGLE_GEMINI_PRO_VISION_MODEL_NAME = os.getenv("GOOGLE_GEMINI_PRO_VISION_MODEL_NAME", "gemini-pro-vision")

# --- Other Integrations ---
RCLONE_REMOTE_NAME = os.getenv("RCLONE_REMOTE_NAME", "gdrive")
RCLONE_REMOTE_PATH = os.getenv("RCLONE_REMOTE_PATH", "art-backups")
SELLBRITE_ACCOUNT_TOKEN = os.getenv("SELLBRITE_ACCOUNT_TOKEN")  # <-- ADDED
SELLBRITE_SECRET_KEY = os.getenv("SELLBRITE_SECRET_KEY")      # <-- ADDED
SELLBRITE_API_BASE_URL = os.getenv("SELLBRITE_API_BASE_URL", "https://api.sellbrite.com/v1")
ETSY_SHOP_URL = os.getenv("ETSY_SHOP_URL", "https://www.robincustance.etsy.com")

# -----------------------------------------------------------------------------
# 3. FOLDER STRUCTURE & PATHS (STRICTLY WHAT'S LIVE)
# -----------------------------------------------------------------------------
ART_PROCESSING_DIR = Path(os.getenv("ART_PROCESSING_DIR", BASE_DIR / "art-processing"))
UNANALYSED_ROOT = ART_PROCESSING_DIR / "unanalysed-artwork"
PROCESSED_ROOT = ART_PROCESSING_DIR / "processed-artwork"
FINALISED_ROOT = ART_PROCESSING_DIR / "finalised-artwork"
ARTWORK_VAULT_ROOT = ART_PROCESSING_DIR / "artwork-vault"

OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", BASE_DIR / "outputs"))
COMPOSITES_DIR = OUTPUTS_DIR / "composites"
SELECTIONS_DIR = OUTPUTS_DIR / "selections"
SELLBRITE_DIR = OUTPUTS_DIR / "sellbrite"
SIGNED_DIR = OUTPUTS_DIR / "signed"

MOCKUPS_INPUT_DIR = Path(os.getenv("MOCKUPS_INPUT_DIR", BASE_DIR / "inputs" / "mockups"))
MOCKUPS_STAGING_DIR = MOCKUPS_INPUT_DIR / "uncategorised"
MOCKUPS_CATEGORISED_DIR = MOCKUPS_INPUT_DIR / "categorised"
SIGNATURES_DIR = Path(os.getenv("SIGNATURES_DIR", BASE_DIR / "inputs" / "signatures"))
GENERIC_TEXTS_DIR = Path(os.getenv("GENERIC_TEXTS_DIR", BASE_DIR / "generic_texts"))
COORDS_DIR = Path(os.getenv("COORDS_DIR", BASE_DIR / "inputs" / "Coordinates"))

SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", BASE_DIR / "scripts"))
SETTINGS_DIR = Path(os.getenv("SETTINGS_DIR", BASE_DIR / "settings"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", BASE_DIR / "logs"))
CODEX_LOGS_DIR = Path(os.getenv("CODEX_LOGS_DIR", BASE_DIR / "CODEX-LOGS"))
STATIC_DIR = Path(os.getenv("STATIC_DIR", BASE_DIR / "static"))
TEMPLATES_DIR = Path(os.getenv("TEMPLATES_DIR", BASE_DIR / "templates"))
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "artnarrator.sqlite3"

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
GDWS_CONTENT_DIR = DATA_DIR / "gdws_content"  # <-- ADD THIS LINE
DB_PATH = DATA_DIR / "artnarrator.sqlite3"

# -----------------------------------------------------------------------------
# 4. HELPER/REGISTRY FILES (ONLY WHAT'S USED)
# -----------------------------------------------------------------------------
SKU_TRACKER = SETTINGS_DIR / "sku_tracker.json"
ANALYSIS_STATUS_FILE = LOGS_DIR / "analysis_status.json"
ONBOARDING_PATH = SETTINGS_DIR / "Master-Etsy-Listing-Description-Writing-Onboarding.txt"
OUTPUT_JSON = ART_PROCESSING_DIR / "master-artwork-paths.json"
MOCKUP_CATEGORISATION_LOG = LOGS_DIR / "mockup_categorisation.log"

# -----------------------------------------------------------------------------
# 5. FILE/FILENAME TEMPLATES
# -----------------------------------------------------------------------------
FILENAME_TEMPLATES = {
    "artwork": "{seo_slug}.jpg",
    "mockup": "{seo_slug}-MU-{num:02d}.jpg",
    "thumbnail": "{seo_slug}-THUMB.jpg",
    "analyse": "{seo_slug}-ANALYSE.jpg",
    "listing_json": "{seo_slug}-listing.json",
    "qc_json": "{seo_slug}.qc.json",
}

# -----------------------------------------------------------------------------
# 6. FILE TYPES, LIMITS, IMAGE SIZES
# -----------------------------------------------------------------------------
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png").split(","))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
ANALYSE_MAX_DIM = int(os.getenv("ANALYSE_MAX_DIM", "2400"))
ANALYSE_MAX_MB = int(os.getenv("ANALYSE_MAX_MB", "5"))
THUMB_WIDTH = int(os.getenv("THUMB_WIDTH", "400"))
THUMB_HEIGHT = int(os.getenv("THUMB_HEIGHT", "400"))

# -----------------------------------------------------------------------------
# 7. MOCKUP CATEGORIES (DYNAMIC)
# -----------------------------------------------------------------------------
def get_mockup_categories() -> list[str]:
    override = os.getenv("MOCKUP_CATEGORIES")
    if override:
        return [c.strip() for c in override.split(",") if c.strip()]
    d = MOCKUPS_INPUT_DIR
    if d.exists():
        return sorted(
            [
                f.name
                for f in d.iterdir()
                if f.is_dir() and f.name.lower() != "uncategorised"
            ]
        )
    return []

MOCKUP_CATEGORIES = get_mockup_categories()

# -----------------------------------------------------------------------------
# 8. FOLDER AUTO-CREATION (STRICT)
# -----------------------------------------------------------------------------
_CRITICAL_FOLDERS = [
    ART_PROCESSING_DIR,
    UNANALYSED_ROOT,
    PROCESSED_ROOT,
    FINALISED_ROOT,
    ARTWORK_VAULT_ROOT,
    OUTPUTS_DIR,
    COMPOSITES_DIR,
    SELECTIONS_DIR,
    SELLBRITE_DIR,
    SIGNED_DIR,
    MOCKUPS_INPUT_DIR,
    SIGNATURES_DIR,
    GENERIC_TEXTS_DIR,
    COORDS_DIR,
    SCRIPTS_DIR,
    SETTINGS_DIR,
    LOGS_DIR,
    CODEX_LOGS_DIR,
    DATA_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
]
for folder in _CRITICAL_FOLDERS:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"Could not create required folder {folder}: {exc}")

# -----------------------------------------------------------------------------
# 9. SCRIPTS (For automation & CLI)
# -----------------------------------------------------------------------------
ANALYZE_SCRIPT_PATH = SCRIPTS_DIR / "analyze_artwork.py"
GENERATE_SCRIPT_PATH = SCRIPTS_DIR / "generate_composites.py"

# -----------------------------------------------------------------------------
# 10. AUDIT/MARKDOWN/QA
# -----------------------------------------------------------------------------
QA_AUDIT_INDEX = BASE_DIR / "QA_AUDIT_INDEX.md"
SITEMAP_FILE = BASE_DIR / "SITEMAP.md"
CHANGELOG_FILE = BASE_DIR / "CHANGELOG.md"

---
## requirements.txt
---
annotated-types==0.7.0
anyio==4.9.0
blinker==1.9.0
certifi==2025.6.15
charset-normalizer==3.4.2
click==8.2.1
distro==1.9.0
Flask==3.1.1
gunicorn
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.10
itsdangerous==2.2.0
Jinja2==3.1.6
jiter==0.10.0
joblib==1.5.1
markdown-it-py==3.0.0
MarkupSafe==3.0.2
mdurl==0.1.2
numpy==2.3.1
openai==1.93.0
opencv-python==4.11.0.86
pandas==2.3.0
passlib==1.7.4
pillow==11.2.1
pydantic==2.11.7
pydantic_core==2.33.2
Pygments==2.19.2
python-dateutil==2.9.0.post0
python-dotenv==1.1.1
pytz==2025.2
requests==2.32.4
rich==14.0.0
scikit-learn==1.7.0
scipy==1.16.0
six==1.17.0
sniffio==1.3.1
SQLAlchemy==2.0.30
threadpoolctl==3.6.0
tqdm==4.67.1
typing-inspection==0.4.1
typing_extensions==4.14.0
tzdata==2025.2
urllib3==2.5.0
Werkzeug==3.1.3
google-generativeai==0.5.0
google-cloud-vision==3.10.2
google-api-python-client==2.126.0
google-auth==2.29.0
google-cloud-storage==2.16.0
google-cloud-secret-manager==2.22.0
google-cloud-logging==3.11.0


---
## routes/__init__.py
---


---
## routes/admin_security.py
---
"""Admin security routes for toggling login requirement."""
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime

from utils import security, session_tracker, user_manager
from utils.auth_decorators import role_required
import config

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@role_required("admin")
def dashboard():
    return render_template("admin/dashboard.html")


@bp.route("/security", methods=["GET", "POST"])
@role_required("admin")
def security_page():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "enable":
            security.enable_login()
        elif action == "disable":
            minutes = int(request.form.get("minutes", 5))
            security.disable_login_for(minutes)
        elif action == "nocache_on":
            minutes = int(request.form.get("minutes", 5))
            security.enable_no_cache(minutes)
        elif action == "nocache_off":
            security.disable_no_cache()
        return redirect(url_for("admin.security_page"))
    remaining = security.remaining_minutes()
    login_required = security.login_required_enabled()
    no_cache = security.force_no_cache_enabled()
    cache_remaining = security.no_cache_remaining()
    active_count = len(session_tracker.active_sessions(config.ADMIN_USERNAME))
    return render_template(
        "admin/security.html",
        login_required=login_required,
        remaining=remaining,
        no_cache=no_cache,
        cache_remaining=cache_remaining,
        expires=None,
        active=active_count,
        max_sessions=session_tracker.MAX_SESSIONS,
    )


@bp.route("/users", methods=["GET", "POST"])
@role_required("admin")
def manage_users():
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username")
        role = request.form.get("role", "viewer")
        password = request.form.get("password", "changeme")
        if action == "add" and username:
            user_manager.add_user(username, role, password)
        elif action == "delete" and username:
            user_manager.delete_user(username)
    users = user_manager.load_users()
    return render_template("admin/users.html", users=users, config=config)


---
## routes/api_routes.py
---
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



---
## routes/artwork_routes.py
---
"""Artwork-related Flask routes.

This module powers the full listing workflow from initial review to
finalisation. It handles validation, moving files, regenerating image link
lists and serving gallery pages for processed and finalised artworks.
"""

# This file now references all path, directory, and filename variables strictly from config.py. No local or hardcoded path constants remain.
from __future__ import annotations

import json
import subprocess
import uuid
import random
import logging
from pathlib import Path
import shutil
import os
import traceback
import datetime
import time
from utils.logger_utils import log_action, strip_binary
from config import (
    PROCESSED_ROOT,
    FINALISED_ROOT,
    UNANALYSED_ROOT,
    ARTWORK_VAULT_ROOT,
    BASE_DIR,
    ANALYSIS_STATUS_FILE,
)
import config

# Initialise module logger immediately so early failures are captured
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

from PIL import Image
import io
import scripts.analyze_artwork as aa
import google.generativeai as genai

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    abort,
    Response,
    jsonify,
)
import re

from . import utils
from .utils import (
    ALLOWED_COLOURS_LOWER,
    relative_to_base,
    FINALISED_ROOT,
    parse_csv_list,
    join_csv_list,
    read_generic_text,
    clean_terms,
    infer_sku_from_filename,
    sync_filename_with_sku,
    is_finalised_image,
    get_allowed_colours,
    load_json_file_safe,
    generate_mockups_for_listing,
)
from utils.sku_assigner import peek_next_sku

bp = Blueprint("artwork", __name__)

# ---------------------------------------------------------------------------
# Health-check Endpoints
# ---------------------------------------------------------------------------


@bp.get("/health/openai")
def health_openai():
    """Return status of OpenAI connection."""
    logger = logging.getLogger(__name__)
    try:
        aa.client.models.list()
        return jsonify({"ok": True})
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenAI health check failed: %s", exc)
        debug = config.DEBUG
        error = str(exc)
        if debug:
            error += "\n" + traceback.format_exc()
        return jsonify({"ok": False, "error": error}), 500


@bp.get("/health/google")
def health_google():
    """Return status of Google Vision connection."""
    logger = logging.getLogger(__name__)
    try:
        genai.list_models()
        return jsonify({"ok": True})
    except Exception as exc:  # noqa: BLE001
        logger.error("Google health check failed: %s", exc)
        debug = config.DEBUG
        error = str(exc)
        if debug:
            error += "\n" + traceback.format_exc()
        return jsonify({"ok": False, "error": error}), 500


# Ensure analysis status file exists at import time
load_json_file_safe(ANALYSIS_STATUS_FILE)


def _write_analysis_status(
    step: str,
    percent: int,
    file: str | None = None,
    status: str | None = None,
    error: str | None = None,
) -> None:
    """Write progress info for frontend polling."""

    logger = logging.getLogger(__name__)

    try:
        ANALYSIS_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error(
            "Unable to create status directory %s: %s", ANALYSIS_STATUS_FILE.parent, exc
        )

    payload = {"step": step, "percent": percent, "file": file}
    if status:
        payload["status"] = status
    if error:
        payload["error"] = error

    try:
        ANALYSIS_STATUS_FILE.write_text(json.dumps(payload))
        logger.debug("STATUS WRITTEN %s", payload)
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Failed writing analysis status: %s", exc)
        try:
            ANALYSIS_STATUS_FILE.write_text(
                json.dumps({"step": "error", "error": str(exc)})
            )
        except Exception as sub_exc:
            logger.error("Failed resetting analysis status file: %s", sub_exc)


@bp.route("/status/analyze")
def analysis_status():
    """Return JSON progress info for the current analysis job."""
    data = load_json_file_safe(ANALYSIS_STATUS_FILE)
    if not data:
        data = {"step": "idle", "percent": 0, "status": "idle"}
    return Response(json.dumps(data), mimetype="application/json")


def _run_ai_analysis(img_path: Path, provider: str) -> dict:
    """Run the AI analysis script and return its JSON output."""
    logger = logging.getLogger("art_analysis")
    logger.info("[DEBUG] _run_ai_analysis: img_path=%s provider=%s cwd=%s", img_path, provider, os.getcwd())

    # Log key environment variables with API keys masked
    safe_env = {k: ("***" if "KEY" in k else v) for k, v in os.environ.items()}
    logger.info("[DEBUG] ENV: %s", safe_env)

    if not img_path.exists():
        logger.warning("[DEBUG] Image path does not exist: %s", img_path)

    if provider == "openai":
        script_path = config.SCRIPTS_DIR / "analyze_artwork.py"
        cmd = [
            "python3",
            str(script_path),
            str(img_path),
            "--provider",
            "openai",
            "--json-output",
        ]
    elif provider == "google":
        script_path = config.SCRIPTS_DIR / "analyze_artwork_google.py"
        cmd = ["python3", str(script_path), str(img_path)]
    else:
        raise ValueError(f"Unknown provider: {provider}")

    logger.info("[DEBUG] Subprocess cmd: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        logger.error("AI analysis subprocess timed out for %s", img_path)
        raise RuntimeError("AI analysis timed out after 300 seconds")
    except Exception as exc:  # noqa: BLE001 - unexpected OSError
        logger.error("Subprocess execution failed: %s", exc)
        raise RuntimeError(str(exc)) from exc

    logger.info("[DEBUG] Returncode: %s", result.returncode)
    logger.info("[DEBUG] STDOUT: %s", result.stdout[:2000])
    logger.info("[DEBUG] STDERR: %s", result.stderr[:2000])

    output = result.stdout.strip()
    logger.info("AI Analysis Output: %s", output)

    if result.returncode != 0:
        try:
            err = json.loads(result.stderr)
            msg = err.get("error", "Unknown error")
        except Exception:
            msg = (result.stderr or "Unknown error").strip()
        raise RuntimeError(f"AI analysis failed: {msg}")

    if not output:
        raise RuntimeError("AI analysis failed. Please try again.")

    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s", e)
        raise RuntimeError("AI analysis output could not be parsed.")


def _generate_composites(seo_folder: str, log_id: str) -> None:
    cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=utils.BASE_DIR,
        timeout=600,
    )
    composite_log = utils.LOGS_DIR / f"composite_gen_{log_id}.log"
    with open(composite_log, "w") as log:
        log.write("=== STDOUT ===\n")
        log.write(result.stdout)
        log.write("\n\n=== STDERR ===\n")
        log.write(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Composite generation failed ({result.returncode})")


def validate_listing_fields(data: dict, generic_text: str) -> list[str]:
    """Return a list of validation error messages for the listing."""
    errors: list[str] = []

    title = data.get("title", "").strip()
    if not title:
        errors.append("Title cannot be blank")
    if len(title) > 140:
        errors.append("Title exceeds 140 characters")

    tags = data.get("tags", [])
    if len(tags) > 13:
        errors.append("Too many tags (max 13)")
    seen = set()
    for t in tags:
        if not t or len(t) > 20:
            errors.append(f"Invalid tag: '{t}'")
        if "-" in t or "," in t:
            errors.append(f"Tag may not contain hyphens or commas: '{t}'")
        if not re.fullmatch(r"[A-Za-z0-9 ]+", t):
            errors.append(f"Tag has invalid characters: '{t}'")
        low = t.lower()
        if low in seen:
            errors.append(f"Duplicate tag: '{t}'")
        seen.add(low)

    materials = data.get("materials", [])
    if len(materials) > 13:
        errors.append("Too many materials (max 13)")
    seen_mats = set()
    for m in materials:
        if len(m) > 45:
            errors.append(f"Material too long: '{m}'")
        if not re.fullmatch(r"[A-Za-z0-9 ,]+", m):
            errors.append(f"Material has invalid characters: '{m}'")
        ml = m.lower()
        if ml in seen_mats:
            errors.append(f"Duplicate material: '{m}'")
        seen_mats.add(ml)

    seo_filename = data.get("seo_filename", "")
    if len(seo_filename) > 70:
        errors.append("SEO filename exceeds 70 characters")
    if " " in seo_filename or not re.fullmatch(r"[A-Za-z0-9.-]+", seo_filename):
        errors.append("SEO filename has invalid characters or spaces")
    if not re.search(
        r"Artwork-by-Robin-Custance-RJC-[A-Za-z0-9-]+\.jpg$", seo_filename
    ):
        errors.append(
            "SEO filename must end with 'Artwork-by-Robin-Custance-RJC-XXXX.jpg'"
        )

    sku = data.get("sku", "")
    if not sku:
        errors.append("SKU is required")
    if len(sku) > 32 or not re.fullmatch(r"[A-Za-z0-9-]+", sku):
        errors.append("SKU must be <=32 chars and alphanumeric/hyphen")
    if sku and not sku.startswith("RJC-"):
        errors.append("SKU must start with 'RJC-'")
    if sku and infer_sku_from_filename(seo_filename or "") != sku:
        errors.append("SKU must match value in SEO filename")

    try:
        price = float(data.get("price"))
        if abs(price - 17.88) > 1e-2:
            errors.append("Price must be 17.88")
    except Exception:
        errors.append("Price must be a number (17.88)")

    for colour_key in ("primary_colour", "secondary_colour"):
        col = data.get(colour_key, "").strip()
        if not col:
            errors.append(f"{colour_key.replace('_', ' ').title()} is required")
            continue
        if col.lower() not in ALLOWED_COLOURS_LOWER:
            errors.append(f"{colour_key.replace('_', ' ').title()} invalid")

    images = [i.strip() for i in data.get("images", []) if str(i).strip()]
    if not images:
        errors.append("At least one image required")
    for img in images:
        if " " in img or not re.search(r"\.(jpg|jpeg|png)$", img, re.I):
            errors.append(f"Invalid image filename: '{img}'")
        if not is_finalised_image(img):
            errors.append(f"Image not in finalised-artwork folder: '{img}'")

    desc = data.get("description", "").strip()
    if len(desc.split()) < 400:
        errors.append("Description must be at least 400 words")
    GENERIC_MARKER = "About the Artist – Robin Custance"
    if generic_text:
        # Normalise whitespace for both description and generic block
        desc_norm = " ".join(desc.split()).lower()
        generic_norm = " ".join(generic_text.split()).lower()
        # Only require that the generic marker exists somewhere in the description (case-insensitive)
        if GENERIC_MARKER.lower() not in desc_norm:
            errors.append(
                f"Description must include the correct generic context block: {GENERIC_MARKER}"
            )
        if "<" in desc or ">" in desc:
            errors.append("Description may not contain HTML")

        return errors


def get_categories_for_aspect(aspect: str) -> list[str]:
    """Return list of mockup categories available for the given aspect."""

    logger = logging.getLogger(__name__)
    logger.debug("[DEBUG] get_categories_for_aspect: aspect=%s", aspect)

    base = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised"
    if not base.exists():
        logger.warning("[DEBUG] Category folder missing: %s", base)
        base = config.MOCKUPS_CATEGORISED_DIR / "4x5-categorised"
        if not base.exists():
            logger.error("[DEBUG] Default category folder also missing: %s", base)
            return []

    cats = [f.name for f in base.iterdir() if f.is_dir()]
    cats = sorted(cats)[:25]
    logger.debug("[DEBUG] categories resolved: %s", cats)
    return cats


@bp.app_context_processor
def inject_latest_artwork():
    latest = utils.latest_analyzed_artwork()
    return dict(latest_artwork=latest)


@bp.route("/")
def home():
    latest = utils.latest_analyzed_artwork()
    return render_template("index.html", menu=utils.get_menu(), latest_artwork=latest)


@bp.route("/upload", methods=["GET", "POST"])
def upload_artwork():
    """Upload new artwork files and run pre-QC then AI analysis."""
    if request.method == "POST":
        files = request.files.getlist("images")
        folder = utils.create_unanalysed_subfolder()
        results = []
        user = session.get("username")
        for f in files:
            try:
                res = _process_upload_file(f, folder)
            except Exception as exc:  # noqa: BLE001 - unexpected IO
                logging.getLogger(__name__).error(
                    "Upload processing failed for %s: %s", f.filename, exc
                )
                res = {"original": f.filename, "success": False, "error": str(exc)}
            status = "success" if res.get("success") else "fail"
            log_action(
                "upload",
                res.get("original", f.filename),
                user,
                res.get("error", "uploaded"),
                status=status,
                error=res.get("error") if not res.get("success") else None,
            )
            results.append(res)

        if (
            request.accept_mimetypes.accept_json
            and not request.accept_mimetypes.accept_html
        ):
            return json.dumps(results), 200, {"Content-Type": "application/json"}

        successes = [r for r in results if r["success"]]
        if successes:
            flash(f"Uploaded {len(successes)} file(s) successfully", "success")
        failures = [r for r in results if not r["success"]]
        for f in failures:
            flash(f"{f['original']}: {f['error']}", "danger")

        if request.accept_mimetypes.accept_html:
            return redirect(url_for("artwork.artworks"))
        return json.dumps(results), 200, {"Content-Type": "application/json"}
    return render_template("upload.html", menu=utils.get_menu())


@bp.route("/artworks")
def artworks():
    processed, processed_names = utils.list_processed_artworks()
    ready = utils.list_ready_to_analyze(processed_names)
    finalised = utils.list_finalised_artworks()
    return render_template(
        "artworks.html",
        ready_artworks=ready,
        processed_artworks=processed,
        finalised_artworks=finalised,
        menu=utils.get_menu(),
    )


@bp.route("/select", methods=["GET", "POST"])
def select():
    if "slots" not in session or request.args.get("reset") == "1":
        utils.init_slots()
    slots = session["slots"]
    options = utils.compute_options(slots)
    zipped = list(zip(slots, options))
    return render_template("mockup_selector.html", zipped=zipped, menu=utils.get_menu())


@bp.route("/regenerate", methods=["POST"])
def regenerate():
    slot_idx = int(request.form["slot"])
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        cat = slots[slot_idx]["category"]
        slots[slot_idx]["image"] = utils.random_image(cat)
        session["slots"] = slots
    return redirect(url_for("artwork.select"))


@bp.route("/swap", methods=["POST"])
def swap():
    slot_idx = int(request.form["slot"])
    new_cat = request.form["new_category"]
    slots = session.get("slots", [])
    if 0 <= slot_idx < len(slots):
        slots[slot_idx]["category"] = new_cat
        slots[slot_idx]["image"] = utils.random_image(new_cat)
        session["slots"] = slots
    return redirect(url_for("artwork.select"))


@bp.route("/proceed", methods=["POST"])
def proceed():
    slots = session.get("slots", [])
    if not slots:
        flash("No mockups selected!", "danger")
        return redirect(url_for("artwork.select"))
    utils.SELECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    selection_id = str(uuid.uuid4())
    selection_file = utils.SELECTIONS_DIR / f"{selection_id}.json"
    with open(selection_file, "w") as f:
        json.dump(slots, f, indent=2)
    log_file = utils.LOGS_DIR / f"composites_{selection_id}.log"
    try:
        result = subprocess.run(
            ["python3", str(utils.GENERATE_SCRIPT_PATH), str(selection_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=utils.BASE_DIR,
        )
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode == 0:
            flash("Composites generated successfully!", "success")
        else:
            flash("Composite generation failed. See logs for details.", "danger")
    except Exception as e:
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash("Error running the composite generator.", "danger")

    latest = utils.latest_composite_folder()
    if latest:
        session["latest_seo_folder"] = latest
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    return redirect(url_for("artwork.composites_preview"))


@bp.route("/analyze/<aspect>/<filename>", methods=["POST"], endpoint="analyze_artwork")
def analyze_artwork_route(aspect, filename):
    """Run analysis on ``filename`` using the selected provider."""

    logger = logging.getLogger(__name__)

    provider = request.form.get("provider", "openai").lower()
    base_name = Path(filename).name

    _write_analysis_status("starting", 0, base_name, status="analyzing")

    # ------------------------------------------------------------------
    # Locate the source image from temporary uploads or processed output
    # ------------------------------------------------------------------
    src_path: Path | None = next(
        (p for p in config.UNANALYSED_ROOT.rglob(base_name) if p.is_file()), None
    )
    if not src_path.exists():
        src_path = None
        try:
            seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
            candidate = PROCESSED_ROOT / seo_folder / f"{Path(filename).stem}.jpg"
            if candidate.exists():
                src_path = candidate
        except FileNotFoundError:
            pass

    if not src_path or not src_path.exists():
        flash(f"Artwork file not found: {filename}", "danger")
        _write_analysis_status(
            "failed", 100, base_name, status="failed", error="file not found"
        )
        return redirect(url_for("artwork.artworks"))

    # ------------------------------------------------------------------
    # Copy file to provider input folder
    # ------------------------------------------------------------------
    dest_dir = UNANALYSED_ROOT / provider
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / base_name

    try:
        shutil.copy2(src_path, dest_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed copying %s to %s: %s", src_path, dest_path, exc)
        flash(f"Failed preparing file for analysis: {exc}", "danger")
        _write_analysis_status(
            "failed", 100, base_name, status="failed", error=str(exc)
        )
        return redirect(url_for("artwork.artworks"))

    # ------------------------------------------------------------------
    # Invoke the analyzer script with the provider-specific path
    # ------------------------------------------------------------------
    log_id = uuid.uuid4().hex
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"

    try:
        if provider == "google":
            script = config.SCRIPTS_DIR / "analyze_artwork_google.py"
            cmd = ["python3", str(script), str(dest_path)]
        else:
            cmd = [
                "python3",
                str(utils.ANALYZE_SCRIPT_PATH),
                str(dest_path),
                "--provider",
                "openai",
            ]
        env = os.environ.copy()
        env["USER_ID"] = session.get("user", "anonymous")
        _write_analysis_status(f"{provider}_call", 20, base_name, status="analyzing")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            env=env,
        )
        with open(log_file, "w", encoding="utf-8") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash(f"❌ Analysis failed for {filename}: {result.stderr}", "danger")
            _write_analysis_status(
                "failed",
                100,
                base_name,
                status="failed",
                error=result.stderr.strip(),
            )
            return redirect(
                url_for("artwork.edit_listing", aspect=aspect, filename=filename)
            )
    except Exception as exc:  # noqa: BLE001
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"\n\n=== Exception ===\n{exc}")
        logger.error("Error running analysis for %s: %s", filename, exc)
        flash(f"❌ Error running analysis: {exc}", "danger")
        _write_analysis_status(
            "failed", 100, base_name, status="failed", error=str(exc)
        )
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )

    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash(
            f"Analysis complete, but no SEO folder/listing found for {filename} ({aspect}).",
            "warning",
        )
        return redirect(url_for("artwork.artworks"))

    listing_path = (
        utils.PROCESSED_ROOT
        / seo_folder
        / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_folder)
    )
    new_filename = f"{seo_folder}.jpg"
    try:
        data = utils.load_json_file_safe(listing_path)
        new_filename = data.get("seo_filename", new_filename)
    except Exception:
        pass

    try:
        cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
        _write_analysis_status("generating", 60, filename, status="analyzing")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=utils.BASE_DIR,
            timeout=600,
        )
        composite_log_file = utils.LOGS_DIR / f"composite_gen_{log_id}.log"
        with open(composite_log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash("Artwork analyzed, but mockup generation failed. See logs.", "danger")
    except Exception as e:
        flash(f"Composites generation error: {e}", "danger")

    _write_analysis_status("done", 100, filename, status="complete")
    return redirect(
        url_for("artwork.edit_listing", aspect=aspect, filename=new_filename)
    )


@bp.post("/analyze-upload/<base>")
def analyze_upload(base):
    """Analyze an uploaded image from the unanalysed folder."""
    uid, rec = utils.get_record_by_base(base)
    if not rec:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    folder = Path(rec["current_folder"])
    qc_path = folder / f"{base}.qc.json"
    try:
        qc = utils.load_json_file_safe(qc_path)
    except Exception:
        flash("Invalid QC data", "danger")
        return redirect(url_for("artwork.artworks"))

    ext = qc.get("extension", "jpg")
    orig_path = folder / f"{base}.{ext}"
    processed_root = PROCESSED_ROOT
    log_id = uuid.uuid4().hex
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"
    provider = request.form.get("provider", "openai")
    _write_analysis_status("starting", 0, orig_path.name, status="analyzing")
    try:
        if provider == "google":
            script = config.SCRIPTS_DIR / "analyze_artwork_google.py"
            cmd = ["python3", str(script), str(orig_path)]
        else:
            cmd = [
                "python3",
                str(utils.ANALYZE_SCRIPT_PATH),
                str(orig_path),
                "--provider",
                "openai",
            ]
        env = os.environ.copy()
        env["USER_ID"] = session.get("user", "anonymous")
        _write_analysis_status(
            f"{provider}_call", 20, orig_path.name, status="analyzing"
        )
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            env=env,
        )
        with open(log_file, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash(f"❌ Analysis failed: {result.stderr}", "danger")
            _write_analysis_status(
                "failed",
                100,
                orig_path.name,
                status="failed",
                error=result.stderr.strip(),
            )
            return redirect(url_for("artwork.artworks"))
    except Exception as e:  # noqa: BLE001
        with open(log_file, "a") as log:
            log.write(f"\n\n=== Exception ===\n{str(e)}")
        flash(f"❌ Error running analysis: {e}", "danger")
        _write_analysis_status(
            "failed", 100, orig_path.name, status="failed", error=str(e)
        )
        return redirect(url_for("artwork.artworks"))

    try:
        seo_folder = utils.find_seo_folder_from_filename(
            qc.get("aspect_ratio", ""), orig_path.name
        )
    except FileNotFoundError:
        flash(
            f"Analysis complete, but no SEO folder/listing found for {orig_path.name} ({qc.get('aspect_ratio','')}).",
            "warning",
        )
        return redirect(url_for("artwork.artworks"))

    listing_data = None
    listing_path = (
        utils.PROCESSED_ROOT
        / seo_folder
        / config.FILENAME_TEMPLATES["listing_json"].format(seo_slug=seo_folder)
    )
    if listing_path.exists():
        # Use helper to guarantee a dict and avoid list-index errors
        listing_data = utils.load_json_file_safe(listing_path)

    for suffix in [f".{ext}", "-thumb.jpg", "-analyse.jpg", ".qc.json"]:
        temp_file = folder / f"{base}{suffix}"
        if not temp_file.exists():
            continue
        template_key = (
            "analyse"
            if suffix == "-analyse.jpg"
            else (
                "thumbnail"
                if suffix == "-thumb.jpg"
                else "qc_json" if suffix.endswith(".qc.json") else "artwork"
            )
        )
        dest = (
            processed_root
            / seo_folder
            / config.FILENAME_TEMPLATES.get(template_key).format(seo_slug=seo_folder)
        )
        if suffix == "-analyse.jpg" and dest.exists():
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            dest = dest.with_name(f"{dest.stem}-{ts}{dest.suffix}")
        utils.move_and_log(temp_file, dest, uid, "processed")

    try:
        cmd = ["python3", str(utils.GENERATE_SCRIPT_PATH), seo_folder]
        _write_analysis_status("generating", 60, orig_path.name, status="analyzing")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=utils.BASE_DIR,
            timeout=600,
        )
        composite_log = utils.LOGS_DIR / f"composite_gen_{log_id}.log"
        with open(composite_log, "w") as log:
            log.write("=== STDOUT ===\n")
            log.write(result.stdout)
            log.write("\n\n=== STDERR ===\n")
            log.write(result.stderr)
        if result.returncode != 0:
            flash("Artwork analyzed, but mockup generation failed.", "danger")
    except Exception as e:  # noqa: BLE001
        flash(f"Composites generation error: {e}", "danger")

    utils.cleanup_unanalysed_folders()

    aspect = (
        listing_data.get("aspect_ratio", qc.get("aspect_ratio", ""))
        if listing_data
        else qc.get("aspect_ratio", "")
    )
    new_filename = f"{seo_folder}.jpg"
    if listing_data:
        new_filename = listing_data.get("seo_filename", new_filename)
    _write_analysis_status("done", 100, orig_path.name, status="complete")
    return redirect(
        url_for("artwork.edit_listing", aspect=aspect, filename=new_filename)
    )


@bp.route("/review/<aspect>/<filename>")
def review_artwork(aspect, filename):
    """Legacy URL – redirect to the new edit/review page."""
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/review/<aspect>/<filename>/regenerate/<int:slot_idx>", methods=["POST"])
def review_regenerate_mockup(aspect, filename, slot_idx):
    seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    utils.regenerate_one_mockup(seo_folder, slot_idx)
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/review/<seo_folder>/swap/<int:slot_idx>", methods=["POST"])
def review_swap_mockup(seo_folder, slot_idx):
    new_cat = request.form["new_category"]
    success = utils.swap_one_mockup(seo_folder, slot_idx, new_cat)

    info = utils.find_aspect_filename_from_seo_folder(seo_folder)

    if (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    ):
        img_url = ""
        if success and info:
            aspect, _filename = info
            folder = utils.PROCESSED_ROOT / seo_folder
            listing = folder / f"{seo_folder}-listing.json"
            if not listing.exists():
                folder = utils.FINALISED_ROOT / seo_folder
                listing = folder / f"{seo_folder}-listing.json"
            try:
                data = utils.load_json_file_safe(listing)
                mp = data.get("mockups", [])[slot_idx]
                if isinstance(mp, dict):
                    comp = mp.get("composite")
                    if comp:
                        img_url = url_for(
                            "artwork.processed_image",
                            seo_folder=seo_folder,
                            filename=comp,
                        )
            except Exception:  # noqa: BLE001
                img_url = ""
        return jsonify({"success": success, "img_url": img_url})

    if not success:
        flash("Failed to swap mockup", "danger")

    if info:
        aspect, filename = info
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )

    flash(
        "Could not locate the correct artwork for editing after swap. Please check the gallery.",
        "warning",
    )
    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/edit-listing/<aspect>/<filename>", methods=["GET", "POST"])
def edit_listing(aspect, filename):
    """Display and update a processed or finalised artwork listing."""

    try:
        seo_folder, folder, listing_path, finalised = utils.resolve_listing_paths(
            aspect, filename
        )
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))

    try:
        data = utils.load_json_file_safe(listing_path)
    except Exception as e:  # noqa: BLE001
        flash(f"Error loading listing: {e}", "danger")
        return redirect(url_for("artwork.artworks"))

    generic_text = read_generic_text(aspect)
    if generic_text:
        data["generic_text"] = generic_text

    openai_info = data.get("openai_analysis")

    if request.method == "POST":
        action = request.form.get("action", "save")

        seo_field = request.form.get(
            "seo_filename", data.get("seo_filename", f"{seo_folder}.jpg")
        ).strip()
        # SKU comes exclusively from the listing JSON; users cannot edit it
        sku_val = str(data.get("sku", "")).strip()
        inferred = infer_sku_from_filename(seo_field) or ""
        if sku_val and inferred and sku_val != inferred:
            sku_val = inferred
            flash("SKU updated to match SEO filename", "info")
        elif not sku_val:
            sku_val = inferred
        seo_val = sync_filename_with_sku(seo_field, sku_val)

        form_data = {
            "title": request.form.get("title", data.get("title", "")).strip(),
            "description": request.form.get(
                "description", data.get("description", "")
            ).strip(),
            "tags": parse_csv_list(request.form.get("tags", "")),
            "materials": parse_csv_list(request.form.get("materials", "")),
            "primary_colour": request.form.get(
                "primary_colour", data.get("primary_colour", "")
            ).strip(),
            "secondary_colour": request.form.get(
                "secondary_colour", data.get("secondary_colour", "")
            ).strip(),
            "seo_filename": seo_val,
            "price": request.form.get("price", data.get("price", "17.88")).strip(),
            "sku": sku_val,
            "images": [
                i.strip()
                for i in request.form.get("images", "").splitlines()
                if i.strip()
            ],
        }

        form_data["tags"], cleaned_tags = clean_terms(form_data["tags"])
        form_data["materials"], cleaned_mats = clean_terms(form_data["materials"])
        if cleaned_tags:
            flash(f"Cleaned tags: {join_csv_list(form_data['tags'])}", "success")
        if cleaned_mats:
            flash(
                f"Cleaned materials: {join_csv_list(form_data['materials'])}", "success"
            )

        if action == "delete":
            shutil.rmtree(utils.PROCESSED_ROOT / seo_folder, ignore_errors=True)
            shutil.rmtree(utils.FINALISED_ROOT / seo_folder, ignore_errors=True)
            try:
                os.remove(utils.UNANALYSED_ROOT / aspect / filename)
            except Exception:
                pass
            flash("Artwork deleted", "success")
            log_action("edits", filename, session.get("username"), "deleted listing")
            return redirect(url_for("artwork.artworks"))

        folder.mkdir(parents=True, exist_ok=True)
        img_files = [
            p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        form_data["images"] = [relative_to_base(p) for p in sorted(img_files)]

        errors = validate_listing_fields(form_data, generic_text)
        if errors:
            form_data["images"] = "\n".join(form_data.get("images", []))
            form_data["tags"] = join_csv_list(form_data.get("tags", []))
            form_data["materials"] = join_csv_list(form_data.get("materials", []))
            mockups = []
            for idx, mp in enumerate(data.get("mockups", [])):
                if isinstance(mp, dict):
                    out = folder / mp.get("composite", "")
                    cat = mp.get("category", "")
                else:
                    p = Path(mp)
                    out = folder / f"{seo_folder}-{p.stem}.jpg"
                    cat = p.parent.name
                tid = re.search(r"(\d+)$", out.stem)
                thumb = folder / "THUMBS" / f"{seo_folder}-{aspect}-mockup-thumb-{tid.group(1) if tid else idx}.jpg"
                mockups.append(
                    {
                        "path": out,
                        "category": cat,
                        "exists": out.exists(),
                        "index": idx,
                        "thumb": thumb,
                        "thumb_exists": thumb.exists(),
                    }
                )
            return render_template(
                "edit_listing.html",
                artwork=form_data,
                errors=errors,
                aspect=aspect,
                filename=filename,
                seo_folder=seo_folder,
                mockups=mockups,
                menu=utils.get_menu(),
                colour_options=get_allowed_colours(),
                categories=get_categories_for_aspect(aspect),
                finalised=finalised,
                locked=data.get("locked", False),
                editable=not data.get("locked", False),
                openai_analysis=openai_info,
                cache_ts=int(time.time()),
            )

        data.update(form_data)
        data["generic_text"] = generic_text

        full_desc = re.sub(r"\s+$", "", form_data["description"])
        gen = generic_text.strip()
        if gen and not full_desc.endswith(gen):
            full_desc = re.sub(r"\n{3,}", "\n\n", full_desc.rstrip()) + "\n\n" + gen
        data["description"] = full_desc.strip()

        with open(listing_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        flash("Listing updated", "success")
        log_action("edits", filename, session.get("username"), "listing updated")
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )

    raw_ai = data.get("ai_listing")
    ai = {}
    fallback_ai: dict = {}

    def parse_fallback(text: str) -> dict:
        match = re.search(r"```json\s*({.*?})\s*```", text, re.DOTALL)
        if not match:
            match = re.search(r"({.*})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                return {}
        return {}

    if isinstance(raw_ai, dict):
        ai = raw_ai
        if isinstance(raw_ai.get("fallback_text"), str):
            fallback_ai.update(parse_fallback(raw_ai.get("fallback_text")))
    elif isinstance(raw_ai, str):
        try:
            ai = json.loads(raw_ai)
        except Exception:
            fallback_ai.update(parse_fallback(raw_ai))

    if isinstance(data.get("fallback_text"), str):
        fallback_ai.update(parse_fallback(data["fallback_text"]))

    price = data.get("price") or ai.get("price") or fallback_ai.get("price") or "17.88"
    sku = (
        data.get("sku")
        or ai.get("sku")
        or fallback_ai.get("sku")
        or infer_sku_from_filename(data.get("seo_filename", ""))
        or ""
    )
    primary = (
        data.get("primary_colour")
        or ai.get("primary_colour")
        or fallback_ai.get("primary_colour", "")
    )
    secondary = (
        data.get("secondary_colour")
        or ai.get("secondary_colour")
        or fallback_ai.get("secondary_colour", "")
    )

    images = data.get("images")
    if not images:
        imgs = [
            p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        images = [relative_to_base(p) for p in sorted(imgs)]
    else:
        images = [relative_to_base(Path(p)) for p in images]

    artwork = {
        "title": data.get("title") or ai.get("title") or fallback_ai.get("title", ""),
        "description": data.get("description")
        or ai.get("description")
        or fallback_ai.get("description", ""),
        "tags": join_csv_list(
            data.get("tags") or ai.get("tags") or fallback_ai.get("tags", [])
        ),
        "materials": join_csv_list(
            data.get("materials")
            or ai.get("materials")
            or fallback_ai.get("materials", [])
        ),
        "primary_colour": primary,
        "secondary_colour": secondary,
        "seo_filename": data.get("seo_filename")
        or ai.get("seo_filename")
        or fallback_ai.get("seo_filename")
        or f"{seo_folder}.jpg",
        "price": price,
        "sku": sku,
        "images": "\n".join(images),
    }

    if not artwork.get("title"):
        artwork["title"] = seo_folder.replace("-", " ").title()
    if not artwork.get("description"):
        artwork["description"] = (
            "(No description found. Try re-analyzing or check AI output.)"
        )

    artwork["full_listing_text"] = utils.build_full_listing_text(
        artwork.get("description", ""), data.get("generic_text", "")
    )

    mockups = []
    for idx, mp in enumerate(data.get("mockups", [])):
        if isinstance(mp, dict):
            out = folder / mp.get("composite", "")
            cat = mp.get("category", "")
        else:
            p = Path(mp)
            out = folder / f"{seo_folder}-{p.stem}.jpg"
            cat = p.parent.name
        tid = re.search(r"(\d+)$", out.stem)
        thumb = folder / "THUMBS" / f"{seo_folder}-{aspect}-mockup-thumb-{tid.group(1) if tid else idx}.jpg"
        mockups.append(
            {
                "path": out,
                "category": cat,
                "exists": out.exists(),
                "index": idx,
                "thumb": thumb,
                "thumb_exists": thumb.exists(),
            }
        )
    return render_template(
        "edit_listing.html",
        artwork=artwork,
        aspect=aspect,
        filename=filename,
        seo_folder=seo_folder,
        mockups=mockups,
        menu=utils.get_menu(),
        errors=None,
        colour_options=get_allowed_colours(),
        categories=get_categories_for_aspect(aspect),
        finalised=finalised,
        locked=data.get("locked", False),
        editable=not data.get("locked", False),
        openai_analysis=openai_info,
        cache_ts=int(time.time()),
    )


_PROCESSED_REL = PROCESSED_ROOT.relative_to(BASE_DIR).as_posix()
_FINALISED_REL = FINALISED_ROOT.relative_to(BASE_DIR).as_posix()
_LOCKED_REL = utils.ARTWORK_VAULT_ROOT.relative_to(BASE_DIR).as_posix()


@bp.route(f"/static/{_PROCESSED_REL}/<seo_folder>/<filename>")
def processed_image(seo_folder, filename):
    """Serve artwork images from processed or finalised folders."""
    final_folder = utils.FINALISED_ROOT / seo_folder
    if (final_folder / filename).exists():
        folder = final_folder
    else:
        folder = utils.PROCESSED_ROOT / seo_folder
    file_path = folder / filename
    if not file_path.exists():
        current_app.logger.error("Image not found: %s", file_path)
        return "", 404
    return send_from_directory(folder, filename)


@bp.route(f"/static/{_FINALISED_REL}/<seo_folder>/<filename>")
def finalised_image(seo_folder, filename):
    """Serve images strictly from the finalised-artwork folder."""
    folder = utils.FINALISED_ROOT / seo_folder
    return send_from_directory(folder, filename)


@bp.route(f"/static/{_LOCKED_REL}/<seo_folder>/<filename>")
def locked_image(seo_folder, filename):
    """Serve images from the locked artwork vault."""
    folder = utils.ARTWORK_VAULT_ROOT / seo_folder
    return send_from_directory(folder, filename)


@bp.route("/thumbs/<seo_folder>/<filename>")
def serve_mockup_thumb(seo_folder: str, filename: str):
    """Serve mockup thumbnails from the THUMBS directory."""
    thumb_folder = utils.PROCESSED_ROOT / seo_folder / "THUMBS"
    return send_from_directory(thumb_folder, filename)


@bp.route("/artwork-img/<aspect>/<filename>")
def artwork_image(aspect, filename):
    folder = utils.UNANALYSED_ROOT / aspect
    candidate = folder / filename
    if candidate.exists():
        return send_from_directory(str(folder.resolve()), filename)
    alt_folder = utils.UNANALYSED_ROOT / f"{aspect}-artworks" / Path(filename).stem
    candidate = alt_folder / filename
    if candidate.exists():
        return send_from_directory(str(alt_folder.resolve()), filename)
    return "", 404


@bp.route("/unanalysed-img/<filename>")
def unanalysed_image(filename: str):
    """Serve images from the unanalysed artwork folders."""
    path = next(
        (p for p in config.UNANALYSED_ROOT.rglob(filename) if p.is_file()), None
    )
    if path:
        return send_from_directory(path.parent, path.name)
    abort(404)


@bp.route("/mockup-img/<category>/<filename>")
def mockup_img(category, filename):
    return send_from_directory(utils.MOCKUPS_DIR / category, filename)


@bp.route("/composite-img/<folder>/<filename>")
def composite_img(folder, filename):
    return send_from_directory(utils.COMPOSITES_DIR / folder, filename)


@bp.route("/composites")
def composites_preview():
    latest = utils.latest_composite_folder()
    if latest:
        return redirect(url_for("artwork.composites_specific", seo_folder=latest))
    flash("No composites found", "warning")
    return redirect(url_for("artwork.artworks"))


@bp.route("/composites/<seo_folder>")
def composites_specific(seo_folder):
    folder = utils.PROCESSED_ROOT / seo_folder
    json_path = folder / f"{seo_folder}-listing.json"
    images = []
    if json_path.exists():
        listing = utils.load_json_file_safe(json_path)
        for idx, mp in enumerate(listing.get("mockups", [])):
            if isinstance(mp, dict):
                out = folder / mp.get("composite", "")
                cat = mp.get("category", "")
            else:
                p = Path(mp)
                out = folder / f"{seo_folder}-{p.stem}.jpg"
                cat = p.parent.name
            images.append(
                {
                    "filename": out.name,
                    "category": cat,
                    "index": idx,
                    "exists": out.exists(),
                }
            )
    else:
        for idx, img in enumerate(sorted(folder.glob(f"{seo_folder}-mockup-*.jpg"))):
            images.append(
                {"filename": img.name, "category": None, "index": idx, "exists": True}
            )
    return render_template(
        "composites_preview.html",
        images=images,
        folder=seo_folder,
        menu=utils.get_menu(),
    )


@bp.route("/composites/<seo_folder>/regenerate/<int:slot_index>", methods=["POST"])
def regenerate_composite(seo_folder, slot_index):
    utils.regenerate_one_mockup(seo_folder, slot_index)
    return redirect(url_for("artwork.composites_specific", seo_folder=seo_folder))


@bp.route("/approve_composites/<seo_folder>", methods=["POST"])
def approve_composites(seo_folder):
    flash("Composites approved", "success")
    return redirect(url_for("artwork.composites_specific", seo_folder=seo_folder))


@bp.route("/finalise/<aspect>/<filename>", methods=["GET", "POST"])
def finalise_artwork(aspect, filename):
    """Move processed artwork to finalised location and update listing data."""
    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash(f"Artwork not found: {filename}", "danger")
        return redirect(url_for("artwork.artworks"))

    processed_dir = utils.PROCESSED_ROOT / seo_folder
    final_dir = utils.FINALISED_ROOT / seo_folder
    user = session.get("username")

    # ------------------------------------------------------------------
    # Move processed artwork into the finalised location and update paths
    # ------------------------------------------------------------------
    try:
        if final_dir.exists():
            raise FileExistsError(f"{final_dir} already exists")

        shutil.move(str(processed_dir), str(final_dir))
        uid, _rec = utils.get_record_by_seo_filename(filename)
        if uid:
            utils.update_status(uid, final_dir, "finalised")

        # Marker file indicating finalisation time
        (final_dir / "finalised.txt").write_text(
            datetime.datetime.now().isoformat(), encoding="utf-8"
        )

        # Remove original artwork from input directory if it still exists
        orig_input = utils.UNANALYSED_ROOT / aspect / filename
        try:
            os.remove(orig_input)
        except FileNotFoundError:
            pass

        # Update any stored paths within the listing JSON
        listing_file = final_dir / f"{seo_folder}-listing.json"
        if listing_file.exists():
            # Always allocate a fresh SKU on finalisation
            utils.assign_or_get_sku(listing_file, config.SKU_TRACKER, force=True)
            listing_data = utils.load_json_file_safe(listing_file)
            listing_data.setdefault("locked", False)

            def _swap_path(p: str) -> str:
                return p.replace(str(utils.PROCESSED_ROOT), str(utils.FINALISED_ROOT))

            for key in (
                "main_jpg_path",
                "orig_jpg_path",
                "thumb_jpg_path",
                "processed_folder",
            ):
                if isinstance(listing_data.get(key), str):
                    listing_data[key] = _swap_path(listing_data[key])

            if isinstance(listing_data.get("images"), list):
                listing_data["images"] = [
                    _swap_path(img) if isinstance(img, str) else img
                    for img in listing_data["images"]
                ]

            imgs = [
                p
                for p in final_dir.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ]
            listing_data["images"] = [utils.relative_to_base(p) for p in sorted(imgs)]

            with open(listing_file, "w", encoding="utf-8") as lf:
                json.dump(listing_data, lf, indent=2, ensure_ascii=False)

        log_action("finalise", filename, user, f"finalised to {final_dir}")
        flash("Artwork finalised", "success")
    except Exception as e:  # noqa: BLE001
        log_action(
            "finalise", filename, user, "finalise failed", status="fail", error=str(e)
        )
        flash(f"Failed to finalise artwork: {e}", "danger")

    return redirect(url_for("artwork.finalised_gallery"))


@bp.route("/finalised")
def finalised_gallery():
    """Display all finalised artworks in a gallery view."""
    artworks = []
    if utils.FINALISED_ROOT.exists():
        for folder in utils.FINALISED_ROOT.iterdir():
            if not folder.is_dir():
                continue
            listing_file = folder / f"{folder.name}-listing.json"
            if not listing_file.exists():
                continue
            try:
                data = utils.load_json_file_safe(listing_file)
            except Exception:
                continue
            entry = {
                "seo_folder": folder.name,
                "title": data.get("title") or utils.prettify_slug(folder.name),
                "description": data.get("description", ""),
                "sku": data.get("sku", ""),
                "primary_colour": data.get("primary_colour", ""),
                "secondary_colour": data.get("secondary_colour", ""),
                "price": data.get("price", ""),
                "seo_filename": data.get("seo_filename", f"{folder.name}.jpg"),
                "tags": data.get("tags", []),
                "materials": data.get("materials", []),
                "aspect": data.get("aspect_ratio", ""),
                "filename": data.get("filename", f"{folder.name}.jpg"),
                "locked": data.get("locked", False),
                "mockups": [],
            }

            for mp in data.get("mockups", []):
                if isinstance(mp, dict):
                    out = folder / mp.get("composite", "")
                else:
                    p = Path(mp)
                    out = folder / f"{folder.name}-{p.stem}.jpg"
                if out.exists():
                    entry["mockups"].append({"filename": out.name})

            # Filter images that actually exist on disk
            images = []
            for img in data.get("images", []):
                img_path = utils.BASE_DIR / img
                if img_path.exists():
                    images.append(img)
            entry["images"] = images

            ts = folder / "finalised.txt"
            entry["date"] = (
                ts.stat().st_mtime if ts.exists() else listing_file.stat().st_mtime
            )

            main_img = folder / f"{folder.name}.jpg"
            entry["main_image"] = main_img.name if main_img.exists() else None

            artworks.append(entry)
    artworks.sort(key=lambda x: x.get("date", 0), reverse=True)
    return render_template("finalised.html", artworks=artworks, menu=utils.get_menu())


@bp.route("/locked")
def locked_gallery():
    """Show gallery of locked artworks only."""
    locked_items = [
        a for a in utils.list_finalised_artworks_extended() if a.get("locked")
    ]
    return render_template("locked.html", artworks=locked_items, menu=utils.get_menu())


@bp.post("/update-links/<aspect>/<filename>")
def update_links(aspect, filename):
    """Regenerate image URL list from disk for either processed or finalised artwork.

    If the request was sent via AJAX (accepting JSON or using the ``XMLHttpRequest``
    header) the refreshed list of image URLs is returned as JSON rather than
    performing a redirect. This allows the edit page to update the textarea in
    place without losing form state.
    """

    wants_json = (
        "application/json" in request.headers.get("Accept", "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )

    try:
        seo_folder, folder, listing_file, _ = utils.resolve_listing_paths(
            aspect, filename
        )
    except FileNotFoundError:
        msg = "Artwork not found"
        if wants_json:
            return {"success": False, "message": msg, "images": []}, 404
        flash(msg, "danger")
        return redirect(url_for("artwork.artworks"))

    try:
        data = utils.load_json_file_safe(listing_file)
        imgs = [
            p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        data["images"] = [utils.relative_to_base(p) for p in sorted(imgs)]
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        msg = "Image links updated"
        if wants_json:
            return {"success": True, "message": msg, "images": data["images"]}
        flash(msg, "success")
    except Exception as e:  # noqa: BLE001
        msg = f"Failed to update links: {e}"
        if wants_json:
            return {"success": False, "message": msg, "images": []}, 500
        flash(msg, "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/finalise/delete/<aspect>/<filename>")
def delete_finalised(aspect, filename):
    """Delete a finalised artwork folder."""
    try:
        seo_folder = utils.find_seo_folder_from_filename(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.finalised_gallery"))
    folder = utils.FINALISED_ROOT / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    locked = False
    if listing_file.exists():
        try:
            info = utils.load_json_file_safe(listing_file)
            locked = info.get("locked", False)
        except Exception:
            pass
    if locked and request.form.get("confirm") != "DELETE":
        flash("Type DELETE to confirm", "warning")
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )
    try:
        shutil.rmtree(folder)
        flash("Finalised artwork deleted", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Delete failed: {e}", "danger")
    return redirect(url_for("artwork.finalised_gallery"))


@bp.post("/lock/<aspect>/<filename>")
def lock_listing(aspect, filename):
    """Mark a finalised artwork as locked."""
    try:
        seo, folder, listing, finalised = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    if not finalised:
        flash("Artwork must be finalised before locking", "danger")
        return redirect(
            url_for("artwork.edit_listing", aspect=aspect, filename=filename)
        )
    try:
        target = utils.ARTWORK_VAULT_ROOT / f"LOCKED-{seo}"
        utils.ARTWORK_VAULT_ROOT.mkdir(parents=True, exist_ok=True)
        if target.exists():
            idx = 1
            base = target
            while target.exists():
                target = base.with_name(f"{base.name}_{idx}")
                idx += 1
        shutil.move(str(folder), str(target))
        listing = target / f"{seo}-listing.json"
        utils.update_listing_paths(listing, folder, target)
        with open(listing, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["locked"] = True
        with open(listing, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_action("lock", filename, session.get("username"), "locked artwork")
        flash("Artwork locked", "success")
    except Exception as exc:  # noqa: BLE001
        log_action(
            "lock",
            filename,
            session.get("username"),
            "lock failed",
            status="fail",
            error=str(exc),
        )
        flash(f"Failed to lock: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/unlock/<aspect>/<filename>")
def unlock_listing(aspect, filename):
    """Unlock a previously locked artwork."""
    try:
        seo, folder, listing, _ = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    try:
        target = utils.FINALISED_ROOT / seo
        if target.exists():
            idx = 1
            base = target
            while target.exists():
                target = base.with_name(f"{base.name}_{idx}")
                idx += 1
        shutil.move(str(folder), str(target))
        listing = target / f"{seo}-listing.json"
        utils.update_listing_paths(listing, folder, target)
        data = utils.load_json_file_safe(listing)
        data["locked"] = False
        with open(listing, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_action("lock", filename, session.get("username"), "unlocked artwork")
        flash("Artwork unlocked", "success")
    except Exception as exc:  # noqa: BLE001
        log_action(
            "lock",
            filename,
            session.get("username"),
            "unlock failed",
            status="fail",
            error=str(exc),
        )
        flash(f"Failed to unlock: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/reset-sku/<aspect>/<filename>")
def reset_sku(aspect, filename):
    """Force reassign a new SKU for the given artwork."""
    try:
        seo, folder, listing, _ = utils.resolve_listing_paths(aspect, filename)
    except FileNotFoundError:
        flash("Artwork not found", "danger")
        return redirect(url_for("artwork.artworks"))
    try:
        utils.assign_or_get_sku(listing, config.SKU_TRACKER, force=True)
        flash("SKU reset", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Failed to reset SKU: {exc}", "danger")
    return redirect(url_for("artwork.edit_listing", aspect=aspect, filename=filename))


@bp.post("/finalise/push-sellbrite/<aspect>/<filename>")
def push_sellbrite_placeholder(aspect, filename):
    """Placeholder endpoint for future Sellbrite integration."""
    flash("Coming soon!", "info")
    return redirect(url_for("artwork.finalised_gallery"))


@bp.post("/analyze-<provider>/<filename>")
def analyze_api(provider: str, filename: str):
    """Analyze an artwork then redirect or return JSON for editing."""

    logger = logging.getLogger(__name__)
    debug = config.DEBUG
    user = session.get("username")
    logger.info("ROUTE START provider=%s file=%s", provider, filename)
    print(f"ROUTE START provider={provider} file={filename}")

    if provider not in {"openai", "google"}:
        logger.error("Invalid provider %s", provider)
        return jsonify({"success": False, "error": "Invalid provider"}), 400

    if provider == "openai" and not current_app.config.get("OPENAI_CONFIGURED"):
        msg = "OpenAI API Key is not configured"
        _write_analysis_status("failed", 100, filename, status="failed", error=msg)
        log_action("analyse-openai", filename, user, "analysis failed", status="fail", error=msg)
        return jsonify({"success": False, "error": msg}), 400
    if provider == "google" and not current_app.config.get("GOOGLE_CONFIGURED"):
        msg = "Google API Key is not configured"
        _write_analysis_status("failed", 100, filename, status="failed", error=msg)
        log_action("analyse-google", filename, user, "analysis failed", status="fail", error=msg)
        return jsonify({"success": False, "error": msg}), 400

    base = Path(filename).stem
    temp_file = next(
        (p for p in config.UNANALYSED_ROOT.rglob(filename) if p.is_file()), None
    )
    log_id = uuid.uuid4().hex
    log_file = utils.LOGS_DIR / f"analyze_{log_id}.log"

    _write_analysis_status("starting", 0, filename, status="analyzing")

    try:
        if temp_file and temp_file.exists():
            print("Using temporary uploaded file", temp_file)
            qc_path = next(
                (
                    p
                    for p in config.UNANALYSED_ROOT.rglob(f"{base}.qc.json")
                    if p.is_file()
                ),
                None,
            )
            qc = json.load(open(qc_path, "r", encoding="utf-8")) if qc_path else {}
            _write_analysis_status(f"{provider}_call", 20, filename, status="analyzing")
            entry = _run_ai_analysis(temp_file, provider)
            seo_folder = entry["seo_name"]
            listing_json = (
                Path(entry["processed_folder"]) / f"{seo_folder}-listing.json"
            )
            listing = utils.load_json_file_safe(listing_json)
            for suffix in [
                f".{qc.get('extension', 'jpg')}",
                "-thumb.jpg",
                "-analyse.jpg",
                ".qc.json",
            ]:
                src = next(
                    (
                        p
                        for p in config.UNANALYSED_ROOT.rglob(f"{base}{suffix}")
                        if p.is_file()
                    ),
                    None,
                )
                if not src:
                    continue
                key = (
                    "analyse"
                    if suffix == "-analyse.jpg"
                    else (
                        "thumbnail"
                        if suffix == "-thumb.jpg"
                        else "qc_json" if suffix.endswith(".qc.json") else "artwork"
                    )
                )
                dest = Path(entry["processed_folder"]) / config.FILENAME_TEMPLATES[
                    key
                ].format(seo_slug=seo_folder)
                shutil.move(src, dest)
        else:
            print("Resolving processed image for", filename)
            seo_folder, folder, listing_path, _ = utils.resolve_listing_paths(
                "", filename
            )
            img_path = folder / f"{seo_folder}.jpg"
            _write_analysis_status(f"{provider}_call", 20, filename, status="analyzing")
            entry = _run_ai_analysis(img_path, provider)
            seo_folder = entry["seo_name"]
            listing_json = (
                Path(entry["processed_folder"]) / f"{seo_folder}-listing.json"
            )
            listing = utils.load_json_file_safe(listing_json)

        entry = strip_binary(entry)

        with open(log_file, "w", encoding="utf-8") as log:
            log.write(json.dumps(strip_binary(entry), indent=2))

        print("Generating composites for", seo_folder)
        _write_analysis_status("generating", 60, filename, status="analyzing")
        _generate_composites(seo_folder, log_id)
        utils.generate_mockups_for_listing(seo_folder)

        utils.cleanup_unanalysed_folders()

        _write_analysis_status("done", 100, filename, status="complete")
        logger.info("SUCCESS %s", filename)

        edit_info = utils.find_aspect_filename_from_seo_folder(seo_folder)
        edit_url = ""
        if edit_info:
            aspect, seo_file = edit_info
            edit_url = url_for("artwork.edit_listing", aspect=aspect, filename=seo_file)

            # --- ADD THIS BLOCK TO WAIT FOR THE THUMBNAIL ---
            try:
                thumb_filename = config.FILENAME_TEMPLATES["thumbnail"].format(seo_slug=seo_folder)
                thumb_path = config.PROCESSED_ROOT / seo_folder / thumb_filename

                timeout = 5  # seconds
                start_time = time.time()
                while not thumb_path.exists():
                    if time.time() - start_time > timeout:
                        logger.warning(f"Timeout waiting for thumbnail: {thumb_path}")
                        break
                    time.sleep(0.2) # Check every 200ms
            except Exception as e:
                logger.error(f"Error while waiting for thumbnail: {e}")
            # --- END OF NEW BLOCK ---

        # Build response with URL to the edit page. Clients using JavaScript
        # (fetch/XHR) expect JSON and will handle the redirect manually. A
        # normal form POST should receive an HTTP redirect.
        response_payload = {
            "success": True,
            "seo_folder": seo_folder,
            "listing": strip_binary(listing),
            "edit_url": edit_url,
        }

        action = f"analyse-{provider}"
        log_action(action, filename, user, "analysis complete", status="success")
        if (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.accept_mimetypes.best == "application/json"
        ):
            return jsonify(response_payload)

        return redirect(edit_url)

    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        logger.error("Analyze error for %s: %s", filename, exc)
        logger.error(tb)
        print(tb)
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(str(exc) + "\n" + tb)
        msg = exc.args[0] if exc.args else exc
        if isinstance(msg, (bytes, bytearray)):
            masked = f"<{len(msg)} bytes>"
            if debug:
                tb_mask = repr(msg)
                tb = tb.replace(tb_mask, masked)
            msg = masked
        error = str(msg)
        _write_analysis_status("failed", 100, filename, status="failed", error=error)
        if debug:
            error += "\n" + tb
        action = f"analyse-{provider}"
        log_action(
            action,
            filename,
            user,
            "analysis failed",
            status="fail",
            error=error,
        )
        return jsonify({"success": False, "error": error}), 500


# Convenience wrappers for explicit endpoints
@bp.post("/analyze-openai/<filename>")
def analyze_openai(filename: str):
    """Analyze using OpenAI provider."""
    return analyze_api("openai", filename)


@bp.post("/analyze-google/<filename>")
def analyze_google(filename: str):
    """Analyze using Google provider."""
    return analyze_api("google", filename)


@bp.post("/delete/<filename>")
def delete_artwork(filename: str):
    """Delete all files for an artwork."""
    logger = logging.getLogger(__name__)
    base = Path(filename).stem
    try:
        deleted = False
        for p in config.UNANALYSED_ROOT.rglob(f"{base}*"):
            p.unlink(missing_ok=True)
            deleted = True
        try:
            seo_folder, folder, listing_path, _ = utils.resolve_listing_paths(
                "", filename
            )
            with open(listing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            aspect = data.get("aspect_ratio", "")
            for target in [
                utils.PROCESSED_ROOT / seo_folder,
                utils.FINALISED_ROOT / seo_folder,
                utils.ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}",
            ]:
                shutil.rmtree(target, ignore_errors=True)
            if aspect:
                try:
                    os.remove(utils.UNANALYSED_ROOT / aspect / filename)
                except Exception:
                    pass
            deleted = True
        except FileNotFoundError:
            pass
        if deleted:
            utils.cleanup_unanalysed_folders()
            logger.info("Deleted artwork %s", filename)
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Artwork not found"}), 404
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        logger.error("Delete error for %s: %s", filename, exc)
        logger.error(tb)
        debug = config.DEBUG
        error = str(exc)
        if debug:
            error += "\n" + tb
        return jsonify({"success": False, "error": error}), 500


@bp.route("/logs/openai")
@bp.route("/logs/openai/<date>")
def view_openai_logs(date: str | None = None):
    """Return the tail of the most recent OpenAI analysis log."""
    logs = sorted(
        config.LOGS_DIR.glob("analyze-openai-calls-*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not logs:
        return Response("No logs found", mimetype="text/plain")

    target = None
    if date:
        cand = config.LOGS_DIR / f"analyze-openai-calls-{date}.log"
        if cand.exists():
            target = cand
    if not target:
        target = logs[0]

    text = target.read_text(encoding="utf-8")
    lines = text.strip().splitlines()[-50:]
    return Response("\n".join(lines), mimetype="text/plain")


@bp.route("/next-sku")
def preview_next_sku():
    """Return the next SKU without reserving it."""
    next_sku = peek_next_sku(config.SKU_TRACKER)
    return Response(next_sku, mimetype="text/plain")


def _process_upload_file(file_storage, dest_folder):
    """Return result dict for a single uploaded file.

    This helper performs validation, thumbnail generation and JSON QC file
    creation. Any IO or processing error is caught and returned in the
    ``error`` field instead of raising so the caller can continue processing
    remaining files.
    """
    result = {"original": file_storage.filename, "success": False, "error": ""}
    filename = file_storage.filename
    if not filename:
        result["error"] = "No filename"
        return result
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_EXTENSIONS:
        result["error"] = "Invalid file type"
        return result
    try:
        data = file_storage.read()
        if len(data) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            result["error"] = "File too large"
            return result
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except Exception as exc:  # noqa: BLE001 - PIL/IO errors
        result["error"] = "Corrupted image"
        logging.getLogger(__name__).error("Image validation failed: %s", exc)
        return result

    safe = aa.slugify(Path(filename).stem)
    unique = uuid.uuid4().hex[:8]
    uid = uuid.uuid4().hex
    base = f"{safe}-{unique}"
    dest_folder.mkdir(parents=True, exist_ok=True)
    orig_path = dest_folder / f"{base}.{ext}"
    try:
        with open(orig_path, "wb") as f:
            f.write(data)
    except Exception as exc:  # noqa: BLE001 - disk IO errors
        logging.getLogger(__name__).error("Failed writing %s: %s", orig_path, exc)
        result["error"] = "Failed saving file"
        return result

    try:
        with Image.open(orig_path) as img:
            width, height = img.size
            thumb_path = dest_folder / f"{base}-thumb.jpg"
            thumb = img.copy()
            thumb.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
            thumb.save(thumb_path, "JPEG", quality=80)

        analyse_path = dest_folder / f"{base}-analyse.jpg"
        with Image.open(orig_path) as img:
            w, h = img.size
            scale = config.ANALYSE_MAX_DIM / max(w, h)
            if scale < 1.0:
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            img = img.convert("RGB")

            q = 85
            while True:
                img.save(analyse_path, "JPEG", quality=q, optimize=True)
                if (
                    analyse_path.stat().st_size <= config.ANALYSE_MAX_MB * 1024 * 1024
                    or q <= 60
                ):
                    break
                q -= 5
    except Exception as exc:  # noqa: BLE001 - image processing errors
        logging.getLogger(__name__).error("Thumbnail/preview creation failed: %s", exc)
        result["error"] = "Image processing failed"
        return result

    aspect = aa.get_aspect_ratio(orig_path)

    qc_data = {
        "original_filename": filename,
        "extension": ext,
        "image_shape": [width, height],
        "filesize_bytes": len(data),
        "aspect_ratio": aspect,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    qc_path = dest_folder / f"{base}.qc.json"
    try:
        qc_path.write_text(json.dumps(qc_data, indent=2))
    except Exception as exc:  # noqa: BLE001 - disk IO errors
        logging.getLogger(__name__).error("Failed writing QC file %s: %s", qc_path, exc)
        result["error"] = "Failed writing QC file"
        return result

    utils.register_new_artwork(
        uid,
        f"{base}.{ext}",
        dest_folder,
        [orig_path.name, thumb_path.name, analyse_path.name, qc_path.name],
        "unanalysed",
        base,
    )

    result.update({"success": True, "base": base, "aspect": aspect, "uid": uid})
    return result

---
## routes/auth_routes.py
---
"""Authentication routes for ArtNarrator."""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils import security, session_tracker
import uuid
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from datetime import datetime
import config
from db import SessionLocal, User

load_dotenv()

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Display and handle the login form."""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        with SessionLocal() as db_session:
            user = db_session.query(User).filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                if not security.login_required_enabled() and user.role != "admin":
                    flash("Site locked by admin", "danger")
                    return render_template("login.html"), 403
                token = str(uuid.uuid4())
                if not session_tracker.register_session(username, token):
                    flash(
                        "Maximum login limit reached (5 devices). Log out on another device to continue.",
                        "danger",
                    )
                    return render_template("login.html"), 403
                session["logged_in"] = True
                session["username"] = username
                session["role"] = user.role
                session["session_id"] = token
                user.last_login = datetime.utcnow()
                db_session.commit()
                next_page = request.args.get("next") or url_for("artwork.home")
                return redirect(next_page)
        flash("Invalid username or password", "danger")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    """Clear session and redirect to login."""
    token = session.get("session_id")
    username = session.get("username")
    if token and username:
        session_tracker.remove_session(username, token)
    session.clear()
    return redirect(url_for("auth.login"))


---
## routes/coordinate_admin_routes.py
---
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

---
## routes/export_routes.py
---
from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path
from typing import List, Dict

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
    abort,
    session,
)

import config
from . import utils
from scripts import sellbrite_csv_export as sb
from utils.logger_utils import log_action

bp = Blueprint("exports", __name__, url_prefix="/exports")


def _collect_listings(locked_only: bool) -> List[Dict]:
    listings = []
    for base in (config.FINALISED_ROOT, config.ARTWORK_VAULT_ROOT):
        if not base.exists():
            continue
        for listing in base.rglob("*-listing.json"):
            try:
                utils.assign_or_get_sku(listing, config.SKU_TRACKER)
                with open(listing, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if locked_only and not data.get("locked"):
                continue
            listings.append(data)
    return listings


def _export_csv(
    listings: List[Dict], locked_only: bool
) -> tuple[Path, Path, List[str]]:
    config.SELLBRITE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    kind = "locked" if locked_only else "all"
    csv_path = config.SELLBRITE_DIR / f"sellbrite_{stamp}_{kind}.csv"
    log_path = config.SELLBRITE_DIR / f"sellbrite_{stamp}_{kind}.log"

    header = sb.read_template_header(config.SELLBRITE_TEMPLATE_CSV)

    errors = utils.validate_all_skus(listings, config.SKU_TRACKER)
    if errors:
        raise ValueError("; ".join(errors))

    warnings: List[str] = []

    def row_iter():
        for data in listings:
            missing = [
                k for k in ("title", "description", "sku", "price") if not data.get(k)
            ]
            if len((data.get("description") or "").split()) < 400:
                missing.append("description<400w")
            if not data.get("images"):
                missing.append("images")
            if missing:
                warnings.append(
                    f"{data.get('seo_filename', 'unknown')}: {', '.join(missing)}"
                )
            yield data

    sb.export_to_csv(row_iter(), header, csv_path)
    with open(log_path, "w", encoding="utf-8") as log:
        if warnings:
            log.write("\n".join(warnings))
        else:
            log.write("No warnings")
    return csv_path, log_path, warnings


@bp.route("/sellbrite")
def sellbrite_exports():
    items = []
    for csv_file in sorted(
        config.SELLBRITE_DIR.glob("*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        log_file = csv_file.with_suffix(".log")
        export_type = "Locked" if "locked" in csv_file.stem else "All"
        items.append(
            {
                "name": csv_file.name,
                "mtime": datetime.datetime.fromtimestamp(csv_file.stat().st_mtime),
                "type": export_type,
                "log": log_file.name if log_file.exists() else None,
            }
        )
    return render_template(
        "sellbrite_exports.html", exports=items, menu=utils.get_menu()
    )


@bp.route("/sellbrite/run", methods=["GET", "POST"])
def run_sellbrite_export():
    locked = request.args.get("locked") in {"1", "true", "yes"}
    try:
        listings = _collect_listings(locked)
        csv_path, log_path, warns = _export_csv(listings, locked)
        flash(f"Export created: {csv_path.name}", "success")
        if warns:
            flash(f"{len(warns)} warning(s) generated", "warning")
        log_action(
            "sellbrite-exports",
            csv_path.name,
            session.get("username"),
            "export created",
            status="success",
        )
    except Exception as exc:  # noqa: BLE001
        log_action(
            "sellbrite-exports",
            "",
            session.get("username"),
            "export failed",
            status="fail",
            error=str(exc),
        )
        flash(f"Export failed: {exc}", "danger")
    return redirect(url_for("exports.sellbrite_exports"))


@bp.route("/sellbrite/download/<path:csv_filename>")
def download_sellbrite(csv_filename: str):
    return send_from_directory(config.SELLBRITE_DIR, csv_filename, as_attachment=True)


@bp.route("/sellbrite/preview/<path:csv_filename>")
def preview_sellbrite_csv(csv_filename: str):
    path = config.SELLBRITE_DIR / csv_filename
    if not path.exists():
        abort(404)
    rows = []
    header: List[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for i, row in enumerate(reader):
            if i >= 20:
                break
            rows.append(row)
    return render_template(
        "sellbrite_csv_preview.html",
        csv_filename=csv_filename,
        header=header,
        rows=rows,
        menu=utils.get_menu(),
    )


@bp.route("/sellbrite/log/<path:log_filename>")
def view_sellbrite_log(log_filename: str):
    path = config.SELLBRITE_DIR / log_filename
    if not path.exists():
        abort(404)
    text = path.read_text(encoding="utf-8")
    return render_template(
        "sellbrite_log.html",
        log_filename=log_filename,
        log_text=text,
        menu=utils.get_menu(),
    )


---
## routes/gdws_admin_routes.py
---
"""Admin interface for the Guided Description Writing System (GDWS)."""

from flask import Blueprint, render_template, request, jsonify
import json
import random
import re
from pathlib import Path
import shutil
from datetime import datetime

from config import GDWS_CONTENT_DIR
from routes.utils import get_menu
from utils.ai_services import call_ai_to_rewrite, call_ai_to_generate_title

GDWS_CONTENT_PATH = GDWS_CONTENT_DIR

bp = Blueprint("gdws_admin", __name__, url_prefix="/admin/gdws")

# Define which paragraph titles are pinned to the start or end
PINNED_START_TITLES = [
    "About the Artist – Robin Custance",
    "Did You Know? Aboriginal Art & the Spirit of Dot Painting",
    "What You’ll Receive",
    "WHY YOU’LL LOVE THIS ARTWORK",
    "HOW TO BUY & PRINT",
]
PINNED_END_TITLES = [
    "THANK YOU – FROM MY STUDIO TO YOUR HOME",
    "Thank You & Stay Connected",
]

def slugify(text):
    """A simple function to create a filesystem-safe name."""
    s = text.lower()
    s = re.sub(r'[^\w\s-]', '', s).strip()
    s = re.sub(r'[-\s]+', '_', s)
    if "about_the_artist" in s: return "about_the_artist"
    if "did_you_know" in s: return "about_art_style"
    if "what_youll_receive" in s: return "file_details"
    return s

def get_aspect_ratios() -> list[str]:
    """Return a list of available aspect ratio folders."""
    if not GDWS_CONTENT_PATH.exists(): return []
    return sorted([p.name for p in GDWS_CONTENT_PATH.iterdir() if p.is_dir()])

@bp.route("/")
def editor():
    """Renders the main GDWS editor page with available aspect ratios."""
    return render_template(
        "dws_editor.html",
        menu=get_menu(),
        aspect_ratios=get_aspect_ratios(),
        PINNED_START_TITLES=PINNED_START_TITLES,
        PINNED_END_TITLES=PINNED_END_TITLES,
    )

@bp.route("/template/<aspect_ratio>")
def get_template_data(aspect_ratio):
    """Fetches and sorts paragraphs based on saved order and pinned status."""
    aspect_path = GDWS_CONTENT_PATH / aspect_ratio
    if not aspect_path.exists():
        return jsonify({"error": "Aspect ratio not found"}), 404

    all_blocks = {}
    for folder_path in [p for p in aspect_path.iterdir() if p.is_dir()]:
        base_file = folder_path / "base.json"
        if base_file.exists():
            try:
                with open(base_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_blocks[data['title']] = data
            except Exception as e:
                print(f"Error loading {base_file}: {e}")

    start_blocks = [all_blocks.pop(title) for title in PINNED_START_TITLES if title in all_blocks]
    end_blocks = [all_blocks.pop(title) for title in PINNED_END_TITLES if title in all_blocks]
    middle_blocks_dict = all_blocks

    order_file = aspect_path / "order.json"
    sorted_middle_blocks = []
    if order_file.exists():
        with open(order_file, 'r', encoding='utf-8') as f:
            order = json.load(f)
        for title in order:
            if title in middle_blocks_dict:
                sorted_middle_blocks.append(middle_blocks_dict.pop(title))
    
    sorted_middle_blocks.extend(middle_blocks_dict.values())

    return jsonify({"blocks": start_blocks + sorted_middle_blocks + end_blocks})

@bp.route("/save-order", methods=['POST'])
def save_order():
    """Saves the new order of the middle paragraphs."""
    data = request.json
    aspect_ratio = data.get('aspect_ratio')
    order = data.get('order')

    if not aspect_ratio or order is None:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    order_file = GDWS_CONTENT_PATH / aspect_ratio / "order.json"
    with open(order_file, 'w', encoding='utf-8') as f:
        json.dump(order, f, indent=2)
    
    return jsonify({"status": "success", "message": "Order saved."})

@bp.route("/regenerate-title", methods=['POST'])
def regenerate_title():
    """Handles AI regeneration for a paragraph title."""
    data = request.json
    content = data.get('content', '')
    new_title = call_ai_to_generate_title(content)
    return jsonify({"new_title": new_title})

@bp.route("/regenerate-paragraph", methods=['POST'])
def regenerate_paragraph():
    """Handles AI regeneration for a single paragraph."""
    data = request.json
    prompt = (
        f"Instruction: \"{data.get('instructions', '')}\"\n\n"
        f"Rewrite the following text based on the instruction. Respond only with the rewritten text.\n\n"
        f"TEXT TO REWRITE:\n\"{data.get('current_text', '')}\""
    )
    new_text = call_ai_to_rewrite(prompt)
    return jsonify({"new_content": new_text})

@bp.route("/save-paragraph-version", methods=['POST'])
def save_paragraph_version():
    """Saves a new paragraph variation, not overwriting the base."""
    data = request.json
    aspect_ratio = data.get('aspect_ratio')
    title = data.get('title')
    content = data.get('content')
    
    if not all([aspect_ratio, title, content]):
        return jsonify({"status": "error", "message": "Missing data."}), 400

    folder_name = slugify(title)
    folder_path = GDWS_CONTENT_PATH / aspect_ratio / folder_name
    folder_path.mkdir(exist_ok=True)

    variation_id = f"var_{int(datetime.now().timestamp() * 1000)}"
    file_path = folder_path / f"{variation_id}.json"

    save_data = {
        "id": variation_id,
        "title": title,
        "content": content,
        "instructions": data.get('instructions', ''),
        "version": "1.1", # Signifies it's a variation
        "last_updated": datetime.now().isoformat()
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=4)

    return jsonify({"status": "success", "message": f"Saved new variation {file_path}", "new_id": variation_id})

@bp.route("/save-base-paragraph", methods=['POST'])
def save_base_paragraph():
    """Saves edits to a base.json file, handling potential renames."""
    data = request.json
    aspect_ratio = data.get('aspect_ratio')
    original_title = data.get('original_title')
    new_title = data.get('new_title')
    
    if not all([aspect_ratio, original_title, new_title]):
        return jsonify({"status": "error", "message": "Missing data."}), 400

    original_slug = slugify(original_title)
    new_slug = slugify(new_title)
    
    original_folder = GDWS_CONTENT_PATH / aspect_ratio / original_slug
    target_folder = GDWS_CONTENT_PATH / aspect_ratio / new_slug
    
    if original_slug != new_slug:
        if target_folder.exists():
            return jsonify({"status": "error", "message": "A paragraph with that name already exists."}), 400
        if not original_folder.exists():
            return jsonify({"status": "error", "message": "Original paragraph folder not found."}), 404
        original_folder.rename(target_folder)

    file_path = target_folder / "base.json"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    except Exception:
        existing_data = {"id": "base"}

    existing_data['title'] = new_title
    existing_data['content'] = data.get('content', existing_data.get('content', ''))
    existing_data['instructions'] = data.get('instructions', existing_data.get('instructions', ''))
    existing_data['last_updated'] = datetime.now().isoformat()
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=4)
        
    return jsonify({"status": "success", "message": f"Updated {file_path}", "new_slug": new_slug})

---
## routes/mockup_admin_routes.py
---
"""Admin dashboard for managing and categorising mockups."""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_from_directory
from pathlib import Path
import subprocess
import os
import shutil
from PIL import Image
import imagehash

import config
from routes.utils import get_menu

bp = Blueprint("mockup_admin", __name__, url_prefix="/admin/mockups")

THUMBNAIL_DIR = config.MOCKUPS_INPUT_DIR / ".thumbnails"
THUMBNAIL_SIZE = (400, 400)

def get_available_aspects():
    """Finds available aspect ratio staging folders."""
    if not config.MOCKUPS_STAGING_DIR.exists():
        return []
    return sorted([d.name for d in config.MOCKUPS_STAGING_DIR.iterdir() if d.is_dir()])

def generate_thumbnail(source_path: Path, aspect: str):
    """Creates a thumbnail for a mockup image if it doesn't exist."""
    thumb_dir = THUMBNAIL_DIR / aspect
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / source_path.name

    if not thumb_path.exists():
        try:
            with Image.open(source_path) as img:
                img.thumbnail(THUMBNAIL_SIZE)
                img.convert("RGB").save(thumb_path, "JPEG", quality=85)
        except Exception as e:
            print(f"Could not create thumbnail for {source_path.name}: {e}")

@bp.route("/", defaults={'aspect': '4x5'})
@bp.route("/<aspect>")
def dashboard(aspect):
    """Display the paginated and sorted mockup management dashboard."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category_filter = request.args.get('category', 'All')
    sort_by = request.args.get('sort', 'name')

    all_mockups = []
    
    categorised_path = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised"
    categorised_path.mkdir(parents=True, exist_ok=True)
    all_categories = sorted([d.name for d in categorised_path.iterdir() if d.is_dir()])
    
    def collect_mockups(folder_path, category_name):
        for item in folder_path.iterdir():
            if item.is_file() and item.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                generate_thumbnail(item, aspect)
                all_mockups.append({
                    "filename": item.name, 
                    "category": category_name,
                    "mtime": item.stat().st_mtime
                })

    if category_filter == 'All' or category_filter == 'Uncategorised':
        staging_path = config.MOCKUPS_STAGING_DIR / aspect
        staging_path.mkdir(parents=True, exist_ok=True)
        collect_mockups(staging_path, "Uncategorised")

    if category_filter != 'Uncategorised':
        for category_name in all_categories:
            if category_filter == 'All' or category_filter == category_name:
                collect_mockups(categorised_path / category_name, category_name)

    if sort_by == 'date':
        all_mockups.sort(key=lambda x: x['mtime'], reverse=True)
    else:
        all_mockups.sort(key=lambda x: x['filename'])

    total_mockups = len(all_mockups)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_mockups = all_mockups[start:end]
    total_pages = (total_mockups + per_page - 1) // per_page

    return render_template(
        "admin/mockups.html",
        menu=get_menu(),
        mockups=paginated_mockups,
        categories=all_categories,
        current_aspect=aspect,
        aspect_ratios=get_available_aspects(),
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_mockups=total_mockups,
        category_filter=category_filter,
        sort_by=sort_by
    )
    
@bp.route("/thumbnail/<aspect>/<path:filename>")
def mockup_thumbnail(aspect, filename):
    return send_from_directory(THUMBNAIL_DIR / aspect, filename)

@bp.route("/image/<aspect>/<category>/<path:filename>")
def mockup_image(aspect, category, filename):
    if category == "Uncategorised":
        image_path = config.MOCKUPS_STAGING_DIR / aspect
    else:
        image_path = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised" / category
    return send_from_directory(image_path, filename)

@bp.route("/upload/<aspect>", methods=["POST"])
def upload_mockup(aspect):
    files = request.files.getlist('mockup_files')
    staging_path = config.MOCKUPS_STAGING_DIR / aspect
    count = 0
    for file in files:
        if file and file.filename:
            saved_path = staging_path / file.filename
            file.save(saved_path)
            generate_thumbnail(saved_path, aspect)
            count += 1
    if count > 0:
        flash(f"Uploaded and created thumbnails for {count} new mockup(s).", "success")
    return redirect(url_for("mockup_admin.dashboard", aspect=aspect))

@bp.route("/find-duplicates/<aspect>")
def find_duplicates(aspect):
    hashes = {}
    duplicates = []
    all_paths = []
    
    staging_path = config.MOCKUPS_STAGING_DIR / aspect
    all_paths.extend(p for p in staging_path.glob("*.*") if p.suffix.lower() in ['.png', '.jpg', '.jpeg'])
    categorised_path = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised"
    all_paths.extend(p for p in categorised_path.rglob("*.*") if p.suffix.lower() in ['.png', '.jpg', '.jpeg'])

    for path in all_paths:
        try:
            with Image.open(path) as img:
                h = str(imagehash.phash(img))
                if h in hashes:
                    duplicates.append({"original": hashes[h], "duplicate": str(path.relative_to(config.BASE_DIR))})
                else:
                    hashes[h] = str(path.relative_to(config.BASE_DIR))
        except Exception as e:
            print(f"Could not hash {path}: {e}")
            
    return jsonify({"duplicates": duplicates})

@bp.route("/create-category/<aspect>", methods=["POST"])
def create_category(aspect):
    category_name = request.form.get("category_name", "").strip()
    if category_name:
        new_dir = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised" / category_name
        new_dir.mkdir(exist_ok=True)
        flash(f"Category '{category_name}' created.", "success")
    else:
        flash("Category name cannot be empty.", "danger")
    return redirect(url_for("mockup_admin.dashboard", aspect=aspect))
    
@bp.route("/suggest-category", methods=["POST"])
def suggest_category():
    filename = request.json.get("filename")
    aspect = request.json.get("aspect")
    script_path = config.SCRIPTS_DIR / "mockup_categoriser.py"
    file_to_process = config.MOCKUPS_STAGING_DIR / aspect / filename
    if not file_to_process.exists():
        return jsonify({"success": False, "error": f"File not found: {filename}"}), 404
    try:
        result = subprocess.run(
            ["python3", str(script_path), "--file", str(file_to_process), "--no-move"],
            capture_output=True, text=True, check=True, timeout=120
        )
        return jsonify({"success": True, "suggestion": result.stdout.strip()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/move-mockup", methods=["POST"])
def move_mockup():
    data = request.json
    filename, aspect, original_category, new_category = data.get("filename"), data.get("aspect"), data.get("original_category"), data.get("new_category")
    
    if original_category == "Uncategorised":
        source_path = config.MOCKUPS_STAGING_DIR / aspect / filename
    else:
        source_path = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised" / original_category / filename
    
    dest_dir = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised" / new_category
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        shutil.move(str(source_path), str(dest_dir / filename))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/delete-mockup", methods=["POST"])
def delete_mockup():
    data = request.json
    filename, aspect, category = data.get("filename"), data.get("aspect"), data.get("category")

    if category == "Uncategorised":
        path_to_delete = config.MOCKUPS_STAGING_DIR / aspect / filename
    else:
        path_to_delete = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised" / category / filename

    try:
        if path_to_delete.is_file():
            path_to_delete.unlink()
            (THUMBNAIL_DIR / aspect / filename).unlink(missing_ok=True)
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "File not found."}), 404
    except Exception as e:
        return jsonify({"success": False, "error": f"Error deleting file: {e}"}), 500

---
## routes/sellbrite_export.py
---
"""Utilities for exporting listings to Sellbrite.

Field mapping between our artwork JSON and Sellbrite's Listings API:

| JSON field       | Sellbrite field |
|------------------|-----------------|
| title            | name            |
| description      | description     |
| tags             | tags            |
| materials        | materials       |
| primary_colour   | primary_colour  |
| secondary_colour | secondary_colour|
| seo_filename     | seo_filename    |
| sku              | sku             |
| price            | price           |
| images           | images          |
"""

from __future__ import annotations

from typing import Any, Dict


def generate_sellbrite_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dictionary formatted for the Sellbrite Listings API."""
    sb = {
        "sku": data.get("sku"),
        "name": data.get("title"),
        "description": data.get("description"),
        "price": data.get("price"),
        "tags": data.get("tags", []),
        "materials": data.get("materials", []),
        "primary_colour": data.get("primary_colour"),
        "secondary_colour": data.get("secondary_colour"),
        "seo_filename": data.get("seo_filename"),
        "images": data.get("images", []),
    }
    return {k: v for k, v in sb.items() if v not in (None, "", [])}


---
## routes/sellbrite_service.py
---
"""Sellbrite API integration utilities."""

from __future__ import annotations

import base64
import logging
import os
from typing import Dict

import requests
from flask import Blueprint, jsonify
from dotenv import load_dotenv

load_dotenv()

SELLBRITE_TOKEN = os.getenv("SELLBRITE_TOKEN")
SELLBRITE_SECRET = os.getenv("SELLBRITE_SECRET")
API_BASE = "https://api.sellbrite.com/v1"

logger = logging.getLogger(__name__)

bp = Blueprint("sellbrite", __name__)


def _auth_header() -> Dict[str, str]:
    """Return the HTTP Authorization header for Sellbrite."""
    if not SELLBRITE_TOKEN or not SELLBRITE_SECRET:
        logger.error("Sellbrite credentials not configured")
        return {}
    creds = f"{SELLBRITE_TOKEN}:{SELLBRITE_SECRET}".encode("utf-8")
    encoded = base64.b64encode(creds).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}


def test_sellbrite_connection() -> bool:
    """Attempt a simple authenticated request to verify credentials."""
    url = f"{API_BASE}/products"
    try:
        resp = requests.get(url, headers=_auth_header(), timeout=10)
    except requests.RequestException as exc:
        logger.error("Sellbrite connection error: %s", exc)
        return False
    if resp.status_code == 200:
        logger.info("Sellbrite authentication succeeded")
        return True
    logger.error(
        "Sellbrite authentication failed: %s %s", resp.status_code, resp.text
    )
    return False


@bp.route("/sellbrite/test")
def sellbrite_test():
    """Flask route demonstrating a simple API connectivity check."""
    success = test_sellbrite_connection()
    status = 200 if success else 500
    return jsonify({"success": success}), status


if __name__ == "__main__":
    ok = test_sellbrite_connection()
    print("Connection successful" if ok else "Connection failed")


---
## routes/test_routes.py
---
from flask import Blueprint, render_template

# Blueprint for overlay migration testing
test_bp = Blueprint('test_bp', __name__)

@test_bp.route('/overlay-test')
def overlay_test():
    return render_template('codex-library/Overlay-Menu-Design-Template/main-design-template.html')


# Route to view edit listing overlay test template
@test_bp.route('/test/edit-listing')
def edit_listing_test():
    """Render overlay version of edit listing template."""
    return render_template('edit_listing_overlay_test.html')


# Route to view artworks overlay test template
@test_bp.route('/test/artworks')
def artworks_test():
    """Render overlay version of artworks template."""
    return render_template('artworks_overlay_test.html')


---
## routes/utils.py
---
# This file now references all path, directory, and filename variables strictly from config.py. No local or hardcoded path constants remain.
import os
import json
import random
import re
import logging
import csv
import fcntl
import shutil
import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Iterable

from utils.sku_assigner import get_next_sku, peek_next_sku

from dotenv import load_dotenv
from flask import session
from PIL import Image
import cv2
import numpy as np
import config

from config import (
    BASE_DIR,
    UNANALYSED_ROOT,
    PROCESSED_ROOT,
    SELECTIONS_DIR,
    COMPOSITES_DIR,
    FINALISED_ROOT,
    ARTWORK_VAULT_ROOT,
    LOGS_DIR,
    MOCKUPS_INPUT_DIR,
    ANALYSE_MAX_DIM,
    GENERIC_TEXTS_DIR,
    COORDS_DIR,
    ANALYZE_SCRIPT_PATH,
    GENERATE_SCRIPT_PATH,
    FILENAME_TEMPLATES,
    OUTPUT_JSON,
)

# ==============================
# Paths & Configuration
# ==============================
load_dotenv()

# Etsy accepted colour values
ALLOWED_COLOURS = [
    "Beige",
    "Black",
    "Blue",
    "Bronze",
    "Brown",
    "Clear",
    "Copper",
    "Gold",
    "Grey",
    "Green",
    "Orange",
    "Pink",
    "Purple",
    "Rainbow",
    "Red",
    "Rose gold",
    "Silver",
    "White",
    "Yellow",
]

ALLOWED_COLOURS_LOWER = {c.lower(): c for c in ALLOWED_COLOURS}

Image.MAX_IMAGE_PIXELS = None
for directory in [
    UNANALYSED_ROOT,
    MOCKUPS_INPUT_DIR,
    PROCESSED_ROOT,
    SELECTIONS_DIR,
    COMPOSITES_DIR,
    FINALISED_ROOT,
    LOGS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# JSON File Helpers
# ============================================================================

def load_json_file_safe(path: Path) -> dict:
    """Return JSON from ``path`` handling any errors gracefully."""

    logger = logging.getLogger(__name__)
    path = Path(path)

    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
            logger.warning("Missing %s - created new empty file", path)
            return {}

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            path.write_text("{}")
            logger.warning("Empty JSON file %s - reset to {}", path)
            return {}

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in %s: %s", path, exc)
            path.write_text("{}")
            return {}
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Failed handling %s: %s", path, exc)
        return {}

# ==============================
# Utility Helpers
# ==============================

def get_mockup_categories(aspect_folder: Path | str) -> List[str]:
    """Return sorted list of category folder names under ``aspect_folder``.

    Hidden folders and files are ignored.
    """
    folder = Path(aspect_folder)
    if not folder.exists():
        return []
    return sorted(
        f.name
        for f in folder.iterdir()
        if f.is_dir() and not f.name.startswith(".")
    )


def get_categories() -> List[str]:
    """Return sorted list of mockup categories from the root directory."""
    return get_mockup_categories(MOCKUPS_INPUT_DIR)


def random_image(category: str) -> Optional[str]:
    """Return a random image filename for the given category."""
    cat_dir = MOCKUPS_INPUT_DIR / category
    images = [f.name for f in cat_dir.glob("*.png")]
    return random.choice(images) if images else None


def init_slots() -> None:
    """Initialise mockup slot selections in the session."""
    cats = get_categories()
    session["slots"] = [{"category": c, "image": random_image(c)} for c in cats]


def compute_options(slots) -> List[List[str]]:
    """Return category options for each slot."""
    cats = get_categories()
    return [cats for _ in slots]


def relative_to_base(path: Path | str) -> str:
    """Return a path string relative to the project root."""
    return str(Path(path).resolve().relative_to(BASE_DIR))


def resize_image_for_long_edge(image: Image.Image, target_long_edge: int = 2000) -> Image.Image:
    """Resize image maintaining aspect ratio."""
    width, height = image.size
    if width > height:
        new_width = target_long_edge
        new_height = int(height * (target_long_edge / width))
    else:
        new_height = target_long_edge
        new_width = int(width * (target_long_edge / height))
    return image.resize((new_width, new_height), Image.LANCZOS)


def apply_perspective_transform(art_img: Image.Image, mockup_img: Image.Image, dst_coords: list) -> Image.Image:
    """Overlay artwork onto mockup using perspective transform."""
    w, h = art_img.size
    src_points = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst_points = np.float32(dst_coords)
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    art_np = np.array(art_img)
    warped = cv2.warpPerspective(art_np, matrix, (mockup_img.width, mockup_img.height))
    mask = np.any(warped > 0, axis=-1).astype(np.uint8) * 255
    mask = Image.fromarray(mask).convert("L")
    composite = Image.composite(Image.fromarray(warped), mockup_img, mask)
    return composite


def latest_composite_folder() -> Optional[str]:
    """Return the most recent composite output folder name."""
    latest_time = 0
    latest_folder = None
    for folder in PROCESSED_ROOT.iterdir():
        if not folder.is_dir():
            continue
        images = list(folder.glob("*-mockup-*.jpg"))
        if not images:
            continue
        recent = max(images, key=lambda p: p.stat().st_mtime)
        if recent.stat().st_mtime > latest_time:
            latest_time = recent.stat().st_mtime
            latest_folder = folder.name
    return latest_folder


def latest_analyzed_artwork() -> Optional[Dict[str, str]]:
    """Return info about the most recently analysed artwork."""
    latest_time = 0
    latest_info = None
    for folder in PROCESSED_ROOT.iterdir():
        if not folder.is_dir():
            continue
        listing = folder / f"{folder.name}-listing.json"
        if not listing.exists():
            continue
        t = listing.stat().st_mtime
        if t > latest_time:
            latest_time = t
            try:
                with open(listing, "r", encoding="utf-8") as f:
                    data = json.load(f)
                latest_info = {
                    "aspect": data.get("aspect_ratio"),
                    "filename": data.get("filename"),
                }
            except Exception:
                continue
    return latest_info


def clean_display_text(text: str) -> str:
    """Collapse excess whitespace/newlines in description text."""
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r"\n{2,}", "\n\n", cleaned)
    return cleaned


def build_full_listing_text(ai_desc: str, generic_text: str) -> str:
    """Combine AI description and generic text into one string."""
    parts = [clean_display_text(ai_desc), clean_display_text(generic_text)]
    combined = "\n\n".join([p for p in parts if p])
    return clean_display_text(combined)


def slugify(text: str) -> str:
    """Return a slug suitable for filenames."""
    text = re.sub(r"[^\w\- ]+", "", text)
    text = text.strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()


def prettify_slug(slug: str) -> str:
    """Return a human friendly title from a slug or filename."""
    name = os.path.splitext(slug)[0]
    name = name.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name)
    return name.title()


def list_processed_artworks() -> Tuple[List[Dict], set]:
    """Collect processed artworks and set of original filenames."""
    items: List[Dict] = []
    processed_names: set = set()
    for folder in PROCESSED_ROOT.iterdir():
        if not folder.is_dir():
            continue
        listing_path = folder / f"{folder.name}-listing.json"
        if not listing_path.exists():
            continue
        try:
            with open(listing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        original_name = data.get("filename")
        if original_name:
            processed_names.add(original_name)
        items.append(
            {
                "seo_folder": folder.name,
                "filename": original_name or f"{folder.name}.jpg",
                "aspect": data.get("aspect_ratio", ""),
                "title": data.get("title") or prettify_slug(folder.name),
                "thumb": f"{folder.name}-THUMB.jpg",
            }
        )
    items.sort(key=lambda x: x["title"].lower())
    return items, processed_names


def list_ready_to_analyze(_: set) -> List[Dict]:
    """Return artworks uploaded but not yet analyzed."""
    ready: List[Dict] = []
    for qc_path in UNANALYSED_ROOT.glob("**/*.qc.json"):
        base = qc_path.name[:-8]  # remove .qc.json
        try:
            with open(qc_path, "r", encoding="utf-8") as f:
                qc = json.load(f)
        except Exception:
            continue
        ext = qc.get("extension", "jpg")
        aspect = qc.get("aspect_ratio", "")
        title = prettify_slug(Path(qc.get("original_filename", base)).stem)
        ready.append(
            {
                "aspect": aspect,
                "filename": f"{base}.{ext}",
                "title": title,
                "thumb": f"{base}-thumb.jpg",
                "base": base,
            }
        )
    ready.sort(key=lambda x: x["title"].lower())
    return ready


def list_finalised_artworks() -> List[Dict]:
    """Return artworks that have been finalised."""
    items: List[Dict] = []
    if FINALISED_ROOT.exists():
        for folder in FINALISED_ROOT.iterdir():
            if not folder.is_dir():
                continue
            listing_file = folder / f"{folder.name}-listing.json"
            if not listing_file.exists():
                continue
            try:
                with open(listing_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            items.append(
                {
                    "seo_folder": folder.name,
                    "filename": data.get("filename", f"{folder.name}.jpg"),
                    "aspect": data.get("aspect_ratio", ""),
                    "title": data.get("title") or prettify_slug(folder.name),
                    "thumb": f"{folder.name}-THUMB.jpg",
                }
            )
    items.sort(key=lambda x: x["title"].lower())
    return items


def list_finalised_artworks_extended() -> List[Dict]:
    """Return detailed info for finalised artworks including locked state."""
    items: List[Dict] = []
    for base in (FINALISED_ROOT, ARTWORK_VAULT_ROOT):
        if not base.exists():
            continue
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            slug = folder.name.removeprefix("LOCKED-")
            listing_file = folder / f"{slug}-listing.json"
            if not listing_file.exists():
                continue
            try:
                with open(listing_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            main_img = folder / f"{slug}.jpg"
            thumb_img = folder / f"{slug}-THUMB.jpg"
            items.append(
                {
                    "seo_folder": folder.name,
                    "title": data.get("title") or prettify_slug(slug),
                    "description": data.get("description", ""),
                    "sku": data.get("sku", ""),
                    "primary_colour": data.get("primary_colour", ""),
                    "secondary_colour": data.get("secondary_colour", ""),
                    "price": data.get("price", ""),
                    "seo_filename": data.get("seo_filename", f"{slug}.jpg"),
                    "tags": data.get("tags", []),
                    "materials": data.get("materials", []),
                    "aspect": data.get("aspect_ratio", ""),
                    "filename": data.get("filename", f"{slug}.jpg"),
                    "locked": data.get("locked", False),
                    "main_image": main_img.name if main_img.exists() else None,
                    "thumb": thumb_img.name if thumb_img.exists() else None,
                    "images": [
                        str(p)
                        for p in data.get("images", [])
                        if (BASE_DIR / p).exists()
                    ],
                }
            )
    items.sort(key=lambda x: x["title"].lower())
    return items


def find_seo_folder_from_filename(aspect: str, filename: str) -> str:
    """Return the best matching SEO folder for ``filename``.

    This searches both processed and finalised outputs and compares the given
    base name against multiple permutations found in each listing file. If
    multiple folders match, the most recently modified one is returned.
    """

    basename = Path(filename).stem.lower()
    slug_base = slugify(basename)
    candidates: list[tuple[float, str]] = []

    for base in (PROCESSED_ROOT, FINALISED_ROOT, ARTWORK_VAULT_ROOT):
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            slug = folder.name.removeprefix("LOCKED-")
            listing_file = folder / FILENAME_TEMPLATES["listing_json"].format(seo_slug=slug)
            if not listing_file.exists():
                continue
            try:
                with open(listing_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            stems = {
                Path(data.get("filename", "")).stem.lower(),
                Path(data.get("seo_filename", "")).stem.lower(),
                slug.lower(),
                folder.name.lower(),
                slugify(Path(data.get("filename", "")).stem),
                slugify(Path(data.get("seo_filename", "")).stem),
                slugify(slug),
            }

            if basename in stems or slug_base in stems:
                candidates.append((listing_file.stat().st_mtime, slug))

    if not candidates:
        raise FileNotFoundError(f"SEO folder not found for {filename}")

    return max(candidates, key=lambda x: x[0])[1]


def regenerate_one_mockup(seo_folder: str, slot_idx: int) -> bool:
    """Regenerate a single mockup in-place."""
    folder = PROCESSED_ROOT / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    if not listing_file.exists():
        folder = FINALISED_ROOT / seo_folder
        listing_file = folder / f"{seo_folder}-listing.json"
        if not listing_file.exists():
            return False
    with open(listing_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    mockups = data.get("mockups", [])
    if slot_idx < 0 or slot_idx >= len(mockups):
        return False
    entry = mockups[slot_idx]
    if isinstance(entry, dict):
        category = entry.get("category")
    else:
        category = Path(entry).parent.name
    aspect = data.get("aspect_ratio")
    mockup_root = MOCKUPS_INPUT_DIR / f"{aspect}-categorised"
    mockup_files = list((mockup_root / category).glob("*.png"))
    if not mockup_files:
        return False
    new_mockup = random.choice(mockup_files)
    coords_path = COORDS_DIR / aspect / f"{new_mockup.stem}.json"
    art_path = folder / f"{seo_folder}.jpg"
    output_path = folder / f"{seo_folder}-{new_mockup.stem}.jpg"
    try:
        with open(coords_path, "r", encoding="utf-8") as cf:
            c = json.load(cf)["corners"]
        dst = [[c[0]["x"], c[0]["y"]], [c[1]["x"], c[1]["y"]], [c[3]["x"], c[3]["y"]], [c[2]["x"], c[2]["y"]]]
        art_img = Image.open(art_path).convert("RGBA")
        art_img = resize_image_for_long_edge(art_img)
        mock_img = Image.open(new_mockup).convert("RGBA")
        composite = apply_perspective_transform(art_img, mock_img, dst)
        composite.convert("RGB").save(output_path, "JPEG", quality=85)
        data.setdefault("mockups", [])[slot_idx] = {
            "category": category,
            "source": f"{category}/{new_mockup.name}",
            "composite": output_path.name,
        }
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logging.error("Regenerate error: %s", e)
        return False


def swap_one_mockup(seo_folder: str, slot_idx: int, new_category: str) -> bool:
    """Swap a mockup to a new category and regenerate."""
    folder = PROCESSED_ROOT / seo_folder
    listing_file = folder / f"{seo_folder}-listing.json"
    if not listing_file.exists():
        folder = FINALISED_ROOT / seo_folder
        listing_file = folder / f"{seo_folder}-listing.json"
        if not listing_file.exists():
            return False
    with open(listing_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    mockups = data.get("mockups", [])
    if slot_idx < 0 or slot_idx >= len(mockups):
        return False
    aspect = data.get("aspect_ratio")
    mockup_root = MOCKUPS_INPUT_DIR / f"{aspect}-categorised"
    mockup_files = list((mockup_root / new_category).glob("*.png"))
    if not mockup_files:
        return False
    new_mockup = random.choice(mockup_files)
    coords_path = COORDS_DIR / aspect / f"{new_mockup.stem}.json"
    art_path = folder / f"{seo_folder}.jpg"
    output_path = folder / f"{seo_folder}-{new_mockup.stem}.jpg"
    try:
        with open(coords_path, "r", encoding="utf-8") as cf:
            c = json.load(cf)["corners"]
        dst = [[c[0]["x"], c[0]["y"]], [c[1]["x"], c[1]["y"]], [c[3]["x"], c[3]["y"]], [c[2]["x"], c[2]["y"]]]
        art_img = Image.open(art_path).convert("RGBA")
        art_img = resize_image_for_long_edge(art_img)
        mock_img = Image.open(new_mockup).convert("RGBA")
        composite = apply_perspective_transform(art_img, mock_img, dst)
        composite.convert("RGB").save(output_path, "JPEG", quality=85)
        data.setdefault("mockups", [])[slot_idx] = {
            "category": new_category,
            "source": f"{new_category}/{new_mockup.name}",
            "composite": output_path.name,
        }
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logging.error("Swap error: %s", e)
        return False


def _listing_json_path(seo_folder: str) -> Path:
    """Return the listing JSON path for a SEO folder if it exists."""
    for base in (PROCESSED_ROOT, FINALISED_ROOT, ARTWORK_VAULT_ROOT):
        path = base / seo_folder / f"{seo_folder}-listing.json"
        if path.exists():
            return path
    raise FileNotFoundError(f"Listing file for {seo_folder} not found")


def get_mockups(seo_folder: str) -> list:
    """Return mockup entries from the listing JSON."""
    try:
        listing = _listing_json_path(seo_folder)
        with open(listing, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("mockups", [])
    except Exception as exc:  # noqa: BLE001
        logging.error("Failed reading mockups for %s: %s", seo_folder, exc)
        return []


def create_default_mockups(seo_folder: str) -> None:
    """Create a fallback mockup image and update the listing."""
    dest = PROCESSED_ROOT / seo_folder
    dest.mkdir(parents=True, exist_ok=True)
    default_src = config.STATIC_DIR / "img" / "default-mockup.jpg"
    target = dest / FILENAME_TEMPLATES["mockup"].format(seo_slug=seo_folder, num=1)
    shutil.copy(default_src, target)
    listing = _listing_json_path(seo_folder)
    data = load_json_file_safe(listing)
    data.setdefault("mockups", []).append(
        {"category": "default", "source": "default", "composite": target.name}
    )
    with open(listing, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_mockups_for_listing(seo_folder: str) -> bool:
    """Ensure mockups exist for the listing, creating defaults if needed."""
    try:
        if not get_mockups(seo_folder):
            create_default_mockups(seo_folder)
            logging.info("Default mockups created for %s", seo_folder)
        return True
    except Exception as exc:  # noqa: BLE001
        logging.error("Error generating mockups for %s: %s", seo_folder, exc)
        return False


def get_menu() -> List[Dict[str, str | None]]:
    """Return navigation items for templates."""
    from flask import url_for

    menu = [
        {"name": "Home", "url": url_for("artwork.home")},
        {"name": "Artwork Gallery", "url": url_for("artwork.artworks")},
        {"name": "Finalised", "url": url_for("artwork.finalised_gallery")},
    ]
    latest = latest_analyzed_artwork()
    if latest:
        menu.append({
            "name": "Review Latest Listing",
            "url": url_for("artwork.edit_listing", aspect=latest["aspect"], filename=latest["filename"]),
        })
    else:
        menu.append({"name": "Review Latest Listing", "url": None})
    return menu


def get_allowed_colours() -> List[str]:
    """Return the list of allowed Etsy colour values."""
    return ALLOWED_COLOURS.copy()


def infer_sku_from_filename(filename: str) -> Optional[str]:
    """Infer SKU from an SEO filename using 'RJC-XXXX' at the end."""
    m = re.search(r"RJC-([A-Za-z0-9-]+)(?:\.jpg)?$", filename or "")
    return f"RJC-{m.group(1)}" if m else None


def sync_filename_with_sku(seo_filename: str, sku: str) -> str:
    """Return SEO filename updated so the SKU matches the given value."""
    if not seo_filename:
        return seo_filename
    if not sku:
        return seo_filename
    return re.sub(r"RJC-[A-Za-z0-9-]+(?=\.jpg$)", sku, seo_filename)


def is_finalised_image(path: str | Path) -> bool:
    """Return True if the given path is within a finalised or locked folder."""
    p = Path(path).resolve()
    try:
        p.relative_to(FINALISED_ROOT)
        return True
    except Exception:
        pass
    try:
        p.relative_to(ARTWORK_VAULT_ROOT)
        return True
    except Exception:
        return False


def update_listing_paths(listing: Path, old_base: Path, new_base: Path) -> None:
    """Replace base path strings inside a listing JSON when folders move."""
    if not listing.exists():
        return
    try:
        with open(listing, "r", encoding="utf-8") as lf:
            data = json.load(lf)
    except Exception:
        return

    old_rel = relative_to_base(old_base)
    new_rel = relative_to_base(new_base)

    def _swap(p: str) -> str:
        return p.replace(old_rel, new_rel)

    for key in ("main_jpg_path", "orig_jpg_path", "thumb_jpg_path", "processed_folder"):
        if isinstance(data.get(key), str):
            data[key] = _swap(data[key])

    if isinstance(data.get("images"), list):
        data["images"] = [_swap(img) if isinstance(img, str) else img for img in data["images"]]

    with open(listing, "w", encoding="utf-8") as lf:
        json.dump(data, lf, indent=2, ensure_ascii=False)


def parse_csv_list(text: str) -> List[str]:
    """Parse a comma-separated string into a list of trimmed values."""
    import csv

    if not text:
        return []
    reader = csv.reader([text], skipinitialspace=True)
    row = next(reader, [])
    return [item.strip() for item in row if item.strip()]


def join_csv_list(items: List[str]) -> str:
    """Join a list of strings into a comma-separated string for display."""
    return ", ".join(item.strip() for item in items if item.strip())


def read_generic_text(aspect: str) -> str:
    """Return the generic text block for the given aspect ratio."""
    path = GENERIC_TEXTS_DIR / f"{aspect}.txt"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        logging.warning("Generic text for %s not found", aspect)
        return ""


def clean_terms(items: List[str]) -> Tuple[List[str], List[str]]:
    """Clean list entries by stripping invalid characters and hyphens."""
    cleaned: List[str] = []
    changed = False
    for item in items:
        new = re.sub(r"[^A-Za-z0-9 ,]", "", item)
        new = new.replace("-", "")
        new = re.sub(r"\s+", " ", new).strip()
        cleaned.append(new)
        if new != item.strip():
            changed = True
    return cleaned, cleaned if changed else []


def resolve_listing_paths(aspect: str, filename: str) -> Tuple[str, Path, Path, bool]:
    """Return the folder and listing path for an artwork.

    Searches both processed and finalised directories using
    :func:`find_seo_folder_from_filename` and returns a tuple of
    ``(seo_folder, folder_path, listing_path, finalised)``.
    Raises ``FileNotFoundError`` if nothing matches.
    """

    seo_folder = find_seo_folder_from_filename(aspect, filename)
    processed_dir = PROCESSED_ROOT / seo_folder
    final_dir = FINALISED_ROOT / seo_folder
    locked_dir = ARTWORK_VAULT_ROOT / f"LOCKED-{seo_folder}"

    listing = processed_dir / f"{seo_folder}-listing.json"
    if listing.exists():
        return seo_folder, processed_dir, listing, False

    listing = final_dir / f"{seo_folder}-listing.json"
    if listing.exists():
        return seo_folder, final_dir, listing, True

    listing = locked_dir / f"{seo_folder}-listing.json"
    if listing.exists():
        return seo_folder, locked_dir, listing, True

    raise FileNotFoundError(f"Listing file for {filename} not found")


def find_aspect_filename_from_seo_folder(seo_folder: str) -> Optional[Tuple[str, str]]:
    """Return the aspect ratio and main filename for a given SEO folder.

    The lookup checks both processed and finalised folders. Information is
    primarily loaded from the listing JSON, but if fields are missing the
    filename is inferred from disk contents. Filenames are normalised to use a
    ``.jpg`` extension and to match the actual casing on disk when possible.
    """

    for base in (PROCESSED_ROOT, FINALISED_ROOT, ARTWORK_VAULT_ROOT):
        folder = base / seo_folder
        listing = folder / f"{seo_folder}-listing.json"
        aspect = ""
        filename = ""

        if listing.exists():
            try:
                with open(listing, "r", encoding="utf-8") as lf:
                    data = json.load(lf)
                aspect = data.get("aspect_ratio") or data.get("aspect") or ""
                filename = (
                    data.get("seo_filename")
                    or data.get("filename")
                    or data.get("seo_name")
                    or ""
                )
                if not filename:
                    for key in ("main_jpg_path", "orig_jpg_path", "thumb_jpg_path"):
                        val = data.get(key)
                        if val:
                            filename = Path(val).name
                            break
            except Exception as e:  # noqa: BLE001
                logging.error("Failed reading listing for %s: %s", seo_folder, e)

        if folder.exists() and not filename:
            # Look for an image whose stem matches the folder name
            for p in folder.iterdir():
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"} and p.stem.lower() == seo_folder.lower():
                    filename = p.name
                    break

        if filename:
            if not filename.lower().endswith(".jpg"):
                filename = f"{Path(filename).stem}.jpg"
            # Normalise casing to match actual disk file
            disk_file = folder / filename
            if not disk_file.exists():
                stem = Path(filename).stem.lower()
                for p in folder.iterdir():
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png"} and p.stem.lower() == stem:
                        filename = p.name
                        break
            return aspect, filename

    return None


def assign_or_get_sku(
    listing_json_path: Path, tracker_path: Path, *, force: bool = False
) -> str:
    """Return existing SKU or assign the next sequential one.

    Parameters
    ----------
    listing_json_path:
        Path to the ``*-listing.json`` file.
    tracker_path:
        Path to ``sku_tracker.json`` storing ``last_sku``.
    force:
        If ``True`` always allocate a new SKU even if one exists.
    """
    listing_json_path = Path(listing_json_path)
    tracker_path = Path(tracker_path)

    logger = logging.getLogger(__name__)

    if not listing_json_path.exists():
        raise FileNotFoundError(listing_json_path)

    try:
        with open(listing_json_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Failed reading %s: %s", listing_json_path, exc)
        raise

    existing = str(data.get("sku") or "").strip()
    seo_field = str(data.get("seo_filename") or "").strip()
    if existing and not force:
        new_seo = sync_filename_with_sku(seo_field, existing)
        if new_seo != seo_field:
            data["seo_filename"] = new_seo
            try:
                with open(listing_json_path, "w", encoding="utf-8") as lf:
                    json.dump(data, lf, indent=2, ensure_ascii=False)
            except Exception as exc:  # pragma: no cover - unexpected IO
                logger.error("Failed writing SEO filename to %s: %s", listing_json_path, exc)
                raise
        return existing

    # Allocate the next SKU using the central assigner
    sku = get_next_sku(tracker_path)
    data["sku"] = sku
    if seo_field:
        data["seo_filename"] = sync_filename_with_sku(seo_field, sku)
    try:
        with open(listing_json_path, "w", encoding="utf-8") as lf:
            json.dump(data, lf, indent=2, ensure_ascii=False)
    except Exception as exc:  # pragma: no cover - unexpected IO
        logger.error("Failed writing SKU %s to %s: %s", sku, listing_json_path, exc)
        raise

    logger.info("Assigned SKU %s to %s", sku, listing_json_path.name)
    return sku


def assign_sequential_sku(listing_json_path: Path, tracker_path: Path) -> str:
    """Backward compatible wrapper for ``assign_or_get_sku``."""
    return assign_or_get_sku(listing_json_path, tracker_path)


def validate_all_skus(listings: Iterable[Dict], tracker_path: Path) -> list[str]:
    """Return a list of SKU validation errors for the given listings."""
    tracker_last = 0
    try:
        with open(tracker_path, "r", encoding="utf-8") as tf:
            tracker_last = int(json.load(tf).get("last_sku", 0))
    except Exception:
        pass

    errors: list[str] = []
    seen: dict[int, int] = {}
    nums: list[int] = []

    for idx, data in enumerate(listings):
        sku = str(data.get("sku") or "")
        m = re.fullmatch(r"RJC-(\d{4})", sku)
        if not m:
            errors.append(f"Listing {idx}: invalid or missing SKU")
            continue
        num = int(m.group(1))
        if num in seen:
            errors.append(f"Duplicate SKU {sku} in listings {seen[num]} and {idx}")
        seen[num] = idx
        nums.append(num)

    if nums:
        nums.sort()
        for a, b in zip(nums, nums[1:]):
            if b != a + 1:
                errors.append(f"Gap or out-of-sequence SKU between {a:04d} and {b:04d}")
                break
        if nums[-1] > tracker_last:
            errors.append("Tracker last_sku behind recorded SKUs")

    return errors


# ---------------------------------------------------------------------------
# Artwork Registry & File Move Helpers
# ---------------------------------------------------------------------------

REGISTRY_PATH = OUTPUT_JSON


def _load_registry() -> dict:
    """Return registry JSON as a dictionary, resetting invalid data."""

    if not REGISTRY_PATH.exists():
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text("{}")

    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as rf:
            data = json.load(rf)
    except Exception:  # pragma: no cover - unexpected IO
        return {}

    # Historical versions stored a list which breaks ``dict`` usage.
    if not isinstance(data, dict):
        logging.getLogger(__name__).warning(
            "Registry file not a dict, resetting: %s", REGISTRY_PATH
        )
        return {}

    return data


def _save_registry(reg: dict) -> None:
    """Write the registry ``reg`` to disk atomically."""

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as tf:
        json.dump(reg, tf, indent=2, ensure_ascii=False)
    os.replace(tmp, REGISTRY_PATH)


def create_unanalysed_subfolder() -> Path:
    UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    existing = [p for p in UNANALYSED_ROOT.iterdir() if p.is_dir() and p.name.startswith("unanalysed-")]
    nums = [int(p.name.split("-")[-1]) for p in existing if p.name.split("-")[-1].isdigit()]
    next_num = max(nums, default=0) + 1
    folder = UNANALYSED_ROOT / f"unanalysed-{next_num:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def cleanup_unanalysed_folders() -> None:
    """Delete any empty ``unanalysed-*`` folders under :data:`UNANALYSED_ROOT`."""

    root = UNANALYSED_ROOT.resolve()
    for folder in root.glob("unanalysed-*"):
        if not folder.is_dir():
            continue
        try:
            folder_resolved = folder.resolve()
            if folder_resolved.is_relative_to(root) and not any(folder_resolved.iterdir()):
                shutil.rmtree(folder_resolved, ignore_errors=True)
        except Exception as exc:  # pragma: no cover - unexpected IO
            logging.getLogger(__name__).error("Failed cleaning %s: %s", folder, exc)


def move_and_log(src: Path, dest: Path, uid: str, status: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    reg = _load_registry()
    rec = reg.get(uid, {})
    rec.setdefault("history", []).append({
        "status": status,
        "folder": str(dest.parent),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    rec["current_folder"] = str(dest.parent)
    rec["status"] = status
    assets = set(rec.get("assets", []))
    assets.add(dest.name)
    rec["assets"] = sorted(assets)
    reg[uid] = rec
    _save_registry(reg)


def update_status(uid: str, folder: Path, status: str) -> None:
    reg = _load_registry()
    rec = reg.get(uid)
    if not rec:
        return
    rec.setdefault("history", []).append({
        "status": status,
        "folder": str(folder),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    rec["current_folder"] = str(folder)
    rec["status"] = status
    reg[uid] = rec
    _save_registry(reg)


def register_new_artwork(uid: str, seo_filename: str, folder: Path, asset_files: list[str], status: str, base: str | None = None) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reg = _load_registry()
    reg[uid] = {
        "seo_filename": seo_filename,
        "base": base,
        "current_folder": str(folder),
        "assets": asset_files,
        "status": status,
        "history": [{"status": status, "folder": str(folder), "timestamp": ts}],
        "upload_date": ts,
    }
    _save_registry(reg)


def get_record_by_base(base: str) -> tuple[str, dict] | tuple[None, None]:
    reg = _load_registry()
    for uid, rec in reg.items():
        if rec.get("base") == base:
            return uid, rec
    return None, None


def get_record_by_seo_filename(seo_filename: str) -> tuple[str, dict] | tuple[None, None]:
    reg = _load_registry()
    for uid, rec in reg.items():
        if rec.get("seo_filename") == seo_filename:
            return uid, rec
    return None, None

def assemble_gdws_description(aspect_ratio: str) -> str:
    """
    Assembles a full description by randomly selecting one variation from each
    paragraph type within the specified aspect ratio folder in the GDWS.
    """
    logger = logging.getLogger(__name__)
    description_parts = []
    aspect_path = config.GDWS_CONTENT_DIR / aspect_ratio

    if not aspect_path.exists():
        logger.warning(f"GDWS content for aspect ratio '{aspect_ratio}' not found.")
        return ""

    # Get all paragraph type folders (e.g., about_the_artist, printing_tips)
    paragraph_folders = sorted([p for p in aspect_path.iterdir() if p.is_dir()])

    for folder_path in paragraph_folders:
        variations = list(folder_path.glob("*.json"))
        if variations:
            # Pick one random variation file
            chosen_variation_path = random.choice(variations)
            try:
                with open(chosen_variation_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("content"):
                        description_parts.append(data["content"])
            except Exception as e:
                logger.error(f"Failed to load or parse GDWS variation {chosen_variation_path}: {e}")

    logger.info(f"Assembled description from {len(description_parts)} GDWS paragraphs for '{aspect_ratio}'.")
    return "\n\n".join(description_parts)

---
## scripts/analyze_artwork.py
---
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""ART Narrator | analyze_artwork.py
===============================================================
Professional, production-ready, fully sectioned and sub-sectioned
Robbie Mode™ script for analyzing artworks with OpenAI.
"""
# This file now references all path, directory, and filename variables strictly from config.py. No local or hardcoded path constants remain.

# ============================== [ Imports ] ===============================
import argparse
import datetime as _dt
import json
import logging
import os
import random
import re
import shutil
import sys
import traceback
from pathlib import Path
import contextlib
import fcntl

# Ensure project root is on sys.path for ``config`` import when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
import base64
from dotenv import load_dotenv
from openai import OpenAI
from config import (
    BASE_DIR,
    UNANALYSED_ROOT,
    MOCKUPS_INPUT_DIR as MOCKUPS_DIR,
    ONBOARDING_PATH,
    PROCESSED_ROOT,
    LOGS_DIR,
    SKU_TRACKER,
    OUTPUT_JSON,
)
import config
from utils.logger_utils import sanitize_blob_data
# UPDATED IMPORT: We need the new assembler function
from routes.utils import assemble_gdws_description

Image.MAX_IMAGE_PIXELS = None

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in environment")
client = OpenAI(
    api_key=API_KEY,
    project=config.OPENAI_PROJECT_ID,
)


# ======================= [ 1. CONFIGURATION & PATHS ] =======================

MOCKUPS_PER_LISTING = 9  # 1 thumb + 9 mockups

# --- [ 1.3: Etsy Colour Palette ]
ETSY_COLOURS = {
    'Beige': (222, 202, 173), 'Black': (24, 23, 22), 'Blue': (42, 80, 166), 'Bronze': (140, 120, 83),
    'Brown': (110, 72, 42), 'Clear': (240, 240, 240), 'Copper': (181, 101, 29), 'Gold': (236, 180, 63),
    'Grey': (160, 160, 160), 'Green': (67, 127, 66), 'Orange': (237, 129, 40), 'Pink': (229, 100, 156),
    'Purple': (113, 74, 151), 'Rainbow': (170, 92, 152), 'Red': (181, 32, 42), 'Rose gold': (212, 150, 146),
    'Silver': (170, 174, 179), 'White': (242, 242, 243), 'Yellow': (242, 207, 46)
}


# ====================== [ 2. LOGGING CONFIGURATION ] ========================
START_TS = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d-%H%M")
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / f"analyze-artwork-{START_TS}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")]
)
logger = logging.getLogger("analyze_artwork")

# Additional logger for OpenAI API call details
openai_log_path = LOGS_DIR / (
    "analyze-openai-calls-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d") + ".log"
)
openai_logger = logging.getLogger("openai_analysis")
if not openai_logger.handlers:
    openai_handler = logging.FileHandler(openai_log_path, encoding="utf-8")
    openai_handler.setFormatter(logging.Formatter("%(message)s"))
    openai_logger.addHandler(openai_handler)
    openai_logger.setLevel(logging.INFO)


# User/session information for logging
USER_ID = os.getenv("USER_ID", "anonymous")


class _Tee:
    """Simple tee to duplicate stdout/stderr to the log file."""
    def __init__(self, original, log_file):
        self._original = original
        self._log = log_file

    def write(self, data):
        self._original.write(data)
        self._original.flush()
        self._log.write(data)
        self._log.flush()

    def flush(self):
        self._original.flush()
        self._log.flush()


# ======================== [ 3. UTILITY FUNCTIONS ] ==========================

def get_aspect_ratio(image_path: Path) -> str:
    """Return closest aspect ratio label for given image."""
    with Image.open(image_path) as img:
        w, h = img.size
    aspect_map = [
        ("1x1", 1 / 1), ("2x3", 2 / 3), ("3x2", 3 / 2), ("3x4", 3 / 4), ("4x3", 4 / 3),
        ("4x5", 4 / 5), ("5x4", 5 / 4), ("5x7", 5 / 7), ("7x5", 7 / 5), ("9x16", 9 / 16),
        ("16x9", 16 / 9), ("A-Series-Horizontal", 1.414 / 1), ("A-Series-Vertical", 1 / 1.414),
    ]
    ar = round(w / h, 4)
    best = min(aspect_map, key=lambda tup: abs(ar - tup[1]))
    logger.info(f"Aspect ratio for {image_path.name}: {best[0]}")
    return best[0]


def pick_mockups(aspect: str, max_count: int = 8) -> list:
    """Select mockup images for the given aspect with graceful fallbacks."""
    primary_dir = MOCKUPS_DIR / f"{aspect}-categorised"
    fallback_dir = MOCKUPS_DIR / aspect

    if primary_dir.exists():
        use_dir = primary_dir
    elif fallback_dir.exists():
        logger.warning(f"Categorised mockup folder missing for {aspect}; using fallback")
        use_dir = fallback_dir
    else:
        logger.error(f"No mockup folder found for aspect {aspect}")
        return []

    candidates = [f for f in use_dir.glob("**/*") if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    random.shuffle(candidates)
    selection = [str(f.resolve()) for f in candidates[:max_count]]
    logger.info(f"Selected {len(selection)} mockups from {use_dir.name} for {aspect}")
    return selection

def read_onboarding_prompt() -> str:
    return Path(ONBOARDING_PATH).read_text(encoding="utf-8")


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\- ]+", "", text)
    text = text.strip().replace(" ", "-")
    return re.sub("-+", "-", text).lower()


# Use the central SKU assigner for all SKU operations
from utils.sku_assigner import get_next_sku, peek_next_sku


def sync_filename_with_sku(seo_filename: str, sku: str) -> str:
    """Update the SKU portion of an SEO filename."""
    if not seo_filename or not sku:
        return seo_filename
    return re.sub(r"RJC-[A-Za-z0-9-]+(?=\.jpg$)", sku, seo_filename)


def parse_text_fallback(text: str) -> dict:
    """Extract key fields from a non-JSON AI response."""
    data = {"fallback_text": text}

    tag_match = re.search(r"Tags:\s*(.*)", text, re.IGNORECASE)
    if tag_match:
        data["tags"] = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]
    else:
        data["tags"] = []

    mat_match = re.search(r"Materials:\s*(.*)", text, re.IGNORECASE)
    if mat_match:
        data["materials"] = [m.strip() for m in mat_match.group(1).split(",") if m.strip()]
    else:
        data["materials"] = []

    title_match = re.search(r"(?:Title|Artwork Title|Listing Title)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if title_match:
        data["title"] = title_match.group(1).strip()

    seo_match = re.search(r"(?:seo[_ ]filename|seo file|filename)\s*[:\-]\s*(.+\.jpe?g)", text, re.IGNORECASE)
    if seo_match:
        data["seo_filename"] = seo_match.group(1).strip()

    prim_match = re.search(r"Primary Colour\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if prim_match:
        data["primary_colour"] = prim_match.group(1).strip()
    sec_match = re.search(r"Secondary Colour\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if sec_match:
        data["secondary_colour"] = sec_match.group(1).strip()

    desc_match = re.search(r"(?:Description|Artwork Description)\s*[:\-]\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if desc_match:
        data["description"] = desc_match.group(1).strip()

    return data


def extract_seo_filename_from_text(text: str, fallback_base: str) -> tuple[str, str]:
    """Attempt to extract an SEO filename from plain text."""
    patterns = [r"^\s*(?:SEO Filename|SEO_FILENAME|SEO FILE|FILENAME)\s*[:\-]\s*(.+)$"]
    for line in text.splitlines():
        for pat in patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                base = re.sub(r"\.jpe?g$", "", m.group(1).strip(), flags=re.IGNORECASE)
                return slugify(base), "regex"

    m = re.search(r"([\w\-]+\.jpe?g)", text, re.IGNORECASE)
    if m:
        base = os.path.splitext(m.group(1))[0]
        return slugify(base), "jpg"

    return slugify(fallback_base), "fallback"


def extract_seo_filename(ai_listing: dict | None, raw_text: str, fallback_base: str) -> tuple[str, bool, str]:
    """Return SEO slug, whether fallback was used, and extraction method."""
    if ai_listing and isinstance(ai_listing, dict) and ai_listing.get("seo_filename"):
        name = os.path.splitext(str(ai_listing["seo_filename"]))[0]
        return slugify(name), False, "json"

    if ai_listing and isinstance(ai_listing, dict) and ai_listing.get("title"):
        slug = slugify(str(ai_listing["title"]))
        return slug, True, "title"

    slug, method = extract_seo_filename_from_text(raw_text, fallback_base)
    return slug, True, method


def make_preview_2000px_max(src_jpg: Path, dest_jpg: Path, target_long_edge: int = 2000, target_kb: int = 700, min_quality: int = 60) -> None:
    with Image.open(src_jpg) as im:
        w, h = im.size
        scale = target_long_edge / max(w, h)
        if scale < 1.0:
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        else:
            im = im.copy()

        q = 92
        for _ in range(12):
            im.save(dest_jpg, "JPEG", quality=q, optimize=True)
            kb = os.path.getsize(dest_jpg) / 1024
            if kb <= target_kb or q <= min_quality:
                break
            q -= 7
    logger.info(f"Saved preview {dest_jpg.name} ({kb:.1f} KB, Q={q})")


def save_finalised_artwork(
    original_path: Path,
    seo_name: str,
    output_base_dir: Path,
    verbose: bool = False,
):
    target_folder = Path(output_base_dir) / seo_name
    target_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created/using folder {target_folder}")

    orig_filename = original_path.name
    seo_main_jpg = target_folder / f"{seo_name}.jpg"
    orig_jpg = target_folder / f"original-{orig_filename}"
    thumb_jpg = target_folder / f"{seo_name}-THUMB.jpg"

    shutil.move(str(original_path), orig_jpg)
    shutil.copy2(orig_jpg, seo_main_jpg)
    logger.info(f"Moved original file for {seo_name}")

    make_preview_2000px_max(seo_main_jpg, thumb_jpg, 2000, 700, 60)
    logger.info(f"Finalised files saved to {target_folder}")

    return str(seo_main_jpg), str(orig_jpg), str(thumb_jpg), str(target_folder)


def add_to_pending_mockups_queue(image_path: str, queue_file: str) -> None:
    try:
        if os.path.exists(queue_file):
            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            if not isinstance(queue, list):
                queue = []
        else:
            queue = []
    except Exception:
        queue = []
    if image_path not in queue:
        queue.append(image_path)
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
    logger.info(f"Added to pending mockups queue: {image_path}")


def make_optimized_image_for_ai(
    src_path: Path,
    out_dir: Path,
    max_edge: int = 2400,
    target_bytes: int = 1024 * 1024,
    start_quality: int = 85,
    min_quality: int = 60,
    verbose: bool = False,
) -> Path:
    """Return path to optimized JPEG for AI analysis."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if verbose:
        print("- Optimizing image for AI input...", end="", flush=True)
    out_path = out_dir / f"{src_path.stem}-OPTIMIZED.jpg"
    try:
        if out_path.exists():
            out_path.unlink()
        with Image.open(src_path) as im:
            w, h = im.size
            scale = max_edge / max(w, h)
            if scale < 1.0:
                im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            else:
                im = im.copy()
            im = im.convert("RGB")

            q = start_quality
            while True:
                im.save(out_path, "JPEG", quality=q, optimize=True)
                if out_path.stat().st_size <= target_bytes or q <= min_quality:
                    break
                q -= 5

            if out_path.stat().st_size > target_bytes:
                logger.warning(
                    f"{out_path.name} exceeds {target_bytes} bytes at Q={q}"
                )

        logger.info(
            f"Optimized image saved for AI: {out_path.name} "
            f"({im.width}x{im.height}, {out_path.stat().st_size} bytes, Q={q})"
        )
        if verbose:
            size_mb = out_path.stat().st_size / 1024 / 1024
            print(
                f" done ({out_path.name}, {size_mb:.1f}MB)"
            )
    except Exception as e:
        logger.error(f"Failed to create optimized image for {src_path}: {e}")
        logger.error(traceback.format_exc())
        raise
    return out_path


# ===================== [ 4. COLOUR DETECTION & MAPPING ] ====================

def closest_colour(rgb_tuple):
    min_dist = float('inf')
    best_colour = None
    for name, rgb in ETSY_COLOURS.items():
        dist = sum((rgb[i] - rgb_tuple[i]) ** 2 for i in range(3)) ** 0.5
        if dist < min_dist:
            min_dist = dist
            best_colour = name
    return best_colour


def get_dominant_colours(img_path: Path, n: int = 2):
    from sklearn.cluster import KMeans
    import numpy as np

    try:
        with Image.open(img_path) as img:
            img = img.convert("RGB")
            w, h = img.size
            crop = img.crop((max(0, w // 2 - 25), max(0, h // 2 - 25), min(w, w // 2 + 25), min(h, h // 2 + 25)))
            crop_dir = LOGS_DIR / "crops"
            crop_dir.mkdir(exist_ok=True)
            crop_path = crop_dir / f"{img_path.stem}-crop.jpg"
            crop.save(crop_path, "JPEG", quality=80)
            logger.debug(f"Saved crop for colour check: {crop_path}")
            img = img.resize((100, 100))
            arr = np.asarray(img).reshape(-1, 3)

        k = max(3, n + 1)
        kmeans = KMeans(n_clusters=k, n_init='auto' if hasattr(KMeans, 'n_init') else 10)
        labels = kmeans.fit_predict(arr)
        counts = np.bincount(labels)
        sorted_idx = counts.argsort()[::-1]
        seen = set()
        colours = []
        for i in sorted_idx:
            rgb = tuple(int(c) for c in kmeans.cluster_centers_[i])
            name = closest_colour(rgb)
            if name not in seen:
                seen.add(name)
                colours.append(name)
            if len(colours) >= n:
                break
        if len(colours) < 2:
            colours = (colours + ["White", "Black"])[:2]
    except Exception as e:
        logger.error(f"Colour detection failed for {img_path}: {e}")
        logger.error(traceback.format_exc())
        colours = ["White", "Black"]

    logger.info(f"Colours for {img_path.name}: {colours}")
    return colours


# ========================= [ 5. OPENAI HANDLER ] ===========================

def generate_ai_listing(
    provider: str,
    system_prompt: str,
    image_path: Path,
    aspect: str,
    assigned_sku: str,
    feedback: str | None = None,
    verbose: bool = False,
) -> tuple[dict | None, bool, str, str, str]:
    """Call the selected AI provider and return listing data."""
    if provider == "google":
        raise NotImplementedError("Google provider logic has been moved to a separate script.")

    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
    except Exception as e:
        logger.error("Failed to read image for OpenAI: %s", e)
        return None, False, "", "filesystem_error", str(e)

    encoded = base64.b64encode(img_bytes).decode("utf-8")
    prompt = (
        system_prompt.strip()
        + f"\n\nThe SKU for this artwork is {assigned_sku}. "
        + "NEVER invent a SKU, ALWAYS use the provided assigned_sku for the 'sku' and filename fields."
    )
    user_content = [
        {"type": "text", "text": f"Artwork filename: {image_path.name}\nAspect ratio: {aspect}\nDescribe and analyze the artwork visually, then generate the listing as per the instructions above."},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
    ]
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": user_content}]
    if feedback:
        messages.append({"role": "user", "content": feedback})
    model = config.OPENAI_MODEL
    if verbose:
        print(f"- Sending to OpenAI API (model={model}, temp=0.92, timeout=60s)...")

    max_retries = 3
    attempt = 1
    last_error = ""
    while attempt <= max_retries:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2100,
                temperature=0.92,
                timeout=60,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()
            safe_msg = sanitize_blob_data(messages)
            openai_logger.info(json.dumps({"provider": "openai", "messages": safe_msg, "response": content[:500]}))
            if verbose:
                print(f"- OpenAI response received (length {len(content)} chars). Parsing...")
            
            try:
                return json.loads(content), True, content, "ok", ""
            except json.JSONDecodeError:
                fallback = parse_text_fallback(content)
                return fallback, False, content, "fallback", "OpenAI response not valid JSON"
        except Exception as exc:
            last_error = str(exc)
            logger.error("OpenAI API error (attempt %s/%s): %s", attempt, max_retries, exc)
            logger.error(traceback.format_exc())
            if verbose:
                print(f"- OpenAI API error: {exc}")
            attempt += 1
            if attempt <= max_retries:
                logger.info("Retrying OpenAI call (attempt %s)...", attempt)
                import time
                time.sleep(2)

    logger.error("OpenAI API failed after %s attempts: %s", max_retries, last_error)
    if verbose:
        print(f"- OpenAI API failed after {max_retries} attempts: {last_error}")
    return (
        {
            "fallback_text": "OpenAI API failed, no listing generated.",
            "error": last_error,
            "model_used": model,
            "attempts": max_retries,
            "image": str(image_path),
            "aspect": aspect,
        },
        False,
        "",
        "api_error",
        last_error,
    )

# ========================= [ 6. MAIN ANALYSIS LOGIC ] =========================

def analyze_single(
    image_path: Path,
    system_prompt: str,
    feedback_text: str | None,
    statuses: list,
    idx: int | None = None,
    total: int | None = None,
    verbose: bool = False,
    provider: str = "openai",
):
    """
    Analyze and process a single image path.
    Handles AI optimization, API calls, result parsing, and saving of outputs.
    """

    # --------------------------------------------------------------------------
    # [6.1] DEFINE TEMP DIRECTORY
    # --------------------------------------------------------------------------
    TEMP_DIR = UNANALYSED_ROOT / "temp"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # [6.2] INITIALIZE STATUS & LOGGING
    # --------------------------------------------------------------------------
    status = {"file": str(image_path), "success": False, "error": "", "provider": provider}
    if verbose:
        msg = f"[{idx}/{total}] " if idx is not None and total is not None else ""
        print(f"{msg}Processing image with {provider}: {image_path}")

    try:
        # ----------------------------------------------------------------------
        # [6.3] VALIDATE IMAGE
        # ----------------------------------------------------------------------
        if not image_path.is_file():
            raise FileNotFoundError(str(image_path))

        # ----------------------------------------------------------------------
        # [6.4] PREPARE DATA FOR AI CALL
        # ----------------------------------------------------------------------
        aspect = get_aspect_ratio(image_path)
        mockups = pick_mockups(aspect, MOCKUPS_PER_LISTING)
        # UPDATED: Use the new GDWS assembler function
        generic_text = assemble_gdws_description(aspect)
        fallback_base = image_path.stem
        assigned_sku = peek_next_sku(SKU_TRACKER)

        # ----------------------------------------------------------------------
        # [6.5] OPTIMIZE IMAGE FOR AI
        # ----------------------------------------------------------------------
        opt_img = make_optimized_image_for_ai(image_path, TEMP_DIR, verbose=verbose)
        size_bytes = Path(opt_img).stat().st_size
        with Image.open(opt_img) as _im:
            dimensions = f"{_im.width}x{_im.height}"

        # Prepare log entries
        log_entry = {
            "file": str(image_path),
            "user_id": USER_ID,
            "opt_image": str(opt_img),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1024 / 1024, 2),
            "dimensions": dimensions,
            "time_sent": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "provider": provider,
        }
        start_ts = _dt.datetime.now(_dt.timezone.utc)
        analysis_entry = {
            "original_file": str(image_path),
            "user_id": USER_ID,
            "optimized_file": str(opt_img),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1024 / 1024, 2),
            "dimensions": dimensions,
            "time_sent": start_ts.isoformat(),
            "provider": provider,
        }

        # ----------------------------------------------------------------------
        # [6.6] CALL AI PROVIDER (no automatic fallback)
        # ----------------------------------------------------------------------
        ai_listing, was_json, raw_response, err_type, err_msg = generate_ai_listing(
            provider, system_prompt, opt_img, aspect, assigned_sku, feedback_text, verbose=verbose,
        )

        # ----------------------------------------------------------------------
        # [6.7] ERROR HANDLING (LOGGING, FAIL EARLY)
        # ----------------------------------------------------------------------
        if not was_json:
            log_entry.update({"status": "fail", "error": err_msg, "error_type": err_type})
            end_ts = _dt.datetime.now(_dt.timezone.utc)
            log_entry.update({
                "time_responded": end_ts.isoformat(),
                "duration_sec": (end_ts - start_ts).total_seconds(),
            })
            safe_entry = sanitize_blob_data(log_entry)
            openai_logger.info(json.dumps(safe_entry))
            analysis_entry.update({
                "time_responded": end_ts.isoformat(),
                "duration_sec": (end_ts - start_ts).total_seconds(),
                "status": "fail",
                "api_response": f"{err_type}: {err_msg}",
            })
            status["error"] = f"{err_type}: {err_msg}"
            raise RuntimeError(err_msg)

        log_entry.update({"status": "success"})
        call_end_ts = _dt.datetime.now(_dt.timezone.utc)
        analysis_entry.update({
            "time_responded": call_end_ts.isoformat(),
            "duration_sec": (call_end_ts - start_ts).total_seconds(),
            "status": "success",
            "api_response": "ok",
        })

        # ----------------------------------------------------------------------
        # [6.8] PARSE AND SAVE FINAL OUTPUTS
        # ----------------------------------------------------------------------
        seo_name, used_fallback_naming, naming_method = extract_seo_filename(ai_listing, raw_response, fallback_base)
        log_entry.update({
            "used_fallback_naming": used_fallback_naming,
            "naming_method": naming_method,
        })
        analysis_entry.update({
            "used_fallback_naming": used_fallback_naming,
            "naming_method": naming_method,
        })

        if verbose:
            print("- Parsed JSON OK, writing outputs...")

        main_jpg, orig_jpg, thumb_jpg, folder_path = save_finalised_artwork(
            image_path, seo_name, PROCESSED_ROOT, verbose=verbose,
        )
        primary_colour, secondary_colour = get_dominant_colours(Path(main_jpg), 2)

        end_ts = _dt.datetime.now(_dt.timezone.utc)
        log_entry.update({
            "time_responded": end_ts.isoformat(),
            "duration_sec": (end_ts - start_ts).total_seconds(),
            "seo_filename": f"{seo_name}.jpg",
            "processed_folder": str(folder_path),
        })
        safe_entry = sanitize_blob_data(log_entry)
        openai_logger.info(json.dumps(safe_entry))

        # Description and tags/materials filling
        desc = ai_listing.get("description", "") if isinstance(ai_listing, dict) else ""
        if desc:
            if generic_text and not desc.endswith(generic_text.strip()):
                desc = desc.rstrip() + "\n\n" + generic_text.strip()
        else:
            desc = generic_text.strip()
            
        if isinstance(ai_listing, dict):
            ai_listing["description"] = desc

        tags = ai_listing.get("tags", []) if isinstance(ai_listing, dict) else []
        materials = ai_listing.get("materials", []) if isinstance(ai_listing, dict) else []
        if not tags:
            logger.warning(f"No tags extracted for {image_path.name}")
        if not materials:
            logger.warning(f"No materials extracted for {image_path.name}")

        # ----------------------------------------------------------------------
        # [6.9] ARTWORK ENTRY & HISTORY MANAGEMENT
        # ----------------------------------------------------------------------
        per_artwork_json = Path(folder_path) / f"{seo_name}-listing.json"
        existing_sku = None
        analysis_history = []
        if per_artwork_json.exists():
            try:
                with open(per_artwork_json, "r", encoding="utf-8") as pf:
                    prev = json.load(pf)
                existing_sku = prev.get("sku")
                if existing_sku:
                    logger.info(f"Preserving existing SKU {existing_sku} for {seo_name}")
                prev_ai = prev.get("openai_analysis")
                if isinstance(prev_ai, list):
                    analysis_history = prev_ai
                elif prev_ai:
                    analysis_history = [prev_ai]
            except Exception:
                logger.warning(f"Could not read existing SKU from {per_artwork_json}")

        if not existing_sku:
            existing_sku = assigned_sku
            logger.info(f"Previewing SKU {existing_sku} for {seo_name} (not yet assigned)")

        if isinstance(ai_listing, dict):
            ai_listing["sku"] = existing_sku
            if ai_listing.get("seo_filename"):
                ai_listing["seo_filename"] = sync_filename_with_sku(str(ai_listing["seo_filename"]), existing_sku)

        artwork_entry = {
            "filename": image_path.name,
            "aspect_ratio": aspect,
            "mockups": mockups,
            "generic_text": generic_text,
            "ai_listing": ai_listing,
            "seo_name": seo_name,
            "used_fallback_naming": used_fallback_naming,
            "main_jpg_path": main_jpg,
            "orig_jpg_path": orig_jpg,
            "thumb_jpg_path": thumb_jpg,
            "processed_folder": str(folder_path),
            "primary_colour": primary_colour,
            "secondary_colour": secondary_colour,
            "tags": tags,
            "materials": materials,
            "sku": existing_sku,
        }
        analysis_history.insert(0, analysis_entry)
        artwork_entry["openai_analysis"] = (
            analysis_history if len(analysis_history) > 1 else analysis_history[0]
        )
        with open(per_artwork_json, "w", encoding="utf-8") as af:
            json.dump(artwork_entry, af, indent=2, ensure_ascii=False)
        logger.info(f"Wrote listing JSON to {per_artwork_json}")
        if verbose:
            print(f"- Main image: {main_jpg}")
            print(f"- Thumb: {thumb_jpg}")
            print(f"- Listing JSON: {per_artwork_json}")

        # Add to pending mockups queue
        queue_file = PROCESSED_ROOT / "pending_mockups.json"
        add_to_pending_mockups_queue(main_jpg, str(queue_file))

        status["success"] = True
        logger.info(f"Completed analysis for {image_path.name}")
        return artwork_entry

    except Exception as e:
        status["error"] = str(e)
        logger.error(f"Failed processing {image_path}: {e}")
        logger.error(traceback.format_exc())
        if verbose:
            print(f"- Error: {e}")
        raise

    finally:
        with contextlib.suppress(Exception):
            if 'opt_img' in locals() and Path(opt_img).exists():
                Path(opt_img).unlink()
        statuses.append(status)
        if verbose:
            print("[OK]" if status["success"] else "[FAIL]")


# ============================= [ 7. MAIN ENTRY ] ==============================

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze artwork(s) with AI providers")
    parser.add_argument("image", nargs="?", help="Single image path to process")
    parser.add_argument("--feedback", help="Optional feedback text file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose progress output")
    parser.add_argument(
        "--provider",
        choices=["openai"],
        default="openai",
        help="AI provider to use (only 'openai' is supported)",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit result JSON to stdout for subprocess integration",
    )
    return parser.parse_args()


def main() -> None:
    # --------------------------------------------------------------------------
    # [7.1] PARSE ARGS AND PREP TEMP DIR
    # --------------------------------------------------------------------------
    args = parse_args()
    provider = args.provider
    json_output = args.json_output
    
    if not json_output:
        _log_fp = open(LOG_FILE, "a", encoding="utf-8")
        sys.stdout = _Tee(sys.stdout, _log_fp)
        sys.stderr = _Tee(sys.stderr, _log_fp)
        logger.info("=== ART Narrator: OpenAI Analyzer Started (Interactive Mode) ===")
        print(f"\n===== DreamArtMachine Lite: {provider.capitalize()} Analyzer =====\n")
    else:
        logger.info("=== ART Narrator: OpenAI Analyzer Started (JSON Output Mode) ===")


    TEMP_DIR = UNANALYSED_ROOT / "temp"
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # [7.2] LOAD SYSTEM PROMPT
    # --------------------------------------------------------------------------
    try:
        system_prompt = read_onboarding_prompt()
    except Exception as e:
        logger.error(f"Could not read onboarding prompt: {e}")
        logger.error(traceback.format_exc())
        if not json_output:
            print(f"Error: Could not read onboarding prompt. See log at {LOG_FILE}")
        sys.exit(1)

    # --------------------------------------------------------------------------
    # [7.3] HANDLE VERBOSE/FEEDBACK
    # --------------------------------------------------------------------------
    env_verbose = os.getenv("VERBOSE") == "1"
    verbose = args.verbose or env_verbose
    if verbose and not json_output:
        print("Verbose mode enabled\n")
    feedback_text = None
    if args.feedback:
        try:
            feedback_text = Path(args.feedback).read_text(encoding="utf-8")
            logger.info(f"Loaded feedback from {args.feedback}")
        except Exception as e:
            logger.error(f"Failed to read feedback file {args.feedback}: {e}")
            logger.error(traceback.format_exc())

    single_path = Path(args.image) if args.image else None

    results = []
    statuses: list = []

    # --------------------------------------------------------------------------
    # [7.4] MAIN PROCESSING LOGIC (SINGLE OR BATCH)
    # --------------------------------------------------------------------------
    if single_path:
        logger.info(f"Single-image mode: {single_path}")
        try:
            entry = analyze_single(
                single_path,
                system_prompt,
                feedback_text,
                statuses,
                1,
                1,
                verbose,
                provider,
            )
            if json_output:
                original_stdout = sys.stdout._original if isinstance(sys.stdout, _Tee) else sys.stdout
                original_stdout.write(json.dumps(entry, indent=2))
                sys.exit(0)
            if entry:
                results.append(entry)
        except Exception as e:  # noqa: BLE001
            if json_output:
                error_payload = {"success": False, "error": str(e), "traceback": traceback.format_exc()}
                original_stderr = sys.stderr._original if isinstance(sys.stderr, _Tee) else sys.stderr
                original_stderr.write(json.dumps(error_payload, indent=2))
                sys.exit(1)
            raise
    else:
        all_images = [f for f in UNANALYSED_ROOT.rglob("*.jpg") if f.is_file()]
        total = len(all_images)
        logger.info(f"Batch mode: {total} images found")
        for idx, img_path in enumerate(sorted(all_images), 1):
            if verbose:
                print(f"[{idx}/{total}] Processing image with {provider}: {img_path.relative_to(UNANALYSED_ROOT)}")
            entry = analyze_single(img_path, system_prompt, feedback_text, statuses, idx, total, verbose, provider)
            if entry:
                results.append(entry)

    # --------------------------------------------------------------------------
    # [7.5] WRITE MASTER OUTPUT
    # --------------------------------------------------------------------------
    if results:
        # NOTE: This writes a master list for batch runs, may not be needed
        # for single-file runs via the web UI.
        OUTPUT_JSON.parent.mkdir(exist_ok=True)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as out_f:
            json.dump(results, out_f, indent=2, ensure_ascii=False)
        logger.info(f"Wrote master JSON to {OUTPUT_JSON}")

    # --------------------------------------------------------------------------
    # [7.6] SUMMARY OUTPUT
    # --------------------------------------------------------------------------
    success_count = len([s for s in statuses if s["success"]])
    fail_count = len(statuses) - success_count
    logger.info(f"Analysis complete. Success: {success_count}, Failures: {fail_count}")

    if not json_output:
        if verbose:
            print("\n=== SUMMARY ===")
            print(f"Success: {success_count}   Failed: {fail_count}")
            print(f"See logs at: {LOG_FILE}")
            print(f"Processed output folder: {PROCESSED_ROOT}\n")
        else:
            print(f"\nListings processed! See logs at: {LOG_FILE}")
            if fail_count:
                print(f"{fail_count} file(s) failed. Check the log for details.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        is_json_output = "--json-output" in sys.argv
        if is_json_output:
            error_payload = {"success": False, "error": str(e), "traceback": traceback.format_exc()}
            original_stderr = sys.stderr._original if isinstance(sys.stderr, _Tee) else sys.stderr
            original_stderr.write(json.dumps(error_payload, indent=2))
        else:
            print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        sys.exit(1)

---
## scripts/analyze_artwork_google.py
---
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DreamArtMachine Lite | analyze_artwork_google.py
===============================================================
Dedicated script for analyzing artworks with Google's Gemini Pro Vision.
This script is designed to be called via subprocess.

- Receives a single image path as a command-line argument.
- Prints the final JSON analysis to stdout on success.
- Prints a JSON error object to stderr on failure.
"""

# ============================== [ Imports ] ===============================
import argparse
import datetime as _dt
import json
import logging
import os
import re
import sys
import traceback
from pathlib import Path

# Ensure project root is on sys.path for `config` import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv

import config
from config import (
    LOGS_DIR,
    ONBOARDING_PATH,
    SKU_TRACKER,
    UNANALYSED_ROOT,
)
from utils.logger_utils import sanitize_blob_data
from utils.sku_assigner import peek_next_sku

Image.MAX_IMAGE_PIXELS = None
load_dotenv()

# ====================== [ 1. Configuration & Setup ] ========================

# Configure Google API
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY", ""))
except Exception as e:
    sys.stderr.write(json.dumps({"success": False, "error": f"Failed to configure Google API: {e}"}))
    sys.exit(1)

# Configure Logging
LOGS_DIR.mkdir(exist_ok=True)
google_log_path = LOGS_DIR / (
    "analyze-google-calls-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d") + ".log"
)
google_logger = logging.getLogger("google_analysis")
if not google_logger.handlers:
    handler = logging.FileHandler(google_log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    google_logger.addHandler(handler)
    google_logger.setLevel(logging.INFO)

# ======================== [ 2. Utility Functions ] ==========================

def get_aspect_ratio(image_path: Path) -> str:
    """Return closest aspect ratio label for a given image."""
    with Image.open(image_path) as img:
        w, h = img.size
    aspect_map = [
        ("1x1", 1/1), ("2x3", 2/3), ("3x2", 3/2), ("3x4", 3/4), ("4x3", 4/3),
        ("4x5", 4/5), ("5x4", 5/4), ("5x7", 5/7), ("7x5", 7/5), ("9x16", 9/16),
        ("16x9", 16/9), ("A-Series-Horizontal", 1.414/1), ("A-Series-Vertical", 1/1.414),
    ]
    ar = round(w / h, 4)
    best = min(aspect_map, key=lambda tup: abs(ar - tup[1]))
    return best[0]

def parse_text_fallback(text: str) -> dict:
    """Extract key fields from a non-JSON AI response."""
    data = {"fallback_text": text}
    title_match = re.search(r"(?:Title|Artwork Title)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if title_match:
        data["title"] = title_match.group(1).strip()
    tag_match = re.search(r"Tags:\s*(.*)", text, re.IGNORECASE)
    if tag_match:
        data["tags"] = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]
    return data

def make_optimized_image_for_ai(src_path: Path, out_dir: Path) -> Path:
    """Return path to an optimized JPEG, creating it if necessary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{src_path.stem}-GOOGLE-OPTIMIZED.jpg"
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        im.thumbnail((2048, 2048), Image.LANCZOS)
        im.save(out_path, "JPEG", quality=85, optimize=True)
    return out_path

# ========================= [ 3. Main Analysis Logic ] =========================

def analyze_with_google(image_path: Path):
    """Analyze an image using Google Gemini."""
    start_ts = _dt.datetime.now(_dt.timezone.utc)
    log_entry = {
        "file": str(image_path),
        "provider": "google",
        "time_sent": start_ts.isoformat(),
    }

    try:
        if not image_path.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        temp_dir = UNANALYSED_ROOT / "temp"
        opt_img_path = make_optimized_image_for_ai(image_path, temp_dir)
        aspect = get_aspect_ratio(opt_img_path)
        assigned_sku = peek_next_sku(SKU_TRACKER)
        system_prompt = Path(ONBOARDING_PATH).read_text(encoding="utf-8")

        with open(opt_img_path, "rb") as f:
            img_bytes = f.read()

        prompt = (
            system_prompt.strip()
            + f"\n\nThe SKU for this artwork is {assigned_sku}. "
            + "NEVER invent a SKU, ALWAYS use the provided assigned_sku for the 'sku' and filename fields."
        )

        model_name = config.GOOGLE_GEMINI_PRO_VISION_MODEL_NAME
        parts = [
            prompt,
            f"Artwork filename: {image_path.name}\nAspect ratio: {aspect}\n" "Describe and analyze the artwork visually, then generate the listing as per the instructions above.",
            img_bytes,
        ]

        response = genai.GenerativeModel(model_name).generate_content(
            parts,
            generation_config={"temperature": 0.92},
            stream=False,
        )
        content = response.text.strip()

        safe_parts_for_log = [p for p in parts if not isinstance(p, bytes)]
        log_entry["prompt"] = safe_parts_for_log
        log_entry["response_preview"] = content[:500]

        try:
            ai_listing = json.loads(content)
            was_json = True
            err_msg = ""
        except json.JSONDecodeError:
            ai_listing = parse_text_fallback(content)
            was_json = False
            err_msg = "Google response not valid JSON"

        log_entry.update({
            "status": "success" if was_json else "fallback",
            "error": err_msg,
            "duration_sec": (_dt.datetime.now(_dt.timezone.utc) - start_ts).total_seconds(),
        })
        google_logger.info(json.dumps(sanitize_blob_data(log_entry)))

        return {"ai_listing": ai_listing, "was_json": was_json, "raw_response": content, "error_type": "fallback" if not was_json else "ok", "error_message": err_msg}

    except Exception as e:
        tb = traceback.format_exc()
        log_entry.update({
            "status": "fail",
            "error": str(e),
            "traceback": tb,
            "duration_sec": (_dt.datetime.now(_dt.timezone.utc) - start_ts).total_seconds(),
        })
        google_logger.info(json.dumps(sanitize_blob_data(log_entry)))
        raise RuntimeError(f"Google analysis failed: {e}") from e
    finally:
        if 'opt_img_path' in locals() and opt_img_path.exists():
            opt_img_path.unlink()


# ============================= [ 4. Main Entry ] ==============================
def main():
    parser = argparse.ArgumentParser(description="Analyze a single artwork with Google Gemini.")
    parser.add_argument("image", help="Path to the image file to process.")
    args = parser.parse_args()

    try:
        image_path = Path(args.image).resolve()
        result = analyze_with_google(image_path)
        safe_result = sanitize_blob_data(result)
        sys.stdout.write(json.dumps(safe_result, indent=2))
        sys.exit(0)
    except Exception as e:
        error_payload = {"success": False, "error": str(e), "traceback": traceback.format_exc()}
        sys.stderr.write(json.dumps(error_payload, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)}))
        sys.exit(1)


---
## scripts/generate_composites.py
---
import os
import json
import shutil
import random
import re
from pathlib import Path
from PIL import Image, ImageDraw
import cv2
import numpy as np

# Ensure project root is on sys.path for ``config`` import when run directly
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# This file now references all path, directory, and filename variables strictly from config.py. No local or hardcoded path constants remain.
import config

Image.MAX_IMAGE_PIXELS = None
DEBUG_MODE = False

# ======================= [ 1. CONFIG & PATHS ] =======================
QUEUE_FILE = config.PROCESSED_ROOT / "pending_mockups.json"

# ======================= [ 2. UTILITIES ] =========================

def resize_image_for_long_edge(image: Image.Image, target_long_edge=2000) -> Image.Image:
    width, height = image.size
    scale = target_long_edge / max(width, height)
    if scale < 1.0:
        new_width = int(width * scale)
        new_height = int(height * scale)
        return image.resize((new_width, new_height), Image.LANCZOS)
    return image

def apply_perspective_transform(art_img, mockup_img, dst_coords):
    w, h = art_img.size
    src_points = np.float32([[0, 0], [w, 0], [0, h], [w, h]]) # Corrected order for sort_corners
    dst_points = np.float32([[c['x'], c['y']] for c in dst_coords])
    
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    art_np = np.array(art_img.convert("RGBA"))
    
    warped = cv2.warpPerspective(art_np, matrix, (mockup_img.width, mockup_img.height))
    
    mockup_rgba = mockup_img.convert("RGBA")
    warped_pil = Image.fromarray(warped)
    
    # Composite the warped image over the mockup
    final_image = Image.alpha_composite(mockup_rgba, warped_pil)
    return final_image

def remove_from_queue(processed_img_path, queue_file):
    """Remove the processed image from the pending queue."""
    if os.path.exists(queue_file):
        with open(queue_file, "r", encoding="utf-8") as f:
            queue = json.load(f)
        new_queue = [p for p in queue if p != processed_img_path]
        with open(queue_file, "w", encoding="utf-8") as f:
            json.dump(new_queue, f, indent=2)

# =============== [ 3. MAIN WORKFLOW: QUEUE-BASED PROCESSING ] ================
def main():
    print("\n===== ArtNarrator Lite: Composite Generator (Queue Mode) =====\n")

    if not QUEUE_FILE.exists():
        print(f"⚠️ No pending mockups queue found at {QUEUE_FILE}")
        return

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)
    if not queue:
        print(f"✅ No pending artworks in queue. All done!")
        return

    print(f"🎨 {len(queue)} artworks in the pending queue.\n")

    processed_count = 0
    for img_path_str in queue[:]:
        img_path = Path(img_path_str)
        if not img_path.exists():
            print(f"❌ File not found (skipped): {img_path}")
            remove_from_queue(str(img_path), QUEUE_FILE)
            continue

        folder = img_path.parent
        seo_name = img_path.stem
        
        json_listing = folder / f"{seo_name}-listing.json"
        if not json_listing.exists():
            print(f"⚠️ Listing JSON not found for {img_path.name}, skipping.")
            remove_from_queue(str(img_path), QUEUE_FILE)
            continue
            
        with open(json_listing, "r", encoding="utf-8") as jf:
            entry = json.load(jf)
        aspect = entry.get("aspect_ratio")
        
        print(f"\n[{processed_count+1}/{len(queue)}] Processing: {img_path.name} [{aspect}]")

        mockups_cat_dir = config.MOCKUPS_CATEGORISED_DIR / f"{aspect}-categorised"
        coords_base_dir = config.COORDS_DIR / aspect
        
        if not mockups_cat_dir.exists() or not coords_base_dir.exists():
            print(f"⚠️ Missing mockups or coordinates for aspect: {aspect}")
            remove_from_queue(str(img_path), QUEUE_FILE)
            continue

        art_img = Image.open(img_path)
        mockup_entries = []
        
        categories = [d for d in mockups_cat_dir.iterdir() if d.is_dir()]
        selections = []
        for cat in categories:
            pngs = list(cat.glob("*.png"))
            if pngs:
                selections.append((cat, random.choice(pngs)))

        if not selections:
            print(f"⚠️ No mockups found for aspect {aspect}")
            remove_from_queue(str(img_path), QUEUE_FILE)
            continue

        random.shuffle(selections)
        if len(selections) >= 9:
            selections = random.sample(selections, 9)
        else:
            while len(selections) < 9:
                cat = random.choice(categories)
                pngs = list(cat.glob("*.png"))
                if pngs:
                    selections.append((cat, random.choice(pngs)))
            print(f"⚠️ Only {len(categories)} unique categories available; duplicates used to reach 9")

        for cat_dir, mockup_file in selections:
            coord_path = coords_base_dir / cat_dir.name / f"{mockup_file.stem}.json"
            if not coord_path.exists():
                print(f"⚠️ Missing coordinates for {mockup_file.name} ({aspect}/{cat_dir.name})")
                continue

            with open(coord_path, "r", encoding="utf-8") as f:
                coords_data = json.load(f)

            mockup_img = Image.open(mockup_file)
            composite = apply_perspective_transform(art_img, mockup_img, coords_data["corners"])

            output_filename = f"{seo_name}-{mockup_file.stem}.jpg"
            output_path = folder / output_filename
            composite.convert("RGB").save(output_path, "JPEG", quality=90)

            tid = re.search(r"(\d+)$", mockup_file.stem)
            thumb_dir = folder / "THUMBS"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb_filename = f"{seo_name}-{aspect}-mockup-thumb-{tid.group(1) if tid else '0'}.jpg"
            thumb_path = thumb_dir / thumb_filename
            if not thumb_path.exists():
                thumb_img = composite.copy()
                thumb_img.thumbnail((config.THUMB_WIDTH, config.THUMB_HEIGHT))
                thumb_img.convert("RGB").save(thumb_path, "JPEG", quality=85)

            mockup_entries.append({
                "category": cat_dir.name,
                "source": str(mockup_file.relative_to(config.MOCKUPS_INPUT_DIR)),
                "composite": output_filename,
            })
            print(f"   - Mockup created: {output_filename} ({cat_dir.name})")

        listing_data = entry
        listing_data["mockups"] = mockup_entries
        with open(json_listing, "w", encoding="utf-8") as lf:
            json.dump(listing_data, lf, indent=2, ensure_ascii=False)

        print(f"🎯 Finished all mockups for {img_path.name}.")
        processed_count += 1
        remove_from_queue(str(img_path), QUEUE_FILE)

    print(f"\n✅ Done. {processed_count} artwork(s) processed and removed from queue.\n")

if __name__ == "__main__":
    main()

---
## scripts/generate_coordinates.py
---
#!/usr/bin/env python3
# =============================================================================
# ArtNarrator: Automated Mockup Coordinate Generator
# Purpose:
#   Scans all PNG mockups, fixes any broken sRGB profiles to prevent warnings,
#   and automatically detects the transparent artwork zone, outputting a
#   JSON coordinate file for each.
# =============================================================================

import cv2
import json
import logging
import sys
from pathlib import Path
from PIL import Image

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def fix_srgb_profile(image_path: Path):
    """Strips broken ICC profiles from a PNG image to prevent libpng warnings."""
    try:
        with Image.open(image_path) as img:
            if "icc_profile" in img.info and img.format == 'PNG':
                img.save(image_path, format="PNG")
    except Exception as e:
        logger.warning(f"⚠️ Could not clean sRGB profile for {image_path.name}: {e}")

def sort_corners(pts):
    """Sorts 4 corner points to a consistent order: TL, TR, BL, BR."""
    pts = sorted(pts, key=lambda p: (p["y"], p["x"]))
    top = sorted(pts[:2], key=lambda p: p["x"])
    bottom = sorted(pts[2:], key=lambda p: p["x"])
    return [*top, *bottom]

def detect_corner_points(image_path: Path):
    """Detects 4 corner points of a transparent region in a PNG."""
    image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if image is None or image.shape[2] != 4: return None
    alpha = image[:, :, 3]
    _, thresh = cv2.threshold(alpha, 1, 255, cv2.THRESH_BINARY)
    thresh_inv = cv2.bitwise_not(thresh)
    contours, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    contour = max(contours, key=cv2.contourArea)
    epsilon = 0.02 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    if len(approx) != 4: return None
    corners = [{"x": int(pt[0][0]), "y": int(pt[0][1])} for pt in approx]
    return sort_corners(corners)

def main():
    """Main execution function."""
    print("🚀 Starting Automated Coordinate Generation...", flush=True)
    
    processed_count = 0
    error_count = 0
    
    mockup_root = config.MOCKUPS_CATEGORISED_DIR
    coord_root = config.COORDS_DIR

    if not mockup_root.exists():
        print(f"❌ Error: Mockup directory not found: {mockup_root}", flush=True)
        return

    for aspect_dir in sorted(mockup_root.iterdir()):
        if not aspect_dir.is_dir(): continue
        
        aspect_name = aspect_dir.name.replace("-categorised", "")
        coord_aspect_dir = coord_root / aspect_name
        
        for category_dir in sorted(aspect_dir.iterdir()):
            if not category_dir.is_dir(): continue

            print(f"\n🔍 Processing Category: {aspect_dir.name}/{category_dir.name}", flush=True)
            output_dir = coord_aspect_dir / category_dir.name
            output_dir.mkdir(parents=True, exist_ok=True)

            for mockup_file in sorted(category_dir.glob("*.png")):
                output_path = output_dir / f"{mockup_file.stem}.json"
                print(f"  -> Processing {mockup_file.name}...", flush=True)
                try:
                    fix_srgb_profile(mockup_file)
                    corners = detect_corner_points(mockup_file)
                    if corners:
                        data = {"template": mockup_file.name, "corners": corners}
                        with open(output_path, 'w') as f:
                            json.dump(data, f, indent=4)
                        processed_count += 1
                    else:
                        print(f"  ⚠️ Skipped (no valid 4-corner area found): {mockup_file.name}", flush=True)
                        error_count += 1
                except Exception as e:
                    print(f"  ❌ Error processing {mockup_file.name}: {e}", flush=True)
                    error_count += 1

    print(f"\n🏁 Finished. Processed: {processed_count}, Errors/Skipped: {error_count}\n", flush=True)

if __name__ == "__main__":
    main()

---
## scripts/generate_coordinates_for_ratio.py
---
#!/usr/bin/env python3
# ==============================================================================
# Script: generate_coordinates_for_ratio.py
# Purpose: Scans all PNGs in a given categorized aspect ratio folder,
#          prompts the user to click 4 corners, and saves the coordinates.
# ==============================================================================

import argparse
import pathlib
import logging
import sys
import json
import cv2

# Ensure project root is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def get_args():
    parser = argparse.ArgumentParser(description="Generate coordinates for a single aspect ratio")
    parser.add_argument("--aspect_ratio_path", type=str, required=True, help="Path to an aspect ratio folder (e.g., .../4x5-categorised)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing coordinate files")
    return parser.parse_args()

def pick_points_gui(img_path):
    """Opens a GUI for the user to select 4 corner points."""
    img = cv2.imread(str(img_path))
    if img is None:
        raise IOError(f"Could not read image: {img_path}")
    points = []
    window_name = "Select Corners (TL, TR, BR, BL) - Press ESC to confirm"

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append((x, y))
            cv2.circle(img, (x, y), 7, (0, 255, 0), -1)
            cv2.imshow(window_name, img)

    cv2.imshow(window_name, img)
    cv2.setMouseCallback(window_name, mouse_callback)
    while len(points) < 4:
        key = cv2.waitKey(20) & 0xFF
        if key == 27: # ESC key
            break
    cv2.destroyAllWindows()
    if len(points) != 4:
        raise Exception("Did not select exactly 4 points. Aborted.")
    return points

def main():
    args = get_args()
    aspect_folder = pathlib.Path(args.aspect_ratio_path).resolve()
    aspect_name = aspect_folder.name.replace("-categorised", "")
    
    # Define the output directory based on the aspect name
    out_base = config.COORDS_DIR / aspect_name
    logger.info(f"Saving coordinates to: {out_base}")

    for category_dir in sorted(aspect_folder.iterdir()):
        if not category_dir.is_dir():
            continue
        
        logger.info(f"--- Processing Category: {category_dir.name} ---")
        out_cat_folder = out_base / category_dir.name
        out_cat_folder.mkdir(parents=True, exist_ok=True)
        
        for img in sorted(category_dir.glob("*.png")):
            coord_file = out_cat_folder / f"{img.stem}.json"
            if coord_file.exists() and not args.overwrite:
                logger.info(f"✅ Skipping, coordinates exist: {img.name}")
                continue
            
            logger.info(f"👉 Please select coordinates for: {img.name}")
            try:
                points = pick_points_gui(img)
                # Convert points to the required JSON structure
                corners = [
                    {"x": points[0][0], "y": points[0][1]}, # Top-Left
                    {"x": points[1][0], "y": points[1][1]}, # Top-Right
                    {"x": points[3][0], "y": points[3][1]}, # Bottom-Left (Note: CV2 order vs your format)
                    {"x": points[2][0], "y": points[2][1]}  # Bottom-Right
                ]
                data = {"filename": img.name, "corners": corners}
                with open(coord_file, "w") as f:
                    json.dump(data, f, indent=2)
                logger.info(f"✅ Saved coordinates for: {img.name}")
            except Exception as e:
                logger.error(f"❌ Failed to process {img}: {e}")

if __name__ == "__main__":
    main()

---
## scripts/populate_gdws.py
---
"""
One-time script to parse the generic text files and populate the GDWS content directory.
"""
import os
import re
import json
from pathlib import Path

# --- Configuration ---
# This script assumes it's in the 'scripts' directory and the project root is one level up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Reads from your existing 'generic_texts' directory
SOURCE_TEXT_DIR = PROJECT_ROOT / "generic_texts"
GDWS_CONTENT_DIR = PROJECT_ROOT / "data" / "gdws_content"

# Define the paragraph headings to look for in the text files
PARAGRAPH_HEADINGS = [
    "About the Artist – Robin Custance", "Did You Know? Aboriginal Art & the Spirit of Dot Painting",
    "What You’ll Receive", "Ideal Uses for the", "Printing Tips",
    "Top 10 Print-On-Demand Services for Wall Art & Art Prints", "Important Notes",
    "Frequently Asked Questions", "LET’S CREATE SOMETHING BEAUTIFUL TOGETHER",
    "THANK YOU – FROM MY STUDIO TO YOUR HOME", "EXPLORE MY WORK", "WHY YOU’LL LOVE THIS ARTWORK",
    "HOW TO BUY & PRINT", "Thank You & Stay Connected"
]

def slugify(text):
    """Creates a filesystem-safe name from a heading."""
    s = text.lower()
    s = re.sub(r'[^\w\s-]', '', s).strip()
    s = re.sub(r'[-\s]+', '_', s)
    # Handle specific long names
    if "about_the_artist" in s: return "about_the_artist"
    if "did_you_know" in s: return "about_art_style"
    if "what_youll_receive" in s: return "file_details"
    return s

def parse_and_create_files():
    """Reads source text files, parses them, and creates the GDWS structure."""
    if not SOURCE_TEXT_DIR.exists():
        print(f"❌ Error: Source directory not found at '{SOURCE_TEXT_DIR}'")
        return

    print(f"🚀 Starting GDWS population from '{SOURCE_TEXT_DIR}'...")
    
    GDWS_CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    source_files = list(SOURCE_TEXT_DIR.glob("*.txt"))
    if not source_files:
        print("🤷 No .txt files found in the source directory. Nothing to do.")
        return

    # Create a regex pattern to split the file content by the headings
    split_pattern = re.compile('(' + '|'.join(re.escape(h) for h in PARAGRAPH_HEADINGS) + ')')

    for txt_file in source_files:
        aspect_ratio = txt_file.stem
        # Handle potential typo in filename
        if aspect_ratio.lower() == "a-series-verical":
            aspect_ratio = "A-Series-Vertical"

        aspect_dir = GDWS_CONTENT_DIR / aspect_ratio
        aspect_dir.mkdir(exist_ok=True)
        
        print(f"\nProcessing: {txt_file.name} for aspect ratio '{aspect_ratio}'...")
        
        content = txt_file.read_text(encoding='utf-8')
        # This is the fully corrected line to remove the tags
        content = re.sub(r'\\', '', content).strip()
        
        parts = split_pattern.split(content)
        
        i = 1
        while i < len(parts):
            title = parts[i].strip()
            body = parts[i+1].strip() if (i+1) < len(parts) else ""
            
            folder_name = slugify(title)
            paragraph_dir = aspect_dir / folder_name
            paragraph_dir.mkdir(exist_ok=True)
            
            base_file = paragraph_dir / "base.json"
            
            data_to_save = {
                "id": "base",
                "title": title,
                "content": body,
                "instructions": f"This is the base text for the '{title}' section for the {aspect_ratio} aspect ratio. Edit the text to refine the message for this paragraph."
            }
            
            with open(base_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
                
            print(f"  ✅ Created base file for '{title}'")
            i += 2

    print(f"\n🎉 GDWS population complete! Check the '{GDWS_CONTENT_DIR}' directory.")

if __name__ == "__main__":
    parse_and_create_files()

---
## scripts/run_coordinate_generator.py
---
#!/usr/bin/env python3
# ==============================================================================
# File: run_coordinate_generator.py (ArtNarrator Coordinate Generation Orchestrator)
# Purpose: This script orchestrates the generation of coordinate data for all
#          categorised mockup aspect ratios by calling the worker script.
# ==============================================================================
import subprocess
import pathlib
import logging
import sys

# Ensure project root is on sys.path for config import
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
COORDINATE_GENERATOR_SCRIPT = SCRIPT_DIR / "generate_coordinates_for_ratio.py"
MOCKUPS_INPUT_BASE_DIR = config.MOCKUPS_CATEGORISED_DIR

def run_coordinate_generation_for_all_ratios():
    logger.info(f"Starting coordinate generation using base directory: {MOCKUPS_INPUT_BASE_DIR}")
    if not COORDINATE_GENERATOR_SCRIPT.is_file():
        logger.critical(f"🔴 CRITICAL ERROR: Worker script not found at '{COORDINATE_GENERATOR_SCRIPT}'.")
        return

    if not MOCKUPS_INPUT_BASE_DIR.is_dir():
        logger.critical(f"🔴 CRITICAL ERROR: Mockups directory not found: '{MOCKUPS_INPUT_BASE_DIR}'.")
        return

    # Dynamically find aspect ratio folders
    aspect_ratio_folders = [d.name for d in MOCKUPS_INPUT_BASE_DIR.iterdir() if d.is_dir()]
    
    for ratio_folder_name in aspect_ratio_folders:
        aspect_ratio_path = MOCKUPS_INPUT_BASE_DIR / ratio_folder_name
        logger.info(f"Processing aspect ratio: {ratio_folder_name}")
        try:
            command = [
                sys.executable,
                str(COORDINATE_GENERATOR_SCRIPT),
                "--aspect_ratio_path", str(aspect_ratio_path)
            ]
            logger.info(f"Executing: {' '.join(command)}")
            subprocess.run(command, check=True)
            logger.info(f"✅ Successfully processed aspect ratio: {ratio_folder_name}")
        except Exception as e:
            logger.error(f"🔴 An unexpected error occurred while processing {ratio_folder_name}: {e}", exc_info=True)
        logger.info("-" * 50)
    logger.info("🏁 Finished processing all aspect ratios.")

if __name__ == "__main__":
    run_coordinate_generation_for_all_ratios()

---
## scripts/sellbrite_csv_export.py
---
"""Generate a Sellbrite-compatible CSV from artwork data.

This script reads either an Etsy CSV export or ArtNarrator listing JSON
files and produces a CSV ready for upload to Sellbrite. The Sellbrite
CSV header is taken from a provided template so the column order matches
exactly.

The business rules are enforced:
- Quantity fixed to 25
- Condition set to "New"
- Brand set to "Robin Custance Art"
- Category always "Art & Collectibles > Prints > Digital Prints"
- Weight set to 0 (digital product)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from routes import utils
import config

import pandas as pd


def read_template_header(template_path: Path) -> List[str]:
    """Return the header row from the Sellbrite template CSV."""
    with open(template_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            header = [h.strip() for h in row]
            if header:
                return header
    raise ValueError("Template CSV missing header")


def load_etsy_csv(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield dicts from an Etsy export CSV."""
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        yield row.to_dict()


def load_listing_json(folder: Path) -> Iterable[Dict[str, Any]]:
    """Yield listing data from JSON files within ``folder``."""
    for listing in folder.rglob("*-listing.json"):
        try:
            utils.assign_or_get_sku(listing, config.SKU_TRACKER)
            with open(listing, "r", encoding="utf-8") as f:
                data = json.load(f)
            yield data
        except Exception:
            continue


def ensure_description(text: str) -> str:
    """Return a plain text description of at least 400 words."""
    if not text:
        text = "This digital artwork comes from Australian Aboriginal artist Robin Custance. "
    words = text.split()
    if len(words) < 400:
        pad = (400 - len(words))
        extra = (" Robin shares stories of culture and country through vibrant colours." * 50).split()[:pad]
        words.extend(extra)
    return " ".join(words)


def map_row(data: Dict[str, Any]) -> Dict[str, Any]:
    """Map input fields to Sellbrite fields applying business rules."""
    def first_non_empty(*keys: str) -> Optional[str]:
        for k in keys:
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    sku = first_non_empty("SKU", "sku") or ""
    name = first_non_empty("Title", "title", "name") or sku
    description = first_non_empty("Description", "description") or ""
    description = ensure_description(description)
    price = first_non_empty("Price", "price") or "0"
    tags_raw = first_non_empty("Tags", "tags") or ""
    if isinstance(tags_raw, list):
        tags = ",".join(t.strip().replace(" ", "") for t in tags_raw)
    else:
        tags = ",".join(t.strip().replace(" ", "") for t in str(tags_raw).split(",") if t.strip())

    images: List[str] = []
    for i in range(1, 9):
        img = data.get(f"Image{i}") or data.get(f"image_{i}")
        if not img and i == 1:
            img = data.get("Image1") or data.get("image")
        if img:
            images.append(str(img))
    if not images:
        imgs = data.get("images") or []
        if isinstance(imgs, str):
            imgs = [i for i in imgs.splitlines() if i.strip()]
        images = list(imgs)[:8]

    mapped = {
        "SKU": sku,
        "Name": name,
        "Description": description,
        "Price": price,
        "Quantity": 25,
        "Condition": "New",
        "Brand": "Robin Custance Art",
        "Category": "Art & Collectibles > Prints > Digital Prints",
        "Weight": 0,
    }
    for idx in range(8):
        mapped[f"Image {idx+1}"] = images[idx] if idx < len(images) else ""
    mapped["Tags"] = tags
    return mapped


def export_to_csv(data: Iterable[Dict[str, Any]], template_header: List[str], output: Path) -> None:
    """Write mapped rows to ``output`` with header from template."""
    rows = list(data)
    errors = utils.validate_all_skus(rows, config.SKU_TRACKER)
    if errors:
        raise ValueError("; ".join(errors))

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=template_header)
        writer.writeheader()
        for item in rows:
            mapped = map_row(item)
            row = {k: mapped.get(k, "") for k in template_header}
            writer.writerow(row)



def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate Sellbrite CSV")
    parser.add_argument("template", type=Path, help="Sellbrite template CSV")
    parser.add_argument("output", type=Path, help="Output CSV path")
    parser.add_argument("--etsy", type=Path, help="Etsy CSV export")
    parser.add_argument("--json-dir", type=Path, help="Directory of listing JSON files")
    args = parser.parse_args()

    header = read_template_header(args.template)
    rows: List[Dict[str, Any]] = []
    if args.etsy and args.etsy.exists():
        rows.extend(load_etsy_csv(args.etsy))
    if args.json_dir and args.json_dir.exists():
        rows.extend(load_listing_json(args.json_dir))
    if not rows:
        raise SystemExit("No input data provided")

    export_to_csv(rows, header, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()


---
## scripts/test_connections.py
---
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtNarrator Connection Tester
===============================================================
This script checks all external API and service connections
defined in the project's .env file to ensure keys and credentials
are working correctly. It also verifies access to specific AI models.
"""

import os
import sys
import base64
import smtplib
import requests
from dotenv import load_dotenv

# Ensure the project root is in the Python path to find modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Try to import required libraries and provide helpful errors if they're missing
try:
    import openai
    import google.generativeai as genai
    import config  # Import the application's config
except ImportError as e:
    print(f"❌ Error: A required library is missing. Please run 'pip install {e.name}'")
    sys.exit(1)

# --- Configuration ---
# Load environment variables from the .env file in the project root
load_dotenv(os.path.join(project_root, '.env'))

# --- UI Helpers ---
def print_status(service: str, success: bool, message: str = "") -> None:
    """Prints a formatted status line for a service check."""
    if success:
        print(f"✅ {service:<20} Connection successful. {message}")
    else:
        print(f"❌ {service:<20} FAILED. {message}")

# --- Test Functions ---

def test_openai() -> None:
    """Tests the OpenAI API key and access to specific models."""
    print("\n--- Testing OpenAI ---")
    api_key = config.OPENAI_API_KEY
    if not api_key:
        print_status("OpenAI", False, "OPENAI_API_KEY not found.")
        return

    try:
        client = openai.OpenAI(api_key=api_key)
        client.models.list()  # Basic connection test
        print_status("OpenAI API Key", True, "Key is valid.")

        # Test specific models from config
        models_to_check = {
            "Main Model": config.OPENAI_MODEL,
            "Vision Model": config.OPENAI_VISION_MODEL
        }
        
        errors = []
        for name, model_id in models_to_check.items():
            if not model_id: continue
            try:
                client.models.retrieve(model_id)
                print(f"  - ✅ {name} ({model_id}): Access confirmed.")
            except Exception as e:
                errors.append(f"  - ❌ {name} ({model_id}): FAILED! Error: {e}")
        
        if errors:
            print("\n".join(errors))
            print_status("OpenAI Models", False, "One or more models are inaccessible.")

    except openai.AuthenticationError:
        print_status("OpenAI API Key", False, "AuthenticationError: The API key is incorrect.")
    except Exception as e:
        print_status("OpenAI API Key", False, f"An unexpected error occurred: {e}")

def test_google_gemini() -> None:
    """Tests the Google Gemini API key and access to the specific vision model."""
    print("\n--- Testing Google Gemini ---")
    api_key = config.GEMINI_API_KEY
    if not api_key:
        print_status("Google Gemini", False, "GEMINI_API_KEY not found.")
        return

    try:
        genai.configure(api_key=api_key)
        
        # Test the specific vision model from config
        model_name = config.GOOGLE_GEMINI_PRO_VISION_MODEL_NAME
        if model_name:
             # The genai library requires the 'models/' prefix for get_model
            model_name_for_check = model_name if model_name.startswith('models/') else f'models/{model_name}'
            genai.get_model(model_name_for_check)
            print_status("Google Gemini", True, f"Key is valid and has access to {model_name}.")
        else:
            # Fallback to a general check if no specific model is set
            genai.list_models()
            print_status("Google Gemini", True, "Key is valid (general check).")

    except Exception as e:
        print_status("Google Gemini", False, f"An error occurred: {e}")

def test_sellbrite() -> None:
    """Tests Sellbrite API credentials by making a simple request."""
    print("\n--- Testing Sellbrite ---")
    token = config.SELLBRITE_ACCOUNT_TOKEN
    secret = config.SELLBRITE_SECRET_KEY
    api_base = config.SELLBRITE_API_BASE_URL

    if not token or not secret:
        print_status("Sellbrite", False, "Credentials not found in .env file.")
        return

    try:
        creds = f"{token}:{secret}".encode("utf-8")
        encoded_creds = base64.b64encode(creds).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded_creds}"}
        url = f"{api_base}/warehouses?limit=1"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            print_status("Sellbrite", True)
        else:
            print_status("Sellbrite", False, f"API returned status {response.status_code}. Check credentials.")
    except requests.RequestException as e:
        print_status("Sellbrite", False, f"A network error occurred: {e}")

def test_smtp() -> None:
    """Tests the SMTP server connection and login credentials."""
    # This test is disabled by default. Uncomment the call in main() to run it.
    print("\n--- Testing SMTP ---")
    server = config.SMTP_SERVER
    port = config.SMTP_PORT
    username = config.SMTP_USERNAME
    password = config.SMTP_PASSWORD

    if not all([server, port, username, password]):
        print_status("SMTP", False, "One or more SMTP environment variables are missing.")
        return

    try:
        with smtplib.SMTP(server, port, timeout=10) as connection:
            connection.starttls()
            connection.login(username, password)
        print_status("SMTP", True)
    except smtplib.SMTPAuthenticationError:
        print_status("SMTP", False, "AuthenticationError. Check username/password (or app password).")
    except Exception as e:
        print_status("SMTP", False, f"An unexpected error occurred: {e}")

# --- Main Execution ---
def main() -> None:
    """Runs all connection tests."""
    print("--- 🔑 ArtNarrator API Connection Tester ---")
    test_openai()
    test_google_gemini()
    test_sellbrite()
    # test_smtp() # Uncomment this line if you need to test the SMTP connection
    print("\n--- ✅ All tests complete ---")

if __name__ == "__main__":
    main()

---
## scripts/test_sellbrite_add_listing.py
---
"""
Sellbrite Add Listing Test Script
This utility posts a test product to Sellbrite using credentials from config.py and a sample JSON input.
Run this as a CLI script or from VSCode to verify the integration works.

Robbie Mode™ – Stable, Deterministic, and Logged.
"""

"""
Sellbrite Add Listing Test Script
"""

import sys
from pathlib import Path

# --- Ensure project root is in sys.path ---
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import json
import logging
import requests
from dotenv import load_dotenv
from config import (
    SELLBRITE_ACCOUNT_TOKEN,
    SELLBRITE_SECRET_KEY,
    SELLBRITE_API_BASE_URL,
    DATA_DIR,
    LOGS_DIR,
)

# -----------------------------------------------------------------------------
# 1. Setup & Constants
# -----------------------------------------------------------------------------
load_dotenv()
TEST_JSON_PATH = DATA_DIR / "sellbrite" / "test_sellbrite_listing.json"
RESPONSE_LOG_PATH = LOGS_DIR / "sellbrite_test_response.json"
API_ENDPOINT = f"{SELLBRITE_API_BASE_URL}/products"

# -----------------------------------------------------------------------------
# 2. Auth Headers
# -----------------------------------------------------------------------------
def get_auth_headers() -> dict:
    if not SELLBRITE_ACCOUNT_TOKEN or not SELLBRITE_SECRET_KEY:
        raise ValueError("Sellbrite credentials are not properly set in .env or config.py")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SELLBRITE_ACCOUNT_TOKEN}",
        "X-SB-API-KEY": SELLBRITE_SECRET_KEY,
    }

# -----------------------------------------------------------------------------
# 3. Load Test Payload
# -----------------------------------------------------------------------------
def load_test_payload(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"❌ Test JSON file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# -----------------------------------------------------------------------------
# 4. Post to Sellbrite
# -----------------------------------------------------------------------------
def post_listing(payload: dict, dry_run: bool = False) -> requests.Response | None:
    if dry_run:
        print("🧪 DRY RUN: Would send this JSON to Sellbrite:")
        print(json.dumps(payload, indent=2))
        return None

    headers = get_auth_headers()
    try:
        response = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=10)
        return response
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None

# -----------------------------------------------------------------------------
# 5. Main CLI Logic
# -----------------------------------------------------------------------------
def main():
    dry_run = "--dry-run" in sys.argv
    print("🚀 Sellbrite Listing Test Started...")

    try:
        payload = load_test_payload(TEST_JSON_PATH)
    except Exception as e:
        print(f"❌ Failed to load test payload: {e}")
        return

    response = post_listing(payload, dry_run=dry_run)

    if response is None:
        return

    if response.status_code == 201:
        print("✅ Listing successfully created in Sellbrite.")
    else:
        print(f"❌ Failed with status {response.status_code}: {response.text}")

    try:
        with open(RESPONSE_LOG_PATH, "w", encoding="utf-8") as log_file:
            json.dump(response.json(), log_file, indent=2)
            print(f"📝 Response saved to: {RESPONSE_LOG_PATH}")
    except Exception as e:
        print(f"⚠️ Could not save response JSON: {e}")

# -----------------------------------------------------------------------------
# 6. Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()


---
## settings/Master-Etsy-Listing-Description-Writing-Onboarding.txt
---
🥇 Robin Custance Etsy Listing Writing – Master Instructions (2025)

PURPOSE:
Generate unique, professional, search-optimised artwork listings for Aboriginal and Australian digital art, to be sold as high-resolution digital downloads on Etsy and other platforms. YOUR OUTPUT WILL BE AUTOMATICALLY PROCESSED BY ROBOTIC SYSTEMS—STRICTLY FOLLOW THE STRUCTURE AND INSTRUCTIONS BELOW.

1. OVERVIEW
- You are acting as a renowned art curator and professional art writer.
- You will write artwork listings (description, tags, materials, SEO filename, price, sku, etc.) for digital Aboriginal/Australian art by Robin Custance (Robbie) for use on Etsy and Sellbrite.
- Each listing must be unique, Pulitzer-quality, SEO-rich, and tailored to the specific artwork—never formulaic, never generic.

2. INPUTS
- The original filename is provided for reference only (for admin/tracking). NEVER use the filename for any creative or descriptive content.
- Artwork visual and cues will be provided; describe only what is seen, felt, and artistically relevant.

3. FINAL OUTPUT FORMAT (REQUIRED FIELDS & ORDER)
Output MUST be a single, valid JSON object with these EXACT keys and no others:
- seo_filename
- title
- description
- tags
- materials
- primary_colour
- secondary_colour
- price
- sku

**IMPORTANT: Every key MUST be present in every output. Even if you must estimate, guess, or repeat, NEVER omit a field. Output ONLY the JSON object—NO markdown, HTML, headings, or extra text.**

—Field details—

- **seo_filename**:  
  - Max 70 characters, ends with: "Artwork-by-Robin-Custance-RJC-XXXX.jpg" (replace XXXX with SKU or sequential number)
  - Begins with 2–3 hyphenated words from the artwork’s title (subject or style), never blindly copied from the original file name and never padded or generic
  - No fluff, no filler

- **title**:  
  - Max 140 characters
  - Must strongly reflect: "High Resolution", "Digital", "Download", "Artwork by Robin Custance"
  - Include powerful buyer search terms: "Dot Art", "Aboriginal Print", "Australian Wall Art", "Instant Download", "Printable", etc.
  - First 20 words MUST be strong search terms and clearly describe subject—**no poetic intros, no “Immerse,” “Step into,” “Discover” etc.**

- **description**:  
  - At least 400 words, or at lease 2,600 characters, Pulitzer Prize winning quality, visually and artistically accurate
  - Paragraphs must be no more than 70 words or 400 characters for readability.
  - **First 20 words MUST ONLY contain actual search terms and keyword phrases buyers use for art like this.** Write these as a smooth, natural sentence, not a list or poetic intro. Examples: “Australian outback wall art, Aboriginal dot painting print, digital download, Robin Custance artwork” etc.
  - Must deeply analyse the artwork’s style, method, colours, textures, and inspiration. Include cultural context when appropriate.
  - Always append the generic context/technique block from this onboarding file, separated by two newlines for clear paragraph breaks.
  - NO padding, no shop info, no printing instructions, no artist bio—these are handled elsewhere.

- **tags**:  
  - Array of up to 13 targeted, comma-free tags (max 20 chars/tag), highly relevant to the artwork. Rotate and tailor for each listing.
  - Mix art technique, subject, Australian/Aboriginal terms, branding, and digital wall art keywords.
  - No hyphens, no duplicates, no generic filler.

- **materials**:  
  - Array of up to 13 phrases (max 45 chars/phrase) specific to this artwork’s technique and file type.
  - Never repeat, pad, or use generic phrases unless accurate. Rotate for every artwork.

- **primary_colour, secondary_colour**:  
  - Single-word, plain English colour names matching the two most visually dominant colours in the artwork. Must be accurate. Use image analysis or artist input if unsure.

- **price**:  
  - Must be set to **18.27** exactly (as a float or numeric string with no currency symbols).

- **sku**:
- The SKU is always assigned by the system and provided as assigned_sku for this artwork.
- You must use this exact value for the "sku" field and as the suffix in the "seo_filename" (e.g. "Artwork-by-Robin-Custance-RJC-XXXX.jpg").
- Never invent, guess, or modify the SKU—always use assigned_sku exactly as given.
- This value comes from the project's central SKU tracker and is injected automatically.
- Maximum 32 characters, only letters, numbers, and hyphens allowed.

4. STRICT OUTPUT RULES
- Output a single JSON object, in the order above.
- NO markdown, headings, notes, HTML, or extra text—**just the JSON**.
- If you are unsure about any field, estimate or generate a plausible value (never leave blank or omit).
- If you fail to include all fields or add extra text, your output will break an automated system.
- No description, title, or filename may be repeated between listings.

5. EXAMPLE OUTPUT (SHOW THIS FORMAT)
{
  "seo_filename": "Night-Seeds-Rebirth-Artwork-by-Robin-Custance-RJC-XXXX.jpg",
  "title": "High Resolution Digital Dot Art Print – Aboriginal Night Seeds Rebirth | Robin Custance Download",
  "description": "Australian dot art print, Aboriginal night sky wall decor, digital download, Robin Custance, swirling galaxy artwork... [first 20 words as real search terms] ...[minimum 400 words, then append generic context/technique block]\n\n[Generic block here]",
  "tags": [
    "dot art",
    "night sky",
    "aboriginal",
    "robin custance",
    "australian art",
    "digital print",
    "swirling stars",
    "dreamtime",
    "galaxy decor",
    "modern dot",
    "outback art",
    "starry night",
    "printable"
  ],
  "materials": [
    "High resolution JPEG",
    "Digital painting",
    "Original dot technique",
    "Layered composition",
    "Contemporary wall art file",
    "Professional digital art",
    "Printable file",
    "Precision digital artwork",
    "Gallery-quality image",
    "Modern aboriginal design",
    "Colour-rich JPEG",
    "Instant download",
    "Australian art download"
  ],
  "primary_colour": "Black",
  "secondary_colour": "Brown",
  "price": 18.27,
  "sku": "RJC-XXXX"
}

6. VALIDATION RULES (CHECK ALL BEFORE FINALISING)
- Tags: max 13, max 20 chars each, no hyphens/commas, no duplicates.
- Title: max 140 characters.
- Seo_filename: max 70 chars, correct suffix, no spaces, valid chars only.
- Materials: max 13, max 45 chars/phrase.
- Price: float 18.27, no currency symbol.
- SKU: max 32 chars, unique, matches seo_filename.
- Colours: visually accurate, one-word, plain English.
- Description: min 400 words, starts with search terms, generic block appended using two newlines.

End of Instructions


---
## static/css/404.css
---
body {
    font-family: Arial, sans-serif;
    background-color: #f8f8f8;
    color: #333;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    margin: 0;
}

/* --- Universal Content Container --- */
.container {
    max-width: 2400px;
    width: 100%;
    margin: 0 auto;
    padding: 2.5rem 2rem;
    box-sizing: border-box;
}
@media (max-width: 1800px) {
    .container { max-width: 98vw; }
}
@media (max-width: 1400px) {
    .container { max-width: 99vw; }
}
@media (max-width: 1000px) {
    .container { padding: 1.8rem 1rem; }
}
@media (max-width: 700px) {
    .container { padding: 1.2rem 0.5rem; }
}
h1 {
    font-size: 3em;
    color: #FF6347;
}
p {
    font-size: 1.2em;
    color: #555;
}
a {
    font-size: 1.1em;
    color: #4682B4;
    text-decoration: none;
    margin-top: 20px;
}
a:hover {
    text-decoration: underline;
}


---
## static/css/GDWS-style.css
---
/* --- Page Layout --- */
  .gdws-container {
    display: flex;
    flex-wrap: wrap;
    gap: 2rem;
    align-items: flex-start;
  }
  .gdws-main-content {
    flex: 1;
    min-width: 60%;
  }
  .gdws-sidebar {
    width: 280px;
    position: sticky;
    top: 100px; /* Adjust if your header height changes */
    padding: 1.5rem;
    background-color: var(--color-card-bg);
    border: 1px solid var(--card-border);
  }
  .gdws-sidebar h3 {
    margin-top: 0;
    text-align: center;
    margin-bottom: 1.5rem;
  }
  .gdws-sidebar button {
    width: 100%;
    margin-bottom: 1rem;
  }

  /* --- Block Styles --- */
  .paragraph-block { background-color: var(--color-card-bg); border: 1px solid var(--card-border); padding: 1.5rem; margin-bottom: 1.5rem; cursor: grab; }
  .paragraph-block:active { cursor: grabbing; }
  .paragraph-block h3, .paragraph-block .block-title { margin-top: 0; font-size: 1.2em; }
  .paragraph-block .block-title { width: 100%; padding: 0.5rem; border: 1px solid transparent; background-color: transparent; font-family: inherit; font-weight: bold; }
  .paragraph-block .block-title:focus { border-color: var(--card-border); background-color: var(--color-background); }
  .paragraph-block textarea { width: 100%; min-height: 150px; background-color: var(--color-background); color: var(--color-text); border: 1px solid var(--card-border); padding: 0.5rem; }
  .block-actions { margin-top: 1rem; display: flex; gap: 1rem; justify-content: space-between; align-items: center; flex-wrap: wrap; }
  .title-actions { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
  .btn-regenerate-title { font-size: 0.8em; padding: 0.3em 0.6em; min-width: auto; }
  .sortable-ghost { opacity: 0.4; background: #888; border: 2px dashed var(--color-accent); } /* Style for drag placeholder */
  .pinned { background-color: #f0f0f0; border-left: 4px solid #007bff; cursor: not-allowed; }
  .theme-dark .pinned { background-color: #2a2a2a; border-left-color: #4e9fef; }
  .instructions-modal { display: none; }

---
## static/css/art-cards.css
---
/* ========================================================
   art-cards.css – Art Cards, Galleries, Thumbnails, Previews
   Updated 2025-07-24: responsive edit listing thumbnails
   ======================================================== */

/* === Cards & Art Galleries === */
.artwork-info-card { background: #fcfcfc; border: 1.5px solid #e0e0e0; box-shadow: 0 2px 8px #0001; padding: 1.5em 2em; margin: 0 auto 1.7em auto; max-width: 570px;}
.artwork-info-card h2 { font-size: 1.21em; font-weight: bold; margin-bottom: 0.6em; }
.gallery-section { margin: 2.5em auto 3.5em auto; max-width: 1250px; padding: 0 1em;}
.artwork-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2.4em; margin-bottom: 2em;}
.gallery-card { position: relative; background: var(--card-bg); border: 1px solid var(--card-border, #000); box-shadow: var(--shadow); display: flex; flex-direction: column; align-items: center; transition: box-shadow 0.18s, transform 0.12s; min-height: 365px; padding: 10px; overflow: hidden;}
.gallery-card:hover { box-shadow: 0 4px 16px #0002; transform: translateY(-4px) scale(1.013);}
.card-thumb { width: 100%; background: none; text-align: center; padding: 22px 0 7px 0; }
.card-img-top { max-width: 94%; max-height: 210px; object-fit: cover; box-shadow: 0 1px 7px #0001; background: #fafafa;}
.card-details { flex: 1 1 auto; width: 100%; text-align: center; padding: 12px 13px 20px 13px; display: flex; flex-direction: column; gap: 10px;}
.card-title { font-size: 0.9em; font-weight: 400; line-height: 1.2; color: var(--main-txt); min-height: 3em; margin-bottom: 7px;}
.card-details .btn { margin-top: 7px; width: 90%; min-width: 90px;}
.finalised-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.6em; margin-top: 1.5em; justify-content: center;}
.final-card { background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow); padding: 10px; display: flex; flex-direction: column; max-width: 350px; margin: 0 auto;}
.final-actions, .edit-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: auto;}
.edit-actions { margin-top: 1em;}
.final-actions .btn, .edit-actions .btn { flex: 1 1 auto; min-width: 100px; width: auto; margin-top: 0; }
.desc-snippet { font-size: 0.92em; line-height: 1.3; margin: 4px 0 8px 0; }
.finalised-badge { font-size: 0.9em; color: #d40000; align-self: center; padding: 4px 8px; }
.locked-badge { font-size: 0.9em; color: #0066aa; padding: 2px 6px; border: 1px solid #0066aa; margin-left: 6px;}
.main-artwork-thumb {
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
  display: block;
  margin: 0 auto 0.6em auto;
  border-radius: 6px;
  box-shadow: 0 2px 12px #0002;
}

.mockup-preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}
.mockup-card {
  background: #fff;
  box-shadow: 0 2px 10px #0001;
  padding: 11px 7px;
  text-align: center;
  border: 1px solid var(--card-border);
  border-radius: 4px;
  transition: box-shadow 0.15s;
}
.mockup-card:hover {
  box-shadow: 0 4px 14px #0002;
}

.mockup-thumb-img {
  width: 100%;
  height: 225px;
  object-fit: contain;
  border: 1px solid #eee;
  box-shadow: 0 1px 6px rgba(0,0,0,0.09);
  background: #fafafa;
  cursor: pointer;
  transition: box-shadow 0.15s;
}
.mockup-thumb-img:focus { outline: 2.5px solid var(--accent);}
.mockup-number { font-size: 0.96em; margin-bottom: 6px;}
.missing-img { width: 100%; padding: 20px 0; background: #eee; color: #777; font-size: 0.9em;}
.mini-mockup-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-top: 6px;}
.mini-mockup-grid img { width: 100%; max-height: 120px; object-fit: contain; border-radius: 4px; box-shadow: 0 1px 4px #0001;}
.mockup-thumb-img.selected, .card-img-top.selected, .gallery-thumb.selected { outline: 3px solid #e76a25 !important; outline-offset: 1.5px; }

/* Overlay for per-card progress */
.card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}
.theme-dark .card-overlay { background: rgba(0, 0, 0, 0.65); color: #fff; }
.card-overlay.hidden { display: none; }
.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid #ccc;
  border-top-color: #333;
  border-radius: 50%;
  margin-right: 8px;
  animation: spin 0.8s linear infinite;
}

.category-badge.uncategorised {
  color: #e10000; /* A strong red color */
  font-weight: bold;
}

.theme-dark .category-badge.uncategorised {
  color: #ff5c5c; /* A lighter red for dark mode */
}

@keyframes spin { to { transform: rotate(360deg); } }
.status-icon {
  position: absolute;
  top: 6px;
  right: 8px;
  font-size: 1.4em;
}

/* Gallery view toggles */
.view-toggle { margin-top: 0.5em;}
.view-toggle button { margin-right: 0.5em;}
.finalised-grid.list-view { display: block; }
.finalised-grid.list-view .final-card { flex-direction: row; max-width: none; margin-bottom: 1em;}
.finalised-grid.list-view .card-thumb { width: 150px; margin-right: 1em; }

/* Responsive Art Cards */
@media (max-width: 900px) {
  .artwork-grid { gap: 1.3em; }
  .card-thumb { padding: 12px 0 4px 0;}
  .card-title { font-size: 1em; }
  .finalised-grid { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
}
@media (max-width: 800px) {
  .main-artwork-thumb { max-height: 50vh; }
  .mockup-preview-grid {
    grid-template-columns: repeat(auto-fill, minmax(45%, 1fr));
    gap: 12px;
  }
  .mockup-card { width: 100%; }
  .mini-mockup-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 500px) {
  .mockup-preview-grid {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 10px;
  }
}

---
## static/css/buttons.css
---
/* ========================================================
   buttons.css – All Buttons, Workflow Buttons & Actions
   Monochrome, strong hover, square corners, theme aware
   ======================================================== */

/* ========================================================
   Theme Variables for Buttons (Place in your root CSS file)
   ======================================================== */

:root {
  --btn-primary-bg: #111111;
  --btn-primary-text: #ffffff;
  --btn-primary-hover-bg: #ffffff;
  --btn-primary-hover-text: #111111;
  --btn-primary-hover-shadow: 0 0 0 3px #1112;

  --btn-secondary-bg: #f5f5f5;
  --btn-secondary-text: #111111;
  --btn-secondary-hover-bg: #111111;
  --btn-secondary-hover-text: #ffffff;
  --btn-secondary-hover-shadow: 0 0 0 3px #3332;

  --btn-danger-bg: #444444;
  --btn-danger-text: #ffffff;
  --btn-danger-hover-bg: #ffffff;
  --btn-danger-hover-text: #c8252d;
  --btn-danger-hover-shadow: 0 0 0 3px #c8252d44;

  --btn-disabled-bg: #bbbbbb;
  --btn-disabled-text: #eeeeee;

  --btn-workflow-bg: #ededed;
  --btn-workflow-text: #1a1a1a;
  --btn-workflow-hover-bg: #222222;
  --btn-workflow-hover-text: #ffffff;
  --btn-workflow-hover-shadow: 0 0 0 3px #2222;
  --btn-workflow-border: #bbbbbb;
}

.theme-dark {
  --btn-primary-bg: #ffffff;
  --btn-primary-text: #111111;
  --btn-primary-hover-bg: #111111;
  --btn-primary-hover-text: #ffffff;
  --btn-primary-hover-shadow: 0 0 0 3px #fff2;

  --btn-secondary-bg: #222222;
  --btn-secondary-text: #ffffff;
  --btn-secondary-hover-bg: #ffffff;
  --btn-secondary-hover-text: #222222;
  --btn-secondary-hover-shadow: 0 0 0 3px #fff2;

  --btn-danger-bg: #888888;
  --btn-danger-text: #ffffff;
  --btn-danger-hover-bg: #ffffff;
  --btn-danger-hover-text: #c8252d;
  --btn-danger-hover-shadow: 0 0 0 3px #c8252d44;

  --btn-disabled-bg: #444444;
  --btn-disabled-text: #bbbbbb;

  --btn-workflow-bg: #1a1a1a;
  --btn-workflow-text: #ffffff;
  --btn-workflow-hover-bg: #ffffff;
  --btn-workflow-hover-text: #111111;
  --btn-workflow-hover-shadow: 0 0 0 3px #fff2;
  --btn-workflow-border: #444444;
}

/* ========================================================
   Base Button Styles (Square Corners, Strong Contrast)
   ======================================================== */

.btn,
.btn-primary,
.btn-secondary,
.btn-danger,
.btn-sm,
.wide-btn,
.upload-btn-large,
.art-btn {
  font-family: var(--font-primary, monospace);
  border: none;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, box-shadow 0.12s, outline 0.12s;
  display: inline-block;
  text-align: center;
  text-decoration: none;
  outline: none;
  font-size: 1em;
  border-radius: 0;
  min-width: 120px;
  box-shadow: 0 1px 5px 0 #1111;
}

.btn, .btn-primary, .btn-secondary, .btn-danger {
  width: 90%;
  margin: 10px auto;
  padding: .55em 1.3em;
  font-size: 18px;
  align-self: center;
  font-weight: 600;
}

.btn-sm { font-size: 0.96em; padding: 0.45em 1em; }
.wide-btn { width: 100%; font-size: 1.12em; font-weight: bold; padding: 1em 0; }

/* ========================================================
   Button Types
   ======================================================== */

/* -- Primary Button -- */
.btn-primary, .btn:not(.btn-secondary):not(.btn-danger) {
  background: var(--btn-primary-bg);
  color: var(--btn-primary-text);
}
.btn-primary:hover, .btn-primary:focus,
.btn:not(.btn-secondary):not(.btn-danger):hover,
.btn:not(.btn-secondary):not(.btn-danger):focus {
  background: var(--btn-primary-hover-bg);
  color: var(--btn-primary-hover-text);
  box-shadow: var(--btn-primary-hover-shadow);
  outline: 2px solid var(--btn-primary-hover-bg);
}

/* -- Secondary Button -- */
.btn-secondary {
  background: var(--btn-secondary-bg);
  color: var(--btn-secondary-text);
  border: 1.2px solid var(--btn-workflow-border, #bbbbbb);
}
.btn-secondary:hover,
.btn-secondary:focus {
  background: var(--btn-secondary-hover-bg);
  color: var(--btn-secondary-hover-text);
  border-color: #111111;
  box-shadow: var(--btn-secondary-hover-shadow);
  outline: 2px solid var(--btn-secondary-hover-bg);
}

/* -- Danger Button -- */
.btn-danger {
  background: var(--btn-danger-bg);
  color: var(--btn-danger-text);
}
.btn-danger:hover, .btn-danger:focus {
  background: var(--btn-danger-hover-bg);
  color: var(--btn-danger-hover-text);
  box-shadow: var(--btn-danger-hover-shadow);
  outline: 2px solid #c8252d;
}

/* -- Disabled State -- */
.btn:disabled,
button:disabled,
.btn.disabled,
.btn-primary:disabled,
.btn-secondary:disabled,
.btn-danger:disabled {
  background: var(--btn-disabled-bg);
  color: var(--btn-disabled-text);
  cursor: not-allowed;
  opacity: 0.62;
  filter: grayscale(35%);
  box-shadow: none;
  outline: none;
}

/* -- Active State (All) -- */
.btn:active, .btn-primary:active, .btn-secondary:active, .btn-danger:active {
  filter: brightness(0.96) saturate(110%);
}

/* ========================================================
   Workflow Buttons (Solid & Card, Square Corners)
   ======================================================== */

.workflow-btn {
  font-family: var(--font-primary, monospace);
  display: flex;
  align-items: center;
  justify-content: flex-start;
  font-size: 1.11em;
  font-weight: 600;
  padding: 18px 32px;
  background: var(--btn-workflow-bg);
  color: var(--btn-workflow-text);
  border: 1.2px solid var(--btn-workflow-border, #bbbbbb);
  border-radius: 0;
  min-width: 220px;
  margin: 0 16px 0 0;
  transition: background 0.15s, color 0.15s, box-shadow 0.12s, outline 0.12s;
}
.workflow-btn:hover:not(.disabled),
.workflow-btn:focus:not(.disabled) {
  background: var(--btn-workflow-hover-bg);
  color: var(--btn-workflow-hover-text);
  border-color: #111111;
  box-shadow: var(--btn-workflow-hover-shadow);
  outline: 2px solid var(--btn-workflow-hover-bg);
}
.workflow-btn.disabled,
.workflow-btn[disabled] {
  background: var(--btn-disabled-bg);
  color: var(--btn-disabled-text);
  pointer-events: none;
  opacity: 0.65;
  filter: grayscale(0.35);
  outline: none;
}

/* Card-style for workflow row */
.workflow-row {
  display: flex;
  flex-wrap: wrap;
  gap: 2rem;
  justify-content: center;
  align-items: stretch;
  margin: 2.5rem 0 3rem 0;
}
.workflow-row .workflow-btn {
  flex: 1 1 200px;
  flex-direction: column;
  gap: 1.2rem;
  font-size: 1.06em;
  text-align: center;
  min-width: 180px;
  max-width: 270px;
  padding: 1.7em 1.2em 1.5em 1.2em;
  box-shadow: 0 2px 10px 0 #1111;
  margin: 0;
  border-radius: 0;
}

/* Responsive Buttons */
@media (max-width: 1200px) {
  .workflow-row { gap: 1.2rem; }
  .workflow-row .workflow-btn { font-size: 1em; min-width: 130px; max-width: 210px; padding: 1em 0.8em; }
}
@media (max-width: 800px) {
  .workflow-row { gap: 0.7rem; }
  .workflow-row .workflow-btn { font-size: 0.95em; min-width: 45vw; max-width: 95vw; padding: 0.9em 0.5em 1em 0.5em; margin-bottom: 0.5em; }
}
@media (max-width: 500px) {
  .workflow-row { flex-direction: column; gap: 0.5rem; }
  .workflow-row .workflow-btn { min-width: 98vw; max-width: 100vw; padding: 0.6em 0.2em 0.8em 0.2em; font-size: 0.88em;}
}

/* ========================================================
   Art Actions/Rows
   ======================================================== */
.button-row, .final-actions, .edit-actions {
  display: flex; justify-content: center; align-items: center;
  gap: 10px; margin-top: 20px; flex-wrap: wrap;
}
.button-row form, .final-actions form, .edit-actions form { margin: 0; }
.art-btn {
  font-weight: 500; height: var(--button-height, 48px); min-width: 100px;
  border-radius: 0;
  font-size: 1em; display: flex; align-items: center; justify-content: center;
  background: var(--btn-secondary-bg);
  color: var(--btn-secondary-text);
  border: 1.2px solid var(--btn-workflow-border, #bbbbbb);
  transition: background 0.13s, color 0.13s, border 0.13s, outline 0.13s;
}
.art-btn:not(:disabled):hover,
.art-btn:not(:disabled):focus {
  background: var(--btn-secondary-hover-bg);
  color: var(--btn-secondary-hover-text);
  border-color: #111111;
  box-shadow: var(--btn-secondary-hover-shadow);
  outline: 2px solid var(--btn-secondary-hover-bg);
}
.art-btn.delete,
.art-btn.delete:not(:disabled):hover {
  background: var(--btn-danger-bg);
  color: var(--btn-danger-text) !important;
  border: none;
}
.art-btn:disabled, .art-btn.disabled {
  background: var(--btn-disabled-bg); color: var(--btn-disabled-text);
  cursor: not-allowed; border: none; outline: none;
}

/* --- End of File --- */


---
## static/css/documentation.css
---


---
## static/css/icons.css
---
/* ========================================================
   icons.css – All icon styles and theme filters
   Applies color inversion for icons in dark theme.
   ======================================================== */

.site-logo {
  font-weight: 400;
  font-size: 1.3rem;
  letter-spacing: 0.5px;
}

.logo-icon,
.narrator-icon {
  width: 35px;
  height: 35px;
  margin-right: 6px;
  vertical-align: bottom;
}

.narrator-icon {
  width: 50px;
  margin-bottom: 5px;
}

.artnarrator-logo {
  width: 100px;
  margin: 0px 8px 5px 0px;
  vertical-align: bottom;
}

/* Workflow and hero icons */
.step-btn-icon {
  width: 35px;
  height: 35px;
  margin-right: 12px;
  display: inline-block;
}

.hero-step-icon {
  width: 50px;
  height: 50px;
  margin-right: 10px;
  display: inline-block;
  margin-bottom: 5px;
  vertical-align: bottom;
  color:var(--color-text);
}

.progress-icon {
  width: 48px;
  display: block;
  margin: 0 auto 0.8em auto;
}

/* Theme toggle icons */
.sun-icon { display: block; }
.moon-icon { display: none; }
.theme-dark .sun-icon { display: none; }
.theme-dark .moon-icon { display: block; }

/* Global icon colour inversion */
.theme-dark img.icon,
.theme-dark svg.icon,
.theme-dark .logo-icon,
.theme-dark .hero-step-icon,
.theme-dark .step-btn-icon {
  filter: invert(1) grayscale(1) brightness(1.3);
}
.theme-light img.icon,
.theme-light svg.icon,
.theme-light .logo-icon,
.theme-light .hero-step-icon,
.theme-light .step-btn-icon {
  filter: none;
}

/* Responsive icon sizing for workflow buttons */
@media (max-width: 1200px) {
  .workflow-row .step-btn-icon { width: 2em; height: 2em; }
}
@media (max-width: 800px) {
  .workflow-row .step-btn-icon { width: 1.5em; height: 1.5em; }
}
@media (max-width: 500px) {
  .workflow-row .step-btn-icon { width: 1.2em; height: 1.2em; }
}


---
## static/css/layout.css
---
/* ========================================================
   layout.css – Layout, Grids, Columns, Structure
   Uses --header-bg variable for theme-aware headers.
   ======================================================== */

/* === Layout Grids, Columns & Rows === */
.review-artwork-grid, .row { display: flex; flex-wrap: wrap; gap: 2.5rem; align-items: flex-start; width: 100%; }
.exports-special-grid { display: grid; grid-template-columns: 1fr 1.7fr; gap: 2em; margin: 2em 0; }
.page-title-row { display: flex; align-items: center; gap: 20px; margin-bottom: 40px; }
.page-title-large { font-size: 2.15em; font-weight: bold; text-align: center; margin: 1.4em 0 0.7em 0; }
.mockup-col { flex: 1 1 0; min-width: 340px; max-width: 540px; display: block; }
.edit-listing-col { width: 100%; }
.price-sku-row, .row-inline { display: flex; gap: 1em; }
.price-sku-row > div, .row-inline > div { flex: 1; }

/* === Responsive Grids === */
@media (max-width: 900px) {
  .page-title-row { flex-direction: column; text-align: center; gap: 1em; }
  .exports-special-grid { grid-template-columns: 1fr; gap: 1.1em; }
}
@media (max-width: 800px) {
  .review-artwork-grid { flex-direction: column; gap: 1.5em; }
  .mockup-col, .edit-listing-col { width: 100%; max-width: none;}
}

        /* --- Header --- */
        .site-header, .overlay-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1rem;
            width: 100%;
            background-color: var(--header-bg);
        }
        
        .site-header {
            position: sticky;
            top: 0;
            z-index: 100;
            background-color: var(--header-bg);
            transition: background-color 0.3s, color 0.3s;
            border-bottom: 1px solid var(--color-header-border);
            color: var(--color-text); /* Ensure header text/icons match theme */
        }

        .header-left, .header-right {
            flex: 1;
        }
        .header-center {
            flex-grow: 0;
        }
        .header-right {
            display: flex;
            justify-content: flex-end;
        }

        .menu-toggle-btn, .menu-close-btn {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 1rem;
            font-weight: 500;
        }

        .menu-toggle-btn svg, .menu-close-btn svg {
            width: 16px;
            height: 16px;
        }
        
        .theme-toggle-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 44px;
            height: 44px;
        }

        .theme-toggle-btn svg {
            width: 24px;
            height: 24px;
        }

        /* --- Footer --- */
        .site-footer {
            background-color: var(--color-footer-bg);
            color: var(--color-footer-text);
            height: 400px;
            display: flex;
            margin-top: 3rem;
            flex-direction: column;
            justify-content: center;
            border-top: 1px solid var(--color-footer-border);
        }

        .footer-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 2rem;
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            padding: 0 2rem;
        }

        .footer-column h4 {
            font-size: 1rem;
            margin: 20px 0 1rem 0;
            text-transform: uppercase;
            letter-spacing: 1px;
            opacity: 0.7;
        }

        .footer-column ul {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .footer-column a {
            opacity: 0.9;
            transition: opacity 0.3s;
        }
        .footer-column a:hover {
            opacity: 1;
            color: var(--color-hover);
        }

        .copyright-bar {
            padding: 1rem 2rem;
            text-align: center;
            font-size: 0.8rem;
            margin-top: auto; /* Pushes to the bottom of the flex container */
        }
         
/* --- Upload Dropzone --- */
.upload-dropzone {
  border: var(--border-2);
  padding: var(--space-6);
  text-align: center;
  cursor: pointer;
  color: var(--color-semantic-text-muted);
  transition: background var(--transition-1), border-color var(--transition-1);
}
.upload-dropzone.dragover {
  border-color: var(--color-semantic-accent-primary);
  background: var(--color-semantic-bg-hover);
}
.upload-list {
  margin-top: var(--space-3);
  list-style: none;
  padding: 0;
  font-size: var(--font-size-1);
}
.upload-list li { margin: var(--space-1) 0; }
.upload-list li.success { color: var(--color-semantic-success); }
.upload-list li.error { color: var(--color-semantic-error); }
.upload-progress {
  position: relative;
  background: var(--color-semantic-bg-hover);
  height: var(--space-2);
  margin: var(--space-1) 0;
  width: 100%;
  overflow: hidden;
}
.upload-progress-bar {
  background: var(--color-semantic-accent-primary);
  height: 100%;
  width: 0;
  transition: width 0.2s;
}
.home-hero { margin: 2em auto 2.5em auto; text-align: center; }

/* ===============================
   [ Upload Dropzone ]
   =============================== */
.upload-dropzone {
  border: 2px dashed #bbb;
  max-width: 800px;;
  width: 100%;
  margin: 20px auto;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  color: #666;
  transition: background 0.2s, border-color 0.2s;
}

.upload-dropzone:hover {
  background-color: var(--color-hover);
  color:var(--dark-color-text);
}

.upload-dropzone.dragover {
  border-color: #333;
  background: #f9f9f9;
}

.upload-list {
  margin-top: 1em;
  list-style: none;
  padding: 0;
  font-size: 0.9rem;
}
.upload-list li {
  margin: 0.2em 0;
}
.upload-list li.success { color: green; }
.upload-list li.error { color: red; }

.upload-progress {
  position: relative;
  background: #eee;
  height: 8px;
  margin: 2px 0;
  width: 100%;
  overflow: hidden;
}
.upload-progress-bar {
  background: var(--accent);
  height: 100%;
  width: 0;
  transition: width 0.2s;
}
.upload-percent {
  margin-left: 4px;
  font-size: 0.8em;
}

/* ===============================
   [ Edit Artwork Listing Page ]
   =============================== */
/* --- Edit Action Buttons Area --- */
.edit-listing-col {
  width: 100%;
}

.long-field {
  width: 100%;
  box-sizing: border-box;
  font-size: 1.05em;
  padding: 0.6em;
  margin-bottom: 1em;
  border-radius: 0 !important;   /* FORCE SQUARE */
}

.price-sku-row,
.row-inline {
  display: flex;
  gap: 1em;
}
.price-sku-row > div,
.row-inline > div {
  flex: 1;
}

.edit-actions-col {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.7em;
  margin: 2em 0 0 0;
  width: 100%;
}

.wide-btn {
  width: 100%;
  font-size: 1.12em;
  font-weight: bold;
  padding: 1em 0;
  border-radius: 0 !important;   /* FORCE SQUARE */
}

/* ===== Simple Flexbox Grid System for ArtNarrator ===== */
.row, .review-artwork-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 2.5rem;
  align-items: flex-start;
  width: 100%;
}

.col {
  flex: 1 1 0;
  min-width: 0;
}

.col-6 {
  flex: 0 0 48%;
  max-width: 48%;
  min-width: 340px;  /* optional: keep cards from going too small */
  box-sizing: border-box;
}

.status-line {margin-top:0px}

/* Responsive: Stack columns on small screens */
@media (max-width: 1100px) {
  .col-6 {
    flex: 0 0 100%;
    max-width: 100%;
    min-width: 0;
    margin-bottom: 2rem;
  }
  .review-artwork-grid {
    gap: 1.2rem;
  }
}

/* For older .row usage (legacy) */
@media (max-width: 700px) {
  .row, .review-artwork-grid {
    flex-direction: column;
    gap: 1rem;
  }
  .price-sku-row,
  .row-inline {
    flex-direction: column;
    gap: 0.5em;
  }
}

/* ===== Responsive Mockup Thumbnails ===== */
/* Moved detailed sizing rules to art-cards.css */

@media (min-width: 1400px) {
.home-content-grid {
    max-width: 1400px;
}
}

@media (min-width: 1600px) {
.home-content-grid {
    max-width: 1600px;
}
}

@media (min-width: 1800px) {
.home-content-grid {
    max-width: 1800px;
}
}

@media (min-width: 2400px) {
.home-content-grid {
    max-width: 2400px;
}
}

@keyframes spin {
0% { transform: rotate(0deg); }
100% { transform: rotate(360deg); }
}

/* ===============================
   [ OpenAI Details Table ]
   =============================== */
.openai-details table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 2em;
  font-size: 0.8em;    /* smaller for both columns */
  table-layout: fixed;
}

.openai-details th,
.openai-details td {
  padding-bottom: 0.35em;
  vertical-align: top;
  word-break: break-word;
}

/* Make the first column (labels) nice and wide, second takes rest */
.openai-details th {
  width: 105px;    /* adjust as needed for your headings */
  min-width: 95px;
  font-weight: 600;
  text-align: left;
  font-size: 0.8em;
  white-space: nowrap;   /* keep all on one line */
  padding-bottom: 10px;
  padding-right: 1em;
}

.openai-details td {
  font-size: 0.8em;
}

@media (max-width: 650px) {
  .openai-details th {
    width: 110px;
    min-width: 90px;
    font-size: 0.8em;
  }
  .openai-details td {
    font-size: 0.8em;
  }
}

.openai-details table tr:nth-child(even) {
  background: #f2f2f2;
}

.openai-details th,
.openai-details td {
  padding: 0.33em 0.6em 0.33em 0.3em;
}

---
## static/css/main.css
---
@import url('style.css');
@import url('icons.css');
@import url('layout.css');
@import url('buttons.css');
@import url('art-cards.css');
@import url('overlay-menu.css');
@import url('modals-popups.css');
@import url('GDWS-style.css');
@import url('documentation.css');



---
## static/css/modals-popups.css
---
/* ========================================================
   modals-popups.css – Modals, Popups, Alerts, Carousels
   Added theme-aware table rows and select dropdown styles.
   ======================================================== */

/* --- Modals & Carousel --- */
.analysis-modal,
.modal-bg {
  display: none; position: fixed; z-index: var(--z-modal, 99);
  left: 0; top: 0; width: 100vw; height: 100vh;
  background: rgba(0, 0, 0, 0.65);
  align-items: center; justify-content: center;
}
.analysis-modal.active,
.modal-bg.active { display: flex !important; }
.analysis-box {
  background: var(--color-semantic-bg-primary);
  border: var(--border-1);
  padding: var(--space-4);
  max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto;
}
.analysis-log {
  font-family: var(--font-1); background: var(--color-semantic-bg-hover);
  border: var(--border-1); padding: var(--space-2);
  max-height: 60vh; overflow-y: auto; white-space: pre-wrap; font-size: var(--font-size-1);
}
.modal-img { background: transparent !important; padding: 0 !important; max-width: 94vw; max-height: 93vh; box-shadow: 0 5px 26px rgba(0,0,0,0.22);}
.modal-img img { max-width: 88vw; max-height: 80vh; display: block;}
.modal-close {
  position: absolute; top: 2.3vh; right: 2.6vw;
  font-size: 2em; color: var(--color-btn-text, #fff); background: none;
  border: none; cursor: pointer; z-index: 101; text-shadow: 0 2px 6px #000;
}
.carousel-nav {
  position: absolute; top: 50%; transform: translateY(-50%);
  background: none; border: none; font-size: 2.5em; cursor: pointer; padding: 0 0.2em; color: #888; transition: color 0.2s;
}
body.dark-theme .carousel-nav { color: #fff;}
.carousel-nav:hover { color: #e76a25 !important;}
#carousel-prev { left: 1vw;}
#carousel-next { right: 1vw;}

/* --- Alerts & Flash --- */
.alert-info, .template-info-msg {
  background: #f4faff; color: #3b4051; border-left: 5px solid #8ac6ff; padding: 1.1em 1.3em; font-size: 1em; margin-bottom: 1.4em;
}
.template-error-msg { color: #c8252d; font-weight: bold; font-size: 1.1em; margin-bottom: 1.4em; font-family: monospace, monospace !important;}
.flash, .flash-error {
  background: #fbeaea; color: #a60000; border: 1px solid #f5b5b5; border-left: 5px solid #e10000; padding: 1em 1.4em; margin-bottom: 1.5em;
}
.flash ul { margin: 0; padding-left: 1.2em; }

        /* --- Gemini Modal --- */
        .gemini-modal {
            position: fixed;
            z-index: 1001;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            overflow: auto;
            background-color: rgba(0,0,0,0.5);
            display: none;
            align-items: center;
            justify-content: center;
        }

        .gemini-modal-content {
            background-color: var(--color-background);
            color: var(--color-text);
            margin: auto;
            padding: 2rem;
            border: 1px solid #888;
            width: 80%;
            max-width: 600px;
            position: relative;
        }
        
        .gemini-modal-close {
            position: absolute;
            top: 1rem;
            right: 1.5rem;
            font-size: 1.5rem;
            font-weight: bold;
            cursor: pointer;
        }

        .gemini-modal-body textarea {
            width: 100%;
            min-height: 200px;
            margin-top: 1rem;
            background-color: var(--color-card-bg);
            color: var(--color-text);
            border: 1px solid var(--color-header-border);
            padding: 0.5rem;
        }
        
        .gemini-modal-actions {
            margin-top: 1rem;
            display: flex;
            gap: 1rem;
        }

        .loader {
            border: 4px solid #f3f3f3;
            border-radius: 50%;
            border-top: 4px solid var(--color-hover);
            width: 40px;
            height: 40px;
            animation: spin 2s linear infinite;
            margin: 2rem auto;
        }

/* --- OpenAI Analysis Table --- */
.openai-analysis-table {
  width: 100%;
  border-collapse: collapse;
  font-family: monospace;
  font-size: 1em;
}
.openai-analysis-table th,
.openai-analysis-table td {
  padding: 0.6em 0.8em;
  border: 1px solid var(--card-border);
}
.openai-analysis-table thead th {
  background: var(--table-row-alt-bg);
  font-weight: bold;
  text-align: left;
}
.openai-analysis-table tbody th {
  font-weight: bold;
  text-align: left;
  min-width: 160px;
  white-space: nowrap;
}
.openai-analysis-table tbody tr:nth-child(odd) {
  background: var(--table-row-bg);
}
.openai-analysis-table tbody tr:nth-child(even) {
  background: var(--table-row-alt-bg);
}
@media (max-width: 600px) {
  .openai-analysis-table {
    display: block;
    overflow-x: auto;
  }
  .openai-analysis-table tbody,
  .openai-analysis-table tr,
  .openai-analysis-table th,
  .openai-analysis-table td {
    white-space: nowrap;
  }
}

/* --- Dropdown & Select --- */
select {
  appearance: none;
  background-color: var(--color-card-bg);
  color: var(--color-text);
  border: 1px solid var(--card-border);
  padding: 0.4em 2.2em 0.4em 0.6em;
  border-radius: 4px;
  background-image: linear-gradient(45deg, transparent 50%, currentColor 50%),
    linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-position: right 0.6em top 50%, right 0.3em top 50%;
  background-size: 0.5em 0.5em;
  background-repeat: no-repeat;
}
select:focus {
  outline: none;
  border-color: var(--color-hover);
  box-shadow: 0 0 0 2px rgba(0,0,0,0.15);
}

/* --------- [ Analysis Progress Modal ] --------- */
.analysis-modal {
  display: none;
  position: fixed;
  z-index: 100;
  left: 0;
  top: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0,0,0,0.65);
  align-items: center;
  justify-content: center;
}
.theme-light .analysis-modal { background: rgba(255,255,255,0.6); }
.theme-dark .analysis-modal { background: rgba(0,0,0,0.65); }
.analysis-modal.active { display: flex; }

.analysis-box {
  background: #fff;
  padding: 1.5em 1.2em;
  max-width: 400px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  font-family: monospace;
  text-align: center;
}
.theme-light .analysis-box { background: #000; color: #fff; }
.theme-dark .analysis-box { background: #fff; color: #000; }
.analysis-log {
  font-family: monospace;
  background: #fafbfc;
  border: 1px solid #ddd;
  padding: 0.6em;
  max-height: 60vh;
  overflow-y: auto;
  white-space: pre-wrap;
  font-size: 0.92em;
}
.analysis-log .log-error { color: #b00; }
.analysis-log .latest { background: #eef; }

.analysis-progress {
  background: #eee;
  height: 10px;
  margin: 0.5em 0;
  width: 100%;
}
.analysis-progress-bar {
  background: var(--accent);
  height: 100%;
  width: 0;
  transition: width 0.3s ease;
}
.analysis-status {
  font-size: 0.9em;
  margin-bottom: 0.6em;
}
.analysis-friendly {
  text-align: center;
  font-size: 0.9em;
  margin-top: 0.6em;
  font-style: italic;
}

.progress-icon {
  width: 48px;
  margin: 0 auto 0.8em auto;
  display: block;
}

---
## static/css/overlay-menu.css
---
/* ========================================================
   overlay-menu.css – Overlay Menu, Nav, Sidebar
   ======================================================== */

.overlay-menu {
  position: fixed;
  top: 0; left: 0; width: 100%; height: 100vh;
  background-color: var(--color-overlay-bg, rgba(248, 248, 248, 0.85));
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  z-index: 999;
  display: flex; flex-direction: column; padding: 0;
  opacity: 0; visibility: hidden; transform: translateY(20px);
  transition: opacity 0.5s var(--ease-quart), visibility 0.5s var(--ease-quart), transform 0.5s var(--ease-quart);
  overflow-y: auto; color: #111111;
}
.overlay-menu.is-active { opacity: 1; visibility: visible; transform: translateY(0);}
.overlay-header { flex-shrink: 0; position: sticky; top: 0; background-color: var(--color-overlay-bg);}
.overlay-nav {
  display: grid; grid-template-columns: repeat(3, 1fr);
  flex-grow: 1; padding: 4rem 2rem; gap: 2rem;
  width: 100%; max-width: 1200px; margin: 0 auto 50px auto;
}
.nav-column h3 { font-size: 1rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; opacity: 0.5; margin: 0 0 1.5rem 0;}
.nav-column ul { display: flex; flex-direction: column; gap: 1rem;}
.nav-column a { font-size: 1.2em; font-weight: 500; line-height: 1.3; display: inline-block; transition: color 0.3s var(--ease-quart);}
.nav-column a:hover { color: var(--color-hover);}
@media (max-width: 900px) {
  .overlay-nav { grid-template-columns: 1fr; justify-items: center; text-align: center; gap: 3rem; }
  .nav-column a { font-size: 1.5rem; }
}


---
## static/css/style.css
---
/* ========================================================
   style.css – Globals, Variables & Universal Container
   Defines theme-aware color variables for light and dark modes.
   ======================================================== */

:root {
  --font-primary: monospace !important;
  --color-background: #FFFFFF;
  --color-text: #111111;
  --color-card-bg: #f9f9f9;
  --color-header-border: #eeeeee;
  --color-footer-bg: #FFFFFF;
  --color-footer-text: #111111;
  --color-footer-border: #dddddd;
  --header-bg: #ffffff;
  --table-row-bg: #ffffff;
  --table-row-alt-bg: #f4f4f4;
  --dark-color-footer-bg: #181818;
  --dark-color-footer-text: #FFFFFF;
  --color-hover: #ffa52a;
  --color-danger: #c8252d;
  --color-hover-other: #000000;
  --color-accent: #e76a25;
  --color-accent-hover: #ff9933;
  --card-border: #c8c7c7;
  --workflow-icon-size: 2.1em;
  --dark-color-background: #111111;
  --dark-color-text: #FFFFFF;
  --dark-color-card-bg: #1a1a1a;
  --dark-card-border: #727272;
  --light-card-border: #727272;
}

/* Dark theme variables applied when `.theme-dark` class is present on `html` or `body` */
.theme-dark {
  --color-background: var(--dark-color-background);
  --color-text: var(--dark-color-text);
  --color-card-bg: var(--dark-color-card-bg);
  --card-border: var(--dark-card-border);
  --color-footer-bg: var(--dark-color-footer-bg);
  --color-footer-text: var(--dark-color-footer-text);
  --header-bg: #111111;
  --table-row-bg: #222222;
  --table-row-alt-bg: #333333;
}

/* === Universal Base & Reset === */
*, *::before, *::after { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  font-family: var(--font-primary);
  background-color: var(--color-background);
  color: var(--color-text);
  font-size: 16px;
  line-height: 1.6;
  transition: background-color 0.3s, color 0.3s;
  display: flex;
  flex-direction: column;
}
a, button, input, h1, h2, h3, h4, p, div { font-family: var(--font-primary); font-weight: 400; }
a { color: inherit; text-decoration: none; }
ul { list-style: none; padding: 0; margin: 0; }
button { background: none; border: none; cursor: pointer; padding: 0; color: inherit; }
main { flex-grow: 1; }

/* === Universal Content Container === */
.container {
  max-width: 2400px;
  width: 100%;
  margin: 0 auto;
  padding: .25rem 2rem 2rem 2rem;
  box-sizing: border-box;
}
@media (max-width: 1800px) { .container { max-width: 98vw; } }
@media (max-width: 1400px) { .container { max-width: 99vw; } }
@media (max-width: 1000px) { .container { padding: 1.8rem 1rem; } }
@media (max-width: 700px)  { .container { padding: 1.2rem 0.5rem; } }


---
## static/js/analysis-modal.js
---
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('analysis-modal');
  const bar = document.getElementById('analysis-bar');
  const statusEl = document.getElementById('analysis-status');
  const closeBtn = document.getElementById('analysis-close');
  const statusUrl = document.body.dataset.analysisStatusUrl;
  let pollStatus;

  function openModal(opts = {}) {
    modal.classList.add('active');
    if (opts.message) {
      statusEl.textContent = opts.message;
      bar.style.width = '0%';
    } else {
      fetchStatus();
      pollStatus = setInterval(fetchStatus, 1000);
    }
    modal.querySelector('.analysis-box').focus();
  }

  function closeModal() {
    modal.classList.remove('active');
    clearInterval(pollStatus);
  }

  function fetchStatus() {
    fetch(statusUrl)
      .then(r => r.json())
      .then(d => {
        const pct = d.percent || 0;
        bar.style.width = pct + '%';
        bar.setAttribute('aria-valuenow', pct);
        if (d.status === 'failed') {
          statusEl.textContent = 'FAILED: ' + (d.error || 'Unknown error');
          clearInterval(pollStatus);
        } else if (d.status === 'complete') {
          statusEl.textContent = 'Complete';
          clearInterval(pollStatus);
        } else {
          statusEl.textContent = d.step || 'Analyzing';
        }
      });
  }

  function setMessage(msg) {
    statusEl.textContent = msg;
  }

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  modal.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { e.preventDefault(); closeModal(); }
  });

  document.querySelectorAll('form.analyze-form').forEach(f => {
    f.addEventListener('submit', function(ev) {
      ev.preventDefault();
      openModal();
      const data = new FormData(f);
      fetch(f.action, {method: 'POST', body: data})
        .then(resp => resp.text().then(() => resp.url))
        .then(url => { setTimeout(() => { closeModal(); window.location.href = url; }, 1000); });
    });
  });
  window.AnalysisModal = { open: openModal, close: closeModal, setMessage };
});


---
## static/js/artworks.js
---
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.btn-analyze').forEach(btn => {
    btn.addEventListener('click', ev => {
      ev.preventDefault();
      const card = btn.closest('.gallery-card');
      if (!card) return;
      const provider = btn.dataset.provider;
      const filename = card.dataset.filename;
      if (!filename) return;
      runAnalyze(card, provider, filename);
    });
  });

  document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', ev => {
      ev.preventDefault();
      const card = btn.closest('.gallery-card');
      if (!card) return;
      const filename = card.dataset.filename;
      if (!filename) return;
      if (!confirm('Are you sure?')) return;
      showOverlay(card, 'Deleting…');
      fetch(`/delete/${encodeURIComponent(filename)}`, {method: 'POST'})
        .then(r => r.json())
        .then(d => {
          hideOverlay(card);
          if (d.success) {
            card.remove();
          } else {
            alert(d.error || 'Delete failed');
          }
        })
        .catch(() => { hideOverlay(card); alert('Delete failed'); });
    });
  });
});

function showOverlay(card, text) {
  let ov = card.querySelector('.card-overlay');
  if (!ov) {
    ov = document.createElement('div');
    ov.className = 'card-overlay';
    card.appendChild(ov);
  }
  ov.innerHTML = `<span class="spinner"></span> ${text}`;
  ov.classList.remove('hidden');
}

function hideOverlay(card) {
  const ov = card.querySelector('.card-overlay');
  if (ov) ov.classList.add('hidden');
}

// Request backend analysis for an artwork. If the server responds with
// an edit_url we immediately redirect the browser there. This keeps
// both XHR and non-XHR flows consistent with the Flask route.
// Trigger analysis for ``filename`` via the chosen provider. The backend may
// respond with JSON (listing data) or an image blob. Blob responses are
// displayed directly while JSON results update the card and/or redirect.
const FRIENDLY_AI_ERROR =
  'Sorry, we could not analyze this artwork due to an AI error. Please try again or switch provider.';

function runAnalyze(card, provider, filename) {
  const openaiOk = document.body.dataset.openaiOk === 'true';
  const googleOk = document.body.dataset.googleOk === 'true';
  if ((provider === 'openai' && !openaiOk) || (provider === 'google' && !googleOk)) {
    const msg = provider === 'openai' ? 'OpenAI API Key is not configured. Please contact admin.' : 'Google API Key is not configured. Please contact admin.';
    if (window.AnalysisModal) window.AnalysisModal.open({message: msg});
    return;
  }
  if (window.AnalysisModal) window.AnalysisModal.open();
  showOverlay(card, `Analyzing with ${provider}…`);
  fetch(`/analyze-${provider}/${encodeURIComponent(filename)}`, {
    method: 'POST',
    headers: {'X-Requested-With': 'XMLHttpRequest'}
  })
    .then(async r => {
      const type = r.headers.get('Content-Type') || '';
      if (!r.ok) {
        let msg = 'HTTP ' + r.status;
        if (type.includes('application/json')) {
          try { const j = await r.json(); msg = j.error || msg; } catch {}
        }
        throw new Error(msg);
      }
      if (type.startsWith('image/')) {
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const img = card.querySelector('.card-img-top');
        if (img) img.src = url;
        return {success: true};
      }
      return r.json();
    })
    .then(d => {
      hideOverlay(card);
      if (window.AnalysisModal) window.AnalysisModal.close();
      if (d.success) {
        if (d.edit_url) {
          window.location.href = d.edit_url;
          return;
        }
        updateCard(card, d);
        setStatus(card, true);
      } else {
        setStatus(card, false);
        if (window.AnalysisModal) window.AnalysisModal.open({message: FRIENDLY_AI_ERROR});
      }
    })
    .catch(err => {
      hideOverlay(card);
      setStatus(card, false);
      if (window.AnalysisModal) {
        window.AnalysisModal.open({message: FRIENDLY_AI_ERROR});
      }
    });
}

function setStatus(card, ok) {
  const icon = card.querySelector('.status-icon');
  if (!icon) return;
  icon.textContent = ok ? '✅' : '❌';
}

function updateCard(card, data) {
  const listing = data.listing || {};
  const titleEl = card.querySelector('.card-title');
  if (listing.title && titleEl) titleEl.textContent = listing.title;
  const descEl = card.querySelector('.desc-snippet');
  if (listing.description && descEl) descEl.textContent = listing.description.slice(0, 160);
  if (data.seo_folder) {
    const img = card.querySelector('.card-img-top');
    // Update thumbnail to the processed location
    if (img) img.src = `/static/art-processing/processed-artwork/${data.seo_folder}/${data.seo_folder}-THUMB.jpg?t=` + Date.now();
  }
}


---
## static/js/edit_listing.js
---
/* ==============================
   ArtNarrator Edit Listing JS
   ============================== */

/* --------- [ EL1. Carousel Modal ] --------- */
document.addEventListener('DOMContentLoaded', () => {
  const carousel = document.getElementById('mockup-carousel');
  const imgEl = document.getElementById('carousel-img');
  const closeBtn = document.getElementById('carousel-close');
  const prevBtn = document.getElementById('carousel-prev');
  const nextBtn = document.getElementById('carousel-next');

  const links = Array.from(document.querySelectorAll('.mockup-img-link'));
  const thumb = document.querySelector('.main-thumb-link');
  if (thumb) links.unshift(thumb);
  const images = links.map(l => l.dataset.img);
  let idx = 0;

  function show(i) {
    idx = (i + images.length) % images.length;
    imgEl.src = images[idx];
    carousel.classList.add('active');
  }
  function close() {
    carousel.classList.remove('active');
    imgEl.src = '';
  }
  links.forEach((link, i) => {
    link.addEventListener('click', e => {
      e.preventDefault();
      show(i);
    });
  });
  if (closeBtn) closeBtn.onclick = close;
  if (prevBtn) prevBtn.onclick = () => show(idx - 1);
  if (nextBtn) nextBtn.onclick = () => show(idx + 1);
  if (carousel) carousel.addEventListener('click', e => { if (e.target === carousel) close(); });
  document.addEventListener('keydown', e => {
    if (!carousel.classList.contains('active')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(idx - 1);
    else if (e.key === 'ArrowRight') show(idx + 1);
  });

  /* --------- [ EL2. Swap Mockup Forms ] --------- */
  document.querySelectorAll('.swap-form').forEach(form => {
    form.addEventListener('submit', ev => {
      ev.preventDefault();
      const sel = form.querySelector('select[name="new_category"]');
      const data = new FormData();
      data.append('new_category', sel.value);
      fetch(form.action, {
        method: 'POST',
        body: data,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
      .then(r => r.json())
      .then(d => {
        if (d.success && d.img_url) {
          const card = form.closest('.mockup-card');
          const img = card.querySelector('.mockup-thumb-img');
          if (img) img.src = d.img_url + '?t=' + Date.now();
          const link = card.querySelector('.mockup-img-link');
          if (link) {
            link.href = d.img_url;
            link.dataset.img = d.img_url;
          }
        } else {
          window.location.reload();
        }
      })
      .catch(() => window.location.reload());
    });
  });

  /* --------- [ EL3. Enable Action Buttons ] --------- */
  function toggleActionBtns() {
    const txt = document.querySelector('textarea[name="images"]');
    const disabled = !(txt && txt.value.trim());
    document.querySelectorAll('.require-images').forEach(btn => {
      btn.disabled = disabled;
    });
  }
  const imagesTextarea = document.querySelector('textarea[name="images"]');
  if (imagesTextarea) imagesTextarea.addEventListener('input', toggleActionBtns);
  toggleActionBtns();
});

function swapMockup(category) {
  console.log('Swapping mockup for category: ' + category);
}


---
## static/js/gallery.js
---
document.addEventListener('DOMContentLoaded', () => {
  const modalBg = document.getElementById('final-modal-bg');
  const modalImg = document.getElementById('final-modal-img');
  const closeBtn = document.getElementById('final-modal-close');
  const grid = document.querySelector('.finalised-grid');
  const viewKey = grid ? grid.dataset.viewKey || 'view' : 'view';
  document.querySelectorAll('.final-img-link').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      if (modalBg && modalImg) {
        modalImg.src = link.dataset.img;
        modalBg.style.display = 'flex';
      }
    });
  });
  if (closeBtn) closeBtn.onclick = () => {
    modalBg.style.display = 'none';
    modalImg.src = '';
  };
  if (modalBg) modalBg.onclick = e => {
    if (e.target === modalBg) {
      modalBg.style.display = 'none';
      modalImg.src = '';
    }
  };
  document.querySelectorAll('.locked-delete-form').forEach(f => {
    f.addEventListener('submit', ev => {
      const val = prompt('This listing is locked and will be permanently deleted. Type DELETE to confirm');
      if (val !== 'DELETE') { ev.preventDefault(); }
      else { f.querySelector('input[name="confirm"]').value = 'DELETE'; }
    });
  });
  const gBtn = document.getElementById('grid-view-btn');
  const lBtn = document.getElementById('list-view-btn');
  function apply(v) {
    if (!grid) return;
    if (v === 'list') { grid.classList.add('list-view'); }
    else { grid.classList.remove('list-view'); }
  }
  if (gBtn) gBtn.addEventListener('click', () => { apply('grid'); localStorage.setItem(viewKey, 'grid'); });
  if (lBtn) lBtn.addEventListener('click', () => { apply('list'); localStorage.setItem(viewKey, 'list'); });
  apply(localStorage.getItem(viewKey) || 'grid');
});


---
## static/js/main-overlay-test.js
---
// THIS IS A TEST MIGRATION TEMPLATE. Safe to delete after production migration.
        document.addEventListener('DOMContentLoaded', () => {
            const menuToggle = document.getElementById('menu-toggle');
            const menuClose = document.getElementById('menu-close');
            const overlayMenu = document.getElementById('overlay-menu');
            const themeToggle = document.getElementById('theme-toggle');
            const rootEl = document.documentElement;

            // --- Menu Logic ---
            if (menuToggle && menuClose && overlayMenu) {
                menuToggle.addEventListener('click', () => {
                    overlayMenu.classList.add('is-active');
                    body.style.overflow = 'hidden';
                });

                menuClose.addEventListener('click', () => {
                    overlayMenu.classList.remove('is-active');
                    body.style.overflow = '';
                });
            }

            // --- Theme Logic ---
            // --- Theme Logic ---
            const applyTheme = (theme) => {
                rootEl.classList.remove('theme-light', 'theme-dark');
                rootEl.classList.add('theme-' + theme);
                localStorage.setItem('theme', theme);
            };

            const savedTheme = localStorage.getItem('theme');
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const initial = savedTheme || (prefersDark ? 'dark' : 'light');
            applyTheme(initial);

            if (themeToggle) {
                themeToggle.addEventListener('click', () => {
                    const next = rootEl.classList.contains('theme-dark') ? 'light' : 'dark';
                    applyTheme(next);
                });
            }
            
            // --- Gemini Modal Logic ---
            const modal = document.getElementById('gemini-modal');
            const modalTitle = document.getElementById('gemini-modal-title');
            const modalBody = document.getElementById('gemini-modal-body');
            const closeBtn = document.querySelector('.gemini-modal-close');
            const copyBtn = document.getElementById('gemini-copy-btn');

            const defaultPrompts = {
                'generate-description': `Act as an expert art critic. Write an evocative and compelling gallery description for a piece of art titled "{ART_TITLE}". Focus on the potential materials, the mood it evokes, and the ideal setting for it. Make it about 150 words.`,
                'create-social-post': `Generate a short, engaging Instagram post to promote a piece of art titled "{ART_TITLE}". Include a catchy opening line, a brief description, and 3-5 relevant hashtags.`
            };

            closeBtn.onclick = () => {
                modal.style.display = "none";
            }
            window.onclick = (event) => {
                if (event.target == modal) {
                    modal.style.display = "none";
                }
            }

            document.querySelectorAll('.btn-gemini').forEach(button => {
                button.addEventListener('click', async (e) => {
                    const action = e.target.dataset.action;
                    const artPiece = e.target.closest('.art-piece');
                    const artTitle = artPiece.querySelector('h2').textContent;
                    
                    let promptTemplate = '';
                    let title = '';

                    if (action === 'generate-description') {
                        title = '✨ AI Art Description';
                        promptTemplate = localStorage.getItem('geminiDescriptionPrompt') || defaultPrompts[action];
                    } else if (action === 'create-social-post') {
                        title = '✨ AI Social Media Post';
                        promptTemplate = defaultPrompts[action]; // Using default for this one
                    }

                    const prompt = promptTemplate.replace('{ART_TITLE}', artTitle);

                    modalTitle.textContent = title;
                    modalBody.innerHTML = '<div class="loader"></div>';
                    modal.style.display = 'flex';

                    try {
                        let chatHistory = [{ role: "user", parts: [{ text: prompt }] }];
                        const payload = { contents: chatHistory };
                        const apiKey = ""; 
                        const apiUrl = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + apiKey;
                        
                        const response = await fetch(apiUrl, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });
                        
                        if (!response.ok) {
                             throw new Error("API error: " + response.status + " " + response.statusText);
                        }

                        const result = await response.json();
                        
                        if (result.candidates && result.candidates.length > 0 &&
                            result.candidates[0].content && result.candidates[0].content.parts &&
                            result.candidates[0].content.parts.length > 0) {
                            const text = result.candidates[0].content.parts[0].text;
                            modalBody.innerHTML = '<textarea id="gemini-result">' + text + '</textarea>';
                        } else {
                            throw new Error("Invalid response structure from API.");
                        }

                    } catch (error) {
                        console.error("Gemini API call failed:", error);
                        modalBody.innerHTML = '<p>Sorry, something went wrong. Please try again. (' + error.message + ')</p>';
                    }
                });
            });
            
            copyBtn.addEventListener('click', () => {
                const resultTextarea = document.getElementById('gemini-result');
                if (resultTextarea) {
                    resultTextarea.select();
                    document.execCommand('copy');
                    copyBtn.textContent = 'Copied!';
                    setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
                }
            });

        });


---
## static/js/main.js
---
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('theme-toggle');
  const sunIcon = document.getElementById('icon-sun');
  const moonIcon = document.getElementById('icon-moon');

  function applyTheme(theme) {
    document.documentElement.classList.remove('theme-light', 'theme-dark');
    document.documentElement.classList.add('theme-' + theme);
    localStorage.setItem('theme', theme);
    if (sunIcon && moonIcon) {
      sunIcon.style.display = theme === 'dark' ? 'none' : 'inline';
      moonIcon.style.display = theme === 'dark' ? 'inline' : 'none';
    }
  }

  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initial = saved || (prefersDark ? 'dark' : 'light');
  applyTheme(initial);

  if (toggle) {
    toggle.addEventListener('click', () => {
      const next = document.documentElement.classList.contains('theme-dark')
        ? 'light' : 'dark';
      applyTheme(next);
    });
  }
});


---
## static/js/mockup-admin.js
---
document.addEventListener('DOMContentLoaded', () => {
    // --- Element Definitions ---
    const mockupGrid = document.getElementById('mockup-grid');
    const arSelector = document.getElementById('aspect-ratio-selector');
    const perPageSelector = document.getElementById('per-page-selector');
    const sortSelector = document.getElementById('sort-selector');
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const imageModal = document.getElementById('image-modal');
    const duplicatesModal = document.getElementById('duplicates-modal');
    const uploadModal = document.getElementById('upload-modal');
    const uploadModalContent = `
        <div class="analysis-box">
            <img src="/static/icons/svg/light/upload-light.svg" class="progress-icon" alt="">
            <h3>Uploading Mockups...</h3>
            <div id="upload-filename" class="analysis-status"></div>
            <div class="analysis-progress">
                <div id="upload-bar" class="analysis-progress-bar"></div>
            </div>
            <div id="upload-status" class="analysis-status">0%</div>
        </div>`;

    // --- Page Controls ---
    function updateUrlParams() {
        const aspect = arSelector.value;
        const perPage = perPageSelector.value;
        const sortBy = sortSelector.value;
        const urlParams = new URLSearchParams(window.location.search);
        const category = urlParams.get('category') || 'All';
        window.location.href = `/admin/mockups/${aspect}?per_page=${perPage}&category=${category}&sort=${sortBy}`;
    }

    if (arSelector) arSelector.addEventListener('change', updateUrlParams);
    if (perPageSelector) perPageSelector.addEventListener('change', updateUrlParams);
    if (sortSelector) sortSelector.addEventListener('change', updateUrlParams);

    function selectOptionByText(selectEl, textToFind) {
        const text = (textToFind || '').trim().toLowerCase();
        for (let i = 0; i < selectEl.options.length; i++) {
            const option = selectEl.options[i];
            if (option.text.trim().toLowerCase() === text) {
                selectEl.selectedIndex = i;
                return;
            }
        }
    }

    // --- Main Grid Event Delegation ---
    if (mockupGrid) {
        mockupGrid.addEventListener('click', async (e) => {
            const card = e.target.closest('.gallery-card');
            if (!card) return;

            const filename = card.dataset.filename;
            const originalCategory = card.dataset.category;
            const overlay = card.querySelector('.card-overlay');
            const button = e.target;
            const currentAspect = arSelector.value;

            if (button.classList.contains('card-img-top')) {
                const fullSizeUrl = button.dataset.fullsizeUrl;
                if (fullSizeUrl && imageModal) {
                    imageModal.querySelector('.modal-img').src = fullSizeUrl;
                    imageModal.style.display = 'flex';
                }
                return;
            }

            const actionsContainer = card.querySelector('.categorize-actions');
            if (actionsContainer) {
                if (button.classList.contains('btn-categorize')) {
                    const selectElement = actionsContainer.querySelector('select');
                    overlay.innerHTML = `<span class="spinner"></span> Asking AI...`;
                    overlay.classList.remove('hidden');
                    button.disabled = true;
                    try {
                        const response = await fetch("/admin/mockups/suggest-category", {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ filename: filename, aspect: currentAspect })
                        });
                        const result = await response.json();
                        if (result.success) {
                            selectOptionByText(selectElement, result.suggestion);
                        } else {
                            alert(`Error: ${result.error}`);
                        }
                    } catch (err) {
                        alert('A network error occurred.');
                    } finally {
                        overlay.classList.add('hidden');
                        button.disabled = false;
                    }
                }

                if (button.classList.contains('btn-save-move')) {
                    const newCategory = actionsContainer.querySelector('select').value;
                    if (!newCategory) {
                        alert('Please select a category.');
                        return;
                    }
                    overlay.innerHTML = `<span class="spinner"></span> Moving...`;
                    overlay.classList.remove('hidden');

                    const response = await fetch("/admin/mockups/move-mockup", {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ filename, aspect: currentAspect, original_category: originalCategory, new_category: newCategory })
                    });
                    const result = await response.json();
                    if (result.success) {
                        card.remove(); 
                    } else {
                        overlay.textContent = `Error: ${result.error}`;
                    }
                }
            }
            
            if (button.classList.contains('btn-delete')) {
                if (!confirm(`Are you sure you want to permanently delete "${filename}"?`)) return;
                overlay.innerHTML = `<span class="spinner"></span> Deleting...`;
                overlay.classList.remove('hidden');

                const response = await fetch("/admin/mockups/delete-mockup", {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ filename, aspect: currentAspect, category: originalCategory })
                });
                const result = await response.json();
                if (result.success) {
                    card.remove();
                } else {
                    overlay.textContent = `Error: ${result.error}`;
                }
            }
        });
    }

    // --- Modal Logic ---
    [imageModal, duplicatesModal].forEach(modal => {
        if (modal) {
            const closeBtn = modal.querySelector('.modal-close');
            if(closeBtn) closeBtn.addEventListener('click', () => modal.style.display = 'none');
            modal.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });
        }
    });

    // --- Find Duplicates Logic ---
    const findDuplicatesBtn = document.getElementById('find-duplicates-btn');
    if (findDuplicatesBtn) {
        findDuplicatesBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            const btn = e.target;
            const originalText = btn.textContent;
            btn.textContent = 'Scanning...';
            btn.disabled = true;

            try {
                const response = await fetch(btn.dataset.url);
                const data = await response.json();
                const listEl = document.getElementById('duplicates-list');
                listEl.innerHTML = '';

                if (data.duplicates.length > 0) {
                    const ul = document.createElement('ul');
                    data.duplicates.forEach(pair => {
                        const li = document.createElement('li');
                        li.innerHTML = `<strong>${pair.original}</strong><br>is a duplicate of<br><em>${pair.duplicate}</em>`;
                        ul.appendChild(li);
                    });
                    listEl.appendChild(ul);
                } else {
                    listEl.innerHTML = '<p>No duplicates found. Good job!</p>';
                }
                duplicatesModal.style.display = 'flex';
            } catch (error) {
                alert('Failed to check for duplicates.');
            } finally {
                btn.textContent = originalText;
                btn.disabled = false;
            }
        });
    }

    // --- Drag & Drop Upload Logic ---
    if (dropzone && fileInput && uploadModal) {
        function uploadFile(file) {
            return new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                const formData = new FormData();
                const currentAspect = arSelector.value;
                formData.append('mockup_files', file);

                xhr.upload.addEventListener('progress', e => {
                    if (e.lengthComputable) {
                        const percent = Math.round((e.loaded / e.total) * 100);
                        const progressBar = uploadModal.querySelector('#upload-bar');
                        const statusEl = uploadModal.querySelector('#upload-status');
                        if(progressBar) progressBar.style.width = percent + '%';
                        if(statusEl) statusEl.textContent = `${percent}%`;
                    }
                });
                xhr.addEventListener('load', () => xhr.status < 400 ? resolve() : reject(new Error(`Server responded with ${xhr.status}`)));
                xhr.addEventListener('error', () => reject(new Error('Network error during upload.')));
                xhr.open('POST', `/admin/mockups/upload/${currentAspect}`, true);
                xhr.send(formData);
            });
        }

        async function uploadFiles(files) {
            if (!files || !files.length) return;
            uploadModal.innerHTML = uploadModalContent;
            uploadModal.classList.add('active');
            
            const progressBar = uploadModal.querySelector('#upload-bar');
            const statusEl = uploadModal.querySelector('#upload-status');
            const filenameEl = uploadModal.querySelector('#upload-filename');

            for (const file of Array.from(files)) {
                if(filenameEl) filenameEl.textContent = `Uploading: ${file.name}`;
                if(progressBar) progressBar.style.width = '0%';
                if(statusEl) statusEl.textContent = '0%';
                try {
                    await uploadFile(file);
                    if(statusEl) statusEl.textContent = 'Complete!';
                } catch (error) {
                    if(statusEl) statusEl.textContent = `Error uploading ${file.name}.`;
                    await new Promise(res => setTimeout(res, 2000));
                }
            }
            window.location.reload();
        }

        ['dragenter', 'dragover'].forEach(evt => dropzone.addEventListener(evt, e => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        }));
        ['dragleave', 'drop'].forEach(evt => dropzone.addEventListener(evt, () => dropzone.classList.remove('dragover')));
        dropzone.addEventListener('drop', e => {
            e.preventDefault();
            uploadFiles(e.dataTransfer.files);
        });
        dropzone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', () => uploadFiles(fileInput.files));
    }
});

---
## static/js/new-main.js
---
// THIS IS A TEST MIGRATION TEMPLATE. Safe to delete after production migration.
        document.addEventListener('DOMContentLoaded', () => {
            const menuToggle = document.getElementById('menu-toggle');
            const menuClose = document.getElementById('menu-close');
            const overlayMenu = document.getElementById('overlay-menu');
            const themeToggle = document.getElementById('theme-toggle');
            const rootEl = document.documentElement;

            // --- Menu Logic ---
            if (menuToggle && menuClose && overlayMenu) {
                menuToggle.addEventListener('click', () => {
                    overlayMenu.classList.add('is-active');
                    body.style.overflow = 'hidden';
                });

                menuClose.addEventListener('click', () => {
                    overlayMenu.classList.remove('is-active');
                    body.style.overflow = '';
                });
            }

            // --- Theme Logic ---
            const applyTheme = (theme) => {
                rootEl.classList.remove('theme-light', 'theme-dark');
                rootEl.classList.add('theme-' + theme);
                localStorage.setItem('theme', theme);
            };

            const savedTheme = localStorage.getItem('theme');
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const initial = savedTheme || (prefersDark ? 'dark' : 'light');
            applyTheme(initial);

            if (themeToggle) {
                themeToggle.addEventListener('click', () => {
                    const next = rootEl.classList.contains('theme-dark') ? 'light' : 'dark';
                    applyTheme(next);
                });
            }
            
            // --- Gemini Modal Logic ---
            const modal = document.getElementById('gemini-modal');
            const modalTitle = document.getElementById('gemini-modal-title');
            const modalBody = document.getElementById('gemini-modal-body');
            const closeBtn = document.querySelector('.gemini-modal-close');
            const copyBtn = document.getElementById('gemini-copy-btn');

            const defaultPrompts = {
                'generate-description': `Act as an expert art critic. Write an evocative and compelling gallery description for a piece of art titled "{ART_TITLE}". Focus on the potential materials, the mood it evokes, and the ideal setting for it. Make it about 150 words.`,
                'create-social-post': `Generate a short, engaging Instagram post to promote a piece of art titled "{ART_TITLE}". Include a catchy opening line, a brief description, and 3-5 relevant hashtags.`
            };

            closeBtn.onclick = () => {
                modal.style.display = "none";
            }
            window.onclick = (event) => {
                if (event.target == modal) {
                    modal.style.display = "none";
                }
            }

            document.querySelectorAll('.btn-gemini').forEach(button => {
                button.addEventListener('click', async (e) => {
                    const action = e.target.dataset.action;
                    const artPiece = e.target.closest('.art-piece');
                    const artTitle = artPiece.querySelector('h2').textContent;
                    
                    let promptTemplate = '';
                    let title = '';

                    if (action === 'generate-description') {
                        title = '✨ AI Art Description';
                        promptTemplate = localStorage.getItem('geminiDescriptionPrompt') || defaultPrompts[action];
                    } else if (action === 'create-social-post') {
                        title = '✨ AI Social Media Post';
                        promptTemplate = defaultPrompts[action]; // Using default for this one
                    }

                    const prompt = promptTemplate.replace('{ART_TITLE}', artTitle);

                    modalTitle.textContent = title;
                    modalBody.innerHTML = '<div class="loader"></div>';
                    modal.style.display = 'flex';

                    try {
                        let chatHistory = [{ role: "user", parts: [{ text: prompt }] }];
                        const payload = { contents: chatHistory };
                        const apiKey = ""; 
                        const apiUrl = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + apiKey;
                        
                        const response = await fetch(apiUrl, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });
                        
                        if (!response.ok) {
                             throw new Error("API error: " + response.status + " " + response.statusText);
                        }

                        const result = await response.json();
                        
                        if (result.candidates && result.candidates.length > 0 &&
                            result.candidates[0].content && result.candidates[0].content.parts &&
                            result.candidates[0].content.parts.length > 0) {
                            const text = result.candidates[0].content.parts[0].text;
                            modalBody.innerHTML = '<textarea id="gemini-result">' + text + '</textarea>';
                        } else {
                            throw new Error("Invalid response structure from API.");
                        }

                    } catch (error) {
                        console.error("Gemini API call failed:", error);
                        modalBody.innerHTML = '<p>Sorry, something went wrong. Please try again. (' + error.message + ')</p>';
                    }
                });
            });
            
            copyBtn.addEventListener('click', () => {
                const resultTextarea = document.getElementById('gemini-result');
                if (resultTextarea) {
                    resultTextarea.select();
                    document.execCommand('copy');
                    copyBtn.textContent = 'Copied!';
                    setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
                }
            });

        });


---
## static/js/upload.js
---
/* ================================
   ArtNarrator Upload JS (XMLHttpRequest for Progress)
   ================================ */

document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  
  // Modal elements
  const modal = document.getElementById('upload-modal');
  const progressBar = document.getElementById('upload-bar');
  const statusEl = document.getElementById('upload-status');
  const filenameEl = document.getElementById('upload-filename');

  function uploadFile(file) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('images', file);

      xhr.upload.addEventListener('progress', e => {
        if (e.lengthComputable) {
          const percentComplete = Math.round((e.loaded / e.total) * 100);
          progressBar.style.width = percentComplete + '%';
          statusEl.textContent = `${percentComplete}%`;
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(xhr.responseText);
        } else {
          reject(new Error(`Upload failed: ${xhr.statusText}`));
        }
      });

      xhr.addEventListener('error', () => reject(new Error('Upload failed due to a network error.')));
      xhr.addEventListener('abort', () => reject(new Error('Upload was aborted.')));

      xhr.open('POST', '/upload', true);
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.send(formData);
    });
  }

  async function uploadFiles(files) {
    if (!files || !files.length) return;
    
    modal.classList.add('active');

    for (const file of Array.from(files)) {
      filenameEl.textContent = `Uploading: ${file.name}`;
      progressBar.style.width = '0%';
      statusEl.textContent = '0%';
      
      try {
        await uploadFile(file);
        statusEl.textContent = 'Complete!';
      } catch (error) {
        statusEl.textContent = `Error: ${error.message}`;
        await new Promise(res => setTimeout(res, 2000)); // Show error for 2s
      }
    }

    // Redirect after all files are processed
    modal.classList.remove('active');
    window.location.href = '/artworks';
  }

  if (dropzone) {
    ['dragenter', 'dragover'].forEach(evt => {
      dropzone.addEventListener(evt, e => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    });
    ['dragleave', 'drop'].forEach(evt => {
      dropzone.addEventListener(evt, () => dropzone.classList.remove('dragover'));
    });
    dropzone.addEventListener('drop', e => {
      e.preventDefault();
      uploadFiles(e.dataTransfer.files);
    });
    dropzone.addEventListener('click', () => fileInput.click());
  }

  if (fileInput) {
    fileInput.addEventListener('change', () => uploadFiles(fileInput.files));
  }
});

---
## templates/404.html
---
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oops! Page Not Found</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/404.css') }}">
</head>
<body>
    <div class="container">
        <h1>Oops! Something went wrong...</h1>
        <p>It looks like the page you're looking for has either moved or doesn't exist. Don't worry, it's probably not your fault!</p>
        <p>Why not head back to the <a href="/">homepage</a> and try again?</p>
    </div>
</body>
</html>


---
## templates/500.html
---
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Error</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/404.css') }}">
</head>
<body>
    <div class="container">
        <h1>Something went wrong</h1>
        <p>We've logged the error and will fix it ASAP.</p>
        <p><a href="{{ url_for('artwork.home') }}">Return to home</a></p>
    </div>
</body>
</html>


---
## templates/artworks.html
---
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}Artwork | ArtNarrator{% endblock %}
{% block content %}
<div class="container">

<div class="home-hero" >
  <h1><img src="{{ url_for('static', filename='icons/svg/light/number-circle-two-light.svg') }}" class="hero-step-icon" alt="Step 2: Artwork" />Artwork</h1>
</div>

<div class="gallery-section">

  {% if ready_artworks %}
    <h2 class="mb-3">Ready to Analyze</h2>
    <div class="artwork-grid">
      {% for art in ready_artworks %}
      <div class="gallery-card" data-filename="{{ art.filename }}">
        <div class="card-thumb">
          <img class="card-img-top"
               src="{{ url_for('artwork.unanalysed_image', filename=art.thumb) }}"
               alt="{{ art.title }}">
        </div>
        <span class="status-icon"></span>
        <div class="card-details">
          <div class="card-title">{{ art.title }}</div>
          <div class="desc-snippet"></div>
          <div class="button-row">
            <button class="btn btn-primary btn-analyze" data-provider="openai">Analyze with OpenAI</button>
            <button class="btn btn-secondary btn-analyze" data-provider="google">Analyze with Google</button>
            <button class="btn btn-danger btn-delete">Delete</button>
          </div>
        </div>
        <div class="card-overlay hidden"></div>
      </div>
      {% endfor %}
    </div>
  {% endif %}

  {% if processed_artworks %}
    <h2 class="mb-3 mt-5">Processed Artworks</h2>
    <div class="artwork-grid">
      {% for art in processed_artworks %}
      <div class="gallery-card" data-filename="{{ art.filename }}">
        <div class="card-thumb">
          <img class="card-img-top"
               src="{{ url_for('artwork.processed_image', seo_folder=art.seo_folder, filename=art.thumb) }}"
               alt="{{ art.title }}">
        </div>
        <span class="status-icon"></span>
        <div class="card-details">
          <div class="card-title">{{ art.title }}</div>
          <div class="desc-snippet"></div>
          <div class="button-row">
            <a href="{{ url_for('artwork.edit_listing', aspect=art.aspect, filename=art.filename) }}" class="btn btn-primary btn-edit">Review</a>
            <button class="btn btn-secondary btn-analyze" data-provider="openai">Analyze with OpenAI</button>
            <button class="btn btn-secondary btn-analyze" data-provider="google">Analyze with Google</button>
            <button class="btn btn-danger btn-delete">Delete</button>
          </div>
        </div>
        <div class="card-overlay hidden"></div>
      </div>
      {% endfor %}
    </div>
  {% endif %}

  {% if finalised_artworks %}
    <h2 class="mb-3 mt-5">Finalised Artworks</h2>
    <div class="artwork-grid">
      {% for art in finalised_artworks %}
      <div class="gallery-card" data-filename="{{ art.filename }}">
        <div class="card-thumb">
          <img class="card-img-top"
               src="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.thumb) }}"
               alt="{{ art.title }}">
        </div>
        <span class="status-icon"></span>
        <div class="card-details">
          <div class="card-title">{{ art.title }}</div>
          <div class="desc-snippet"></div>
          <div class="button-row">
            <a href="{{ url_for('artwork.edit_listing', aspect=art.aspect, filename=art.filename) }}" class="btn btn-secondary btn-edit">Edit</a>
            <button class="btn btn-secondary btn-analyze" data-provider="openai">Analyze with OpenAI</button>
            <button class="btn btn-secondary btn-analyze" data-provider="google">Analyze with Google</button>
            <button class="btn btn-danger btn-delete">Delete</button>
          </div>
        </div>
        <div class="card-overlay hidden"></div>
      </div>
      {% endfor %}
    </div>
  {% endif %}
  {% if not ready_artworks and not processed_artworks and not finalised_artworks %}
    <p class="empty-msg">No artworks found. Please upload artwork to get started!</p>
  {% endif %}

</div>

</div>
<script src="{{ url_for('static', filename='js/artworks.js') }}"></script>
{% endblock %}


---
## templates/composites_preview.html
---
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}Composite Preview | ArtNarrator{% endblock %}
{% block content %}
<div class="container">
<h1 style="text-align:center;">Composite Preview: {{ seo_folder }}</h1>
{% if listing %}
  <div style="text-align:center;margin-bottom:1.5em;">
    <img src="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=seo_folder+'.jpg') }}" alt="artwork" style="max-width:260px;border-radius:8px;box-shadow:0 2px 6px #0002;">
  </div>
{% endif %}
{% if images %}
<div class="grid">
  {% for img in images %}
  <div class="item">
    {% if img.exists %}
    <img src="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=img.filename) }}" alt="{{ img.filename }}">
    {% else %}
    <div class="missing-img">Image Not Found</div>
    {% endif %}
    <div style="font-size:0.9em;color:#555;word-break:break-all;">{{ img.filename }}</div>
    {% if img.category %}<div style="color:#888;font-size:0.9em;">{{ img.category }}</div>{% endif %}
    <form method="post" action="{{ url_for('artwork.regenerate_composite', seo_folder=seo_folder, slot_index=img.index) }}">
      <button type="submit" class="btn btn-reject">Regenerate</button>
    </form>
  </div>
  {% endfor %}
</div>
<form method="post" action="{{ url_for('artwork.approve_composites', seo_folder=seo_folder) }}" style="text-align:center;margin-top:2em;">
  <button type="submit" class="composite-btn">Finalize &amp; Approve</button>
</form>
{% else %}
<p style="text-align:center;margin:2em 0;">No composites found.</p>
{% endif %}
<div style="text-align:center;margin-top:2em;">
  <a href="{{ url_for('artwork.select') }}" class="composite-btn" style="background:#666;">Back to Selector</a>
</div>
</div>
{% endblock %}


---
## templates/dws_editor.html
---
{% extends "main.html" %}
{% block title %}Guided Description Editor{% endblock %}

{% block content %}
<style>
  /* --- Page Layout --- */
  .gdws-container { display: flex; flex-wrap: wrap; gap: 2rem; align-items: flex-start; }
  .gdws-main-content { flex: 1; min-width: 60%; }
  .gdws-sidebar { width: 280px; position: sticky; top: 100px; padding: 1.5rem; background-color: var(--color-card-bg); border: 1px solid var(--card-border); }
  .gdws-sidebar h3 { margin-top: 0; text-align: center; margin-bottom: 1.5rem; }
  .gdws-sidebar button { width: 100%; margin-bottom: 1rem; }

  /* --- Block Styles --- */
  .paragraph-block { background-color: var(--color-card-bg); border: 1px solid var(--card-border); padding: 1.5rem; margin-bottom: 1.5rem; cursor: grab; }
  .paragraph-block:active { cursor: grabbing; }
  .paragraph-block h3, .paragraph-block .block-title { margin-top: 0; font-size: 1.2em; }
  .paragraph-block .block-title { width: 100%; padding: 0.5rem; border: 1px solid transparent; background-color: transparent; font-family: inherit; font-weight: bold; }
  .paragraph-block .block-title:focus { border-color: var(--card-border); background-color: var(--color-background); }
  .paragraph-block textarea { width: 100%; min-height: 150px; background-color: var(--color-background); color: var(--color-text); border: 1px solid var(--card-border); padding: 0.5rem; }
  .block-actions { margin-top: 1rem; display: flex; gap: 1rem; justify-content: space-between; align-items: center; flex-wrap: wrap; }
  .title-actions { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
  .btn-regenerate-title { font-size: 0.8em; padding: 0.3em 0.6em; min-width: auto; }
  .sortable-ghost { opacity: 0.4; background: #888; border: 2px dashed var(--color-accent); }
  .pinned { background-color: #f0f0f0; border-left: 4px solid #007bff; cursor: not-allowed; }
  .theme-dark .pinned { background-color: #2a2a2a; border-left-color: #4e9fef; }
  .instructions-modal { display: none; }
</style>

<div class="container">
  <h1>Guided Description Editor</h1>
  <p>Select an aspect ratio to load its base paragraphs. You can edit content, regenerate with AI, and modify the instructions for each section. Paragraphs in the middle section can be reordered via drag-and-drop.</p>
  
  <div class="gdws-container">
    <div class="gdws-main-content">
      <div class="form-group">
        <label for="aspect-ratio-selector">Select Aspect Ratio:</label>
        <select id="aspect-ratio-selector">
          <option value="">-- Choose --</option>
          {% for ar in aspect_ratios %}
          <option value="{{ ar }}">{{ ar }}</option>
          {% endfor %}
        </select>
      </div>
      
      <div id="editor-wrapper" style="margin-top: 2rem;">
        <div id="start-blocks"></div>
        <div id="middle-blocks"></div>
        <div id="end-blocks"></div>
      </div>
    </div>

    <aside class="gdws-sidebar">
      <h3>Global Actions</h3>
      <button id="save-order-btn" class="btn btn-primary wide-btn" disabled>Save Order</button>
      <button id="regenerate-all-btn" class="btn btn-secondary wide-btn" disabled>Regenerate All Content</button>
      <button id="reset-all-btn" class="btn btn-secondary wide-btn" disabled>Reset All to Base</button>
    </aside>
  </div>
</div>

<div id="instructions-modal" class="analysis-modal instructions-modal" role="dialog" aria-modal="true">
    <div class="analysis-box" tabindex="-1">
        <button class="modal-close" aria-label="Close">&times;</button>
        <h3 id="instructions-title">Instructions</h3>
        <textarea id="instructions-text" rows="8" style="width: 100%;"></textarea>
        <div class="block-actions" style="justify-content: flex-end;">
            <button id="save-instructions-btn" class="btn btn-primary">Save Instructions</button>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"></script>

<script>
document.addEventListener('DOMContentLoaded', () => {
    const arSelector = document.getElementById('aspect-ratio-selector');
    const startBlocksContainer = document.getElementById('start-blocks');
    const middleBlocksContainer = document.getElementById('middle-blocks');
    const endBlocksContainer = document.getElementById('end-blocks');
    const editorWrapper = document.getElementById('editor-wrapper');
    
    const regenerateAllBtn = document.getElementById('regenerate-all-btn');
    const resetAllBtn = document.getElementById('reset-all-btn');
    const saveOrderBtn = document.getElementById('save-order-btn');
    
    const instructionsModal = document.getElementById('instructions-modal');
    const instructionsTitle = document.getElementById('instructions-title');
    const instructionsText = document.getElementById('instructions-text');
    const saveInstructionsBtn = document.getElementById('save-instructions-btn');
    const closeInstructionsBtn = instructionsModal.querySelector('.modal-close');
    let currentBlockForInstructions = null;
    
    let sortable = null;
    // CORRECTED: Load the server-rendered JSON into JS variables
    const PINNED_START_TITLES = JSON.parse('{{ PINNED_START_TITLES | tojson | safe }}');
    const PINNED_END_TITLES = JSON.parse('{{ PINNED_END_TITLES | tojson | safe }}');

    async function loadTemplate(aspectRatio) {
        if (!aspectRatio) {
            startBlocksContainer.innerHTML = '<p>Please select an aspect ratio to begin.</p>';
            middleBlocksContainer.innerHTML = '';
            endBlocksContainer.innerHTML = '';
            [regenerateAllBtn, resetAllBtn, saveOrderBtn].forEach(b => b.disabled = true);
            return;
        }
        startBlocksContainer.innerHTML = '<p>Loading...</p>';
        middleBlocksContainer.innerHTML = '';
        endBlocksContainer.innerHTML = '';

        const response = await fetch(`/admin/gdws/template/${aspectRatio}`);
        const data = await response.json();
        
        startBlocksContainer.innerHTML = '';

        data.blocks.forEach(block => {
            const isStart = PINNED_START_TITLES.includes(block.title);
            const isEnd = PINNED_END_TITLES.includes(block.title);
            const container = isStart ? startBlocksContainer : (isEnd ? endBlocksContainer : middleBlocksContainer);
            renderBlock(block, container, !isStart && !isEnd);
        });
        
        if (sortable) sortable.destroy();
        sortable = new Sortable(middleBlocksContainer, {
            animation: 150,
            ghostClass: 'sortable-ghost'
        });

        [regenerateAllBtn, resetAllBtn, saveOrderBtn].forEach(b => b.disabled = false);
    }

    function renderBlock(block, container, isDraggable) {
        const blockEl = document.createElement('div');
        blockEl.className = 'paragraph-block';
        if (!isDraggable) blockEl.classList.add('pinned');
        
        blockEl.dataset.id = block.title; 
        blockEl.dataset.originalTitle = block.title;
        blockEl.dataset.instructions = block.instructions || '';

        blockEl.innerHTML = `
            <div class="title-actions">
                <input type="text" class="block-title" value="${block.title}">
                <button class="btn btn-sm btn-regenerate-title" title="Regenerate Title with AI">AI Title</button>
            </div>
            <textarea>${block.content}</textarea>
            <div class="block-actions">
                <button class="btn btn-secondary btn-instructions">View/Edit Instructions</button>
                <div>
                    <button class="btn btn-secondary btn-regenerate">Regenerate Content</button>
                    <button class="btn btn-primary btn-save-base">Update Base</button>
                </div>
            </div>
        `;
        container.appendChild(blockEl);
    }

    // --- Event Listeners ---

    arSelector.addEventListener('change', () => loadTemplate(arSelector.value));

    resetAllBtn.addEventListener('click', () => {
        const currentAspect = arSelector.value;
        if (currentAspect && confirm('Are you sure? This will discard all unsaved changes and reload the saved base text.')) {
            loadTemplate(currentAspect);
        }
    });

    saveOrderBtn.addEventListener('click', async () => {
        const order = Array.from(middleBlocksContainer.children).map(el => el.dataset.originalTitle);
        
        saveOrderBtn.textContent = 'Saving...';
        saveOrderBtn.disabled = true;
        await fetch('/admin/gdws/save-order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ aspect_ratio: arSelector.value, order: order }),
        });
        saveOrderBtn.textContent = 'Save Order';
        saveOrderBtn.disabled = false;
        alert('New order has been saved!');
    });

    regenerateAllBtn.addEventListener('click', async () => {
        const allBlocks = document.querySelectorAll('.paragraph-block');
        if (!allBlocks.length || !confirm(`This will regenerate content for all ${allBlocks.length} paragraphs. Are you sure?`)) return;

        regenerateAllBtn.textContent = 'Regenerating...';
        regenerateAllBtn.disabled = true;

        for (const blockEl of allBlocks) {
            if (blockEl.closest('#middle-blocks') || blockEl.closest('#start-blocks') || blockEl.closest('#end-blocks')) {
                const btn = blockEl.querySelector('.btn-regenerate');
                await handleRegenerate(blockEl, btn);
            }
        }

        regenerateAllBtn.textContent = 'Regenerate All Content';
        regenerateAllBtn.disabled = false;
    });

    async function handleRegenerate(blockEl, buttonEl) {
        const textarea = blockEl.querySelector('textarea');
        const instructions = blockEl.dataset.instructions;
        
        buttonEl.textContent = '...';
        buttonEl.disabled = true;
        
        const response = await fetch('/admin/gdws/regenerate-paragraph', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ current_text: textarea.value, instructions: instructions }),
        });
        const result = await response.json();
        textarea.value = result.new_content;
        
        buttonEl.textContent = 'Regenerate Content';
        buttonEl.disabled = false;
    }
    
    editorWrapper.addEventListener('click', async (e) => {
        const blockEl = e.target.closest('.paragraph-block');
        if (!blockEl) return;

        const originalTitle = blockEl.dataset.originalTitle;
        let instructions = blockEl.dataset.instructions;
        const titleInput = blockEl.querySelector('.block-title');
        const textarea = blockEl.querySelector('textarea');
        const aspectRatio = arSelector.value;

        if (e.target.classList.contains('btn-regenerate-title')) {
            e.target.textContent = '...';
            const response = await fetch('/admin/gdws/regenerate-title', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ content: textarea.value })
            });
            const result = await response.json();
            titleInput.value = result.new_title;
            e.target.textContent = 'AI Title';
        }

        if (e.target.classList.contains('btn-save-base')) {
            e.target.textContent = 'Updating...';
            const response = await fetch('/admin/gdws/save-base-paragraph', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    aspect_ratio: aspectRatio, 
                    original_title: originalTitle,
                    new_title: titleInput.value,
                    content: textarea.value, 
                    instructions: instructions 
                }),
            });
            const result = await response.json();
            if (result.status === 'success') {
                blockEl.dataset.originalTitle = titleInput.value;
                blockEl.dataset.id = titleInput.value;
            } else {
                alert(`Error: ${result.message}`);
                titleInput.value = originalTitle;
            }
            e.target.textContent = 'Update Base';
        }
        
        if (e.target.classList.contains('btn-regenerate')) {
            await handleRegenerate(blockEl, e.target);
        }

        if (e.target.classList.contains('btn-instructions')) {
            currentBlockForInstructions = blockEl;
            instructionsTitle.textContent = `Instructions for: ${titleInput.value}`;
            instructionsText.value = instructions;
            instructionsModal.classList.add('active');
        }
    });

    // Modal close logic
    closeInstructionsBtn.addEventListener('click', () => instructionsModal.classList.remove('active'));
    saveInstructionsBtn.addEventListener('click', async () => {
        if (currentBlockForInstructions) {
            const title = currentBlockForInstructions.querySelector('.block-title').value;
            const content = currentBlockForInstructions.querySelector('textarea').value;
            const aspectRatio = arSelector.value;
            const newInstructions = instructionsText.value;

            saveInstructionsBtn.textContent = 'Saving...';
            await fetch('/admin/gdws/save-base-paragraph', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    aspect_ratio: aspectRatio, 
                    original_title: currentBlockForInstructions.dataset.originalTitle,
                    new_title: title,
                    content: content, 
                    instructions: newInstructions 
                }),
            });
            currentBlockForInstructions.dataset.instructions = newInstructions;
            saveInstructionsBtn.textContent = 'Save Instructions';
            instructionsModal.classList.remove('active');
        }
    });
});
</script>
{% endblock %}

---
## templates/edit_listing.html
---
{# Edit and finalise a single artwork listing with preview and metadata fields. #}
{% extends "main.html" %}
{% block title %}Edit Listing{% endblock %}
{% block content %}
<style>
  .action-form { width: 100%; }
  .form-col { flex: 1; }
</style>
<div class="container">
  <div class="home-hero">
    <h1><img src="{{ url_for('static', filename='icons/svg/light/number-circle-three-light.svg') }}" class="hero-step-icon" alt="Step 3: Edit Listing" />Edit Listing</h1>
  </div>

  <div class="review-artwork-grid row">
    <div class="col col-6 mockup-col">
      <div class="main-thumb">
        <a href="#" class="main-thumb-link" data-img="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=seo_folder+'.jpg') }}?t={{ cache_ts }}">
          <img src="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=seo_folder+'-THUMB.jpg') }}?t={{ cache_ts }}" class="main-artwork-thumb" alt="Main artwork thumbnail for {{ seo_folder }}">
        </a>
        <div class="thumb-note">Click thumbnail for full size</div>
      </div>

      <div>
        <h3>Preview Mockups</h3>
        <div class="debug-categories">
          <strong>Categories:</strong>
          {% if categories %}
            {{ categories | join(', ') }}
          {% else %}
            none
          {% endif %}
        </div>

        <div class="mockup-preview-grid">
          {% for m in mockups %}
            <div class="mockup-card">
              {% if m.exists %}
                {# Smart fallback logic for thumbnail display #}
                {% set thumb_name = m.path.stem + '-thumb.jpg' %}
                {% set thumb_path = 'art-processing/processed-artwork/' + seo_folder + '/THUMBS/' + thumb_name %}
                {% set full_path = 'art-processing/processed-artwork/' + seo_folder + '/' + m.path.name %}
                <a href="{{ url_for('static', filename=full_path) }}?t={{ cache_ts }}"
                   class="mockup-img-link"
                   data-img="{{ url_for('static', filename=full_path) }}?t={{ cache_ts }}">
                  <img 
                    src="{{ url_for('static', filename=thumb_path) }}?t={{ cache_ts }}"
                    onerror="this.onerror=null; this.src='{{ url_for('static', filename=full_path) }}?t={{ cache_ts }}';"
                    class="mockup-thumb-img"
                    alt="Mockup preview {{ loop.index }}">
                </a>
              {% else %}
                <img src="{{ url_for('static', filename='img/default-mockup.jpg') }}" class="mockup-thumb-img" alt="Default mockup placeholder">
              {% endif %}

              {% if categories %}
                <form role="form" method="post" action="{{ url_for('artwork.review_swap_mockup', seo_folder=seo_folder, slot_idx=m.index) }}" class="swap-form">
                  <select name="new_category" aria-label="Swap mockup category for mockup {{ loop.index }}">
                    {% for c in categories %}
                      <option value="{{ c }}" {% if c == m.category %}selected{% endif %}>{{ c }}</option>
                    {% endfor %}
                  </select>
                  <button type="submit" class="btn btn-sm" onclick="swapMockup('{{ m.category }}')">Swap</button>
                </form>
              {% else %}
                <div class="no-categories-warning">No categories found.</div>
              {% endif %}
            </div>
          {% endfor %}
        </div>
      </div>
    </div>

    <div class="col col-6 edit-listing-col">
      <p class="status-line {% if finalised %}status-finalised{% else %}status-pending{% endif %}">
        Status: This artwork is {% if finalised %}<strong>finalised</strong>{% else %}<em>NOT yet finalised</em>{% endif %}
        {% if locked %}<span class="locked-badge">Locked</span>{% endif %}
      </p>

      {% if errors %}
        <div class="flash-error"><ul>{% for e in errors %}<li>{{ e }}</li>{% endfor %}</ul></div>
      {% endif %}

      <form role="form" id="edit-form" method="POST" autocomplete="off">
        <label for="title-input">Title:</label>
        <textarea name="title" id="title-input" rows="2" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.title|e }}</textarea>

        <label for="description-input">Description:</label>
        <textarea name="description" id="description-input" rows="12" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.description|e }}</textarea>

        <label for="tags-input">Tags (comma-separated):</label>
        <textarea name="tags" id="tags-input" rows="2" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.tags|e }}</textarea>

        <label for="materials-input">Materials (comma-separated):</label>
        <textarea name="materials" id="materials-input" rows="2" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.materials|e }}</textarea>

        <div class="row-inline">
          <div class="form-col">
            <label for="primary_colour-select">Primary Colour:</label>
            <select name="primary_colour" id="primary_colour-select" class="long-field" {% if not editable %}disabled{% endif %}>
              {% for col in colour_options %}
                <option value="{{ col }}" {% if artwork.primary_colour==col %}selected{% endif %}>{{ col }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="form-col">
            <label for="secondary_colour-select">Secondary Colour:</label>
            <select name="secondary_colour" id="secondary_colour-select" class="long-field" {% if not editable %}disabled{% endif %}>
              {% for col in colour_options %}
                <option value="{{ col }}" {% if artwork.secondary_colour==col %}selected{% endif %}>{{ col }}</option>
              {% endfor %}
            </select>
          </div>
        </div>

        <label for="seo_filename-input">SEO Filename:</label>
        <input type="text" id="seo_filename-input" class="long-field" name="seo_filename" value="{{ artwork.seo_filename|e }}" {% if not editable %}disabled{% endif %}>

        <div class="price-sku-row">
          <div>
            <label for="price-input">Price:</label>
            <input type="text" id="price-input" name="price" value="{{ artwork.price|e }}" class="long-field" {% if not editable %}disabled{% endif %}>
          </div>
          <div>
            <label for="sku-input">SKU:</label>
            <input type="text" id="sku-input" value="{{ artwork.sku|e }}" class="long-field" readonly disabled>
          </div>
        </div>

        <label for="images-input">Image URLs (one per line):</label>
        <textarea name="images" id="images-input" rows="5" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.images|e }}</textarea>
      </form>

      <div class="edit-actions-col">
        <button form="edit-form" type="submit" name="action" value="save" class="btn btn-primary wide-btn" {% if not editable %}disabled{% endif %}>Save Changes</button>
        <button form="edit-form" type="submit" name="action" value="delete" class="btn btn-danger wide-btn" onclick="return confirm('Delete this artwork and all files?');" {% if not editable %}disabled{% endif %}>Delete</button>
        {% if not finalised %}
          <form role='form' method="post" action="{{ url_for('artwork.finalise_artwork', aspect=aspect, filename=filename) }}" class="action-form">
            <button type="submit" class="btn btn-primary wide-btn">Finalise</button>
          </form>
        {% endif %}
        <form role='form' method="POST" action="{{ url_for('artwork.analyze_artwork', aspect=aspect, filename=filename) }}" class="action-form analyze-form">
          <select name="provider" class="form-select form-select-sm mb-2">
            <option value="openai">OpenAI</option>
            <option value="google">Google</option>
          </select>
          <button type="submit" class="btn btn-primary wide-btn" {% if locked %}disabled{% endif %}>Re-analyse Artwork</button>
        </form>
        {% if finalised and not locked %}
          <form role='form' method="post" action="{{ url_for('artwork.lock_listing', aspect=aspect, filename=filename) }}" class="action-form">
            <button type="submit" class="btn btn-primary wide-btn">Lock it in</button>
          </form>
        {% elif locked %}
          <form role='form' method="post" action="{{ url_for('artwork.unlock_listing', aspect=aspect, filename=filename) }}" class="action-form">
            <button type="submit" class="btn btn-primary wide-btn">Unlock</button>
          </form>
        {% endif %}
        <form role='form' method="post" action="{{ url_for('artwork.reset_sku', aspect=aspect, filename=filename) }}" class="action-form">
          <button type="submit" class="btn-primary wide-btn" {% if locked %}disabled{% endif %}>Reset SKU</button>
        </form>
      </div>

      {% if openai_analysis %}
        <div class="openai-details">
          {% set entries = openai_analysis if openai_analysis is iterable and openai_analysis.__class__ != dict else [openai_analysis] %}
          {% for info in entries %}
            <table class="openai-analysis-table">
              <thead><tr><th colspan="2">OpenAI Analysis Details</th></tr></thead>
              <tbody>
                <tr><th>Original File</th><td>{{ info.original_file }}</td></tr>
                <tr><th>Optimized File</th><td>{{ info.optimized_file }}</td></tr>
                <tr><th>Size</th><td>{{ info.size_mb }} MB ({{ info.size_bytes }} bytes)</td></tr>
                <tr><th>Dimensions</th><td>{{ info.dimensions }}</td></tr>
                <tr><th>Time Sent</th><td>{{ info.time_sent }}</td></tr>
                <tr><th>Time Responded</th><td>{{ info.time_responded }}</td></tr>
                <tr><th>Duration</th><td>{{ info.duration_sec }} s</td></tr>
                <tr><th>Status</th><td>{{ info.status }}</td></tr>
                {% if info.api_response %}<tr><th>API Response</th><td>{{ info.api_response }}</td></tr>{% endif %}
                {% if info.naming_method %}<tr><th>Naming Method</th><td>{{ info.naming_method }}{% if info.used_fallback_naming %} (fallback){% endif %}</td></tr>{% endif %}
              </tbody>
            </table>
          {% endfor %}
        </div>
      {% endif %}
    </div>
  </div>

  <div id="mockup-carousel" class="modal-bg" tabindex="-1">
    <button id="carousel-close" class="modal-close" aria-label="Close">&times;</button>
    <button id="carousel-prev" class="carousel-nav" aria-label="Previous">&#10094;</button>
    <div class="modal-img"><img id="carousel-img" src="" alt="Mockup Preview" /></div>
    <button id="carousel-next" class="carousel-nav" aria-label="Next">&#10095;</button>
  </div>
</div>
<script src="{{ url_for('static', filename='js/edit_listing.js') }}"></script>
{% endblock %}


---
## templates/finalised.html
---
{# Gallery of all finalised artworks with edit and export actions. #}
{% extends "main.html" %}
{% block title %}Finalised Artworks{% endblock %}
{% block content %}
<div class="container">
<div class="page-title-row">
  <img src="{{ url_for('static', filename='icons/svg/light/number-circle-four-light.svg') }}" class="hero-step-icon" alt="Step 4: Finalised" />
  <h1>Finalised Artworks</h1>
</div>
<p class="help-tip">Finalised artworks are ready for publishing or exporting to Sellbrite. You can still edit or delete them here.</p>
<div class="view-toggle">
  <button id="grid-view-btn" class="btn-small">Grid</button>
  <button id="list-view-btn" class="btn-small">List</button>
</div>
<form method="post" action="{{ url_for('exports.run_sellbrite_export') }}">
  <button type="submit" class="btn-black">Export to CSV</button>
</form>
{% if not artworks %}
  <p>No artworks have been finalised yet. Come back after you approve some beautiful pieces!</p>
{% else %}
<div class="finalised-grid" data-view-key="view">
  {% for art in artworks %}
  <div class="final-card">
    <div class="card-thumb">
      {% if art.main_image %}
      <a href="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.main_image) }}" class="final-img-link" data-img="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.main_image) }}">
        <img src="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=art.main_image) }}" class="card-img-top" alt="{{ art.title }}">
      </a>
      {% else %}
      <img src="{{ url_for('static', filename='img/no-image.svg') }}" class="card-img-top" alt="No image">
      {% endif %}
    </div>
    <div class="card-details">
      <div class="card-title">{{ art.title }}{% if art.locked %} <span class="locked-badge">Locked</span>{% endif %}</div>
      <div class="desc-snippet" title="{{ art.description }}">
        {{ art.description[:200] }}{% if art.description|length > 200 %}...{% endif %}
      </div>
      <div>SKU: {{ art.sku }}</div>
      <div>Price: {{ art.price }}</div>
      <div>Colours: {{ art.primary_colour }} / {{ art.secondary_colour }}</div>
      <div>SEO: {{ art.seo_filename }}</div>
      <div>Tags: {{ art.tags|join(', ') }}</div>
      <div>Materials: {{ art.materials|join(', ') }}</div>
      {% if art.mockups %}
      <div class="mini-mockup-grid">
        {% for m in art.mockups %}
        <img src="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=m.filename) }}" alt="mockup"/>
        {% endfor %}
      </div>
      {% endif %}
      {% if art.images %}
      <details class="img-urls">
        <summary>Image URLs</summary>
        <ul>
          {% for img in art.images %}
          <li>
            <a href="{{ url_for('artwork.finalised_image', seo_folder=art.seo_folder, filename=img.split('/')[-1]) }}" target="_blank">/{{ img }}</a>
          </li>
          {% endfor %}
        </ul>
      </details>
      {% endif %}
    </div>
  <div class="button-row">
    {% if art.locked %}
      <a class="art-btn disabled" aria-disabled="true">Edit</a>
      <form method="post" action="{{ url_for('artwork.unlock_listing', aspect=art.aspect, filename=art.filename) }}">
        <button type="submit" class="art-btn">Unlock</button>
      </form>
      <form method="post" action="{{ url_for('artwork.delete_finalised', aspect=art.aspect, filename=art.filename) }}" class="locked-delete-form">
        <input type="hidden" name="confirm" value="">
        <button type="submit" class="art-btn delete">Delete</button>
      </form>
    {% else %}
      <a href="{{ url_for('artwork.edit_listing', aspect=art.aspect, filename=art.filename) }}" class="art-btn">Edit</a>
      <form method="post" action="{{ url_for('artwork.lock_listing', aspect=art.aspect, filename=art.filename) }}">
        <button type="submit" class="art-btn">Lock</button>
      </form>
      <form method="post" action="{{ url_for('artwork.delete_finalised', aspect=art.aspect, filename=art.filename) }}" onsubmit="return confirm('Delete this artwork?');">
        <button type="submit" class="art-btn delete">Delete</button>
      </form>
    {% endif %}
  </div>
  </div>
  {% endfor %}
</div>
{% endif %}
<div id="final-modal-bg" class="modal-bg">
  <button id="final-modal-close" class="modal-close" aria-label="Close modal">&times;</button>
  <div class="modal-img"><img id="final-modal-img" src="" alt="Full image"/></div>
</div>
<script src="{{ url_for('static', filename='js/gallery.js') }}"></script>
</div>
{% endblock %}


---
## templates/gallery.html
---

<div class="container">

</div>

---
## templates/index.html
---
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}ArtNarrator Home{% endblock %}
{% block content %}
<div class="container">

<!-- ========== [IN.1] Home Hero Section ========== -->
<div class="home-hero">
  <h1><img src="{{ url_for('static', filename='logos/logo-vector.svg') }}" alt="" class="artnarrator-logo"/>Welcome to ArtNarrator Listing Machine</h1>
  <p class="home-intro">
    G’day! Start in the Artwork section, analyze new pieces, review your AI-generated listings and mockups, and prep everything for marketplace export—all streamlined for you.
  </p>
</div>

<!-- ========== [IN.2] Home Quick Actions ========== -->
<div class="workflow-row">
  <a href="{{ url_for('artwork.upload_artwork') }}" class="workflow-btn">
    <img src="{{ url_for('static', filename='icons/svg/light/number-circle-one-light.svg') }}" class="step-btn-icon" alt="Step 1" />
    Upload Artwork
  </a>
  <a href="{{ url_for('artwork.artworks') }}" class="workflow-btn">
    <img src="{{ url_for('static', filename='icons/svg/light/number-circle-two-light.svg') }}" class="step-btn-icon" alt="Step 2" />
    Artwork<br>Select to Analyze
  </a>
  {% if latest_artwork %}
    <a href="{{ url_for('artwork.edit_listing', aspect=latest_artwork.aspect, filename=latest_artwork.filename) }}" class="workflow-btn">
      <img src="{{ url_for('static', filename='icons/svg/light/number-circle-three-light.svg') }}" class="step-btn-icon" alt="Step 3" />
      Edit Review<br>and Finalise Artwork
    </a>
  {% else %}
    <span class="workflow-btn disabled">
      <img src="{{ url_for('static', filename='icons/svg/light/number-circle-three-light.svg') }}" class="step-btn-icon" alt="Step 3" />
      Edit Review<br>and Finalise Artwork
    </span>
  {% endif %}
  <a href="{{ url_for('artwork.finalised_gallery') }}" class="workflow-btn">
    <img src="{{ url_for('static', filename='icons/svg/light/number-circle-four-light.svg') }}" class="step-btn-icon" alt="Step 4" />
    Finalised Gallery<br>(Select to List)
  </a>
  <span class="workflow-btn disabled">
    <img src="{{ url_for('static', filename='icons/svg/light/number-circle-five-light.svg') }}" class="step-btn-icon" alt="Step 5" />
    List Artwork<br>(Export to Sellbrite)
  </span>
</div>

<!-- ========== [IN.3] How It Works Section ========== -->
<section class="how-it-works">
  <h2>How It Works</h2>
  <ol>
    <li><b>Upload:</b> Chuck your artwork into the gallery (easy drag & drop).</li>
    <li><b>Analyze:</b> Let the AI do its magic—SEO, titles, pro description, the lot.</li>
    <li><b>Edit & Finalise:</b> Quick review and tweak, fix anything you like.</li>
    <li><b>Mockups:</b> Instantly see your art in bedrooms, offices, nurseries—looks a million bucks.</li>
    <li><b>Final Gallery:</b> See all your finished work, ready for showtime.</li>
    <li><b>Export:</b> Coming soon! Blast your art onto Sellbrite and more with one click.</li>
  </ol>
</section>
</div>
{% endblock %}


---
## templates/locked.html
---
{# Gallery of all finalised artworks with edit and export actions. #}
{% extends "main.html" %}
{% block title %}Locked Artworks{% endblock %}
{% block content %}
<div class="container">
<h1>Locked Artworks</h1>
<p class="help-tip">These artworks are locked and cannot be edited until unlocked.</p>
<div class="view-toggle">
  <button id="grid-view-btn" class="btn-small">Grid</button>
  <button id="list-view-btn" class="btn-small">List</button>
</div>
<form method="post" action="{{ url_for('exports.run_sellbrite_export', locked=1) }}">
  <button type="submit" class="btn-black">Export to CSV</button>
</form>
{% if not artworks %}
  <p>No artworks have been finalised yet. Come back after you approve some beautiful pieces!</p>
{% else %}
<div class="finalised-grid" data-view-key="lockedView">
  {% for art in artworks %}
  <div class="final-card">
    <div class="card-thumb">
      {% if art.main_image %}
      <a href="{{ url_for('artwork.locked_image', seo_folder=art.seo_folder, filename=art.main_image) }}" class="final-img-link" data-img="{{ url_for('artwork.locked_image', seo_folder=art.seo_folder, filename=art.main_image) }}">
        <img src="{{ url_for('artwork.locked_image', seo_folder=art.seo_folder, filename=art.main_image) }}" class="card-img-top" alt="{{ art.title }}">
      </a>
      {% else %}
      <img src="{{ url_for('static', filename='img/no-image.svg') }}" class="card-img-top" alt="No image">
      {% endif %}
    </div>
    <div class="card-details">
      <div class="card-title">{{ art.title }}</div>
      <div class="desc-snippet" title="{{ art.description }}">
        {{ art.description[:200] }}{% if art.description|length > 200 %}...{% endif %}
      </div>
      <div>SKU: {{ art.sku }}</div>
      <div>Price: {{ art.price }}</div>
      <div>Colours: {{ art.primary_colour }} / {{ art.secondary_colour }}</div>
      <div>SEO: {{ art.seo_filename }}</div>
      <div>Tags: {{ art.tags|join(', ') }}</div>
      <div>Materials: {{ art.materials|join(', ') }}</div>
      {% if art.mockups %}
      <div class="mini-mockup-grid">
        {% for m in art.mockups %}
        <img src="{{ url_for('artwork.locked_image', seo_folder=art.seo_folder, filename=m.filename) }}" alt="mockup"/>
        {% endfor %}
      </div>
      {% endif %}
      {% if art.images %}
      <details class="img-urls">
        <summary>Image URLs</summary>
        <ul>
          {% for img in art.images %}
          <li>
            <a href="{{ url_for('artwork.locked_image', seo_folder=art.seo_folder, filename=img.split('/')[-1]) }}" target="_blank">/{{ img }}</a>
          </li>
          {% endfor %}
        </ul>
      </details>
      {% endif %}
    </div>
  <div class="button-row">
    <a class="art-btn disabled" aria-disabled="true">Edit</a>
    <form method="post" action="{{ url_for('artwork.unlock_listing', aspect=art.aspect, filename=art.filename) }}">
      <button type="submit" class="art-btn">Unlock</button>
    </form>
    <form method="post" action="{{ url_for('artwork.delete_finalised', aspect=art.aspect, filename=art.filename) }}" class="locked-delete-form">
      <input type="hidden" name="confirm" value="">
      <button type="submit" class="art-btn delete">Delete</button>
    </form>
  </div>
  </div>
  {% endfor %}
</div>
{% endif %}
<div id="final-modal-bg" class="modal-bg">
  <button id="final-modal-close" class="modal-close" aria-label="Close modal">&times;</button>
  <div class="modal-img"><img id="final-modal-img" src="" alt="Full image"/></div>
</div>
<script src="{{ url_for('static', filename='js/gallery.js') }}"></script>
</div>
{% endblock %}


---
## templates/login.html
---
{% extends "main.html" %}
{% block title %}Login{% endblock %}
{% block content %}
<div class="container">
  <h1>Login</h1>
  {% with msgs = get_flashed_messages(with_categories=true) %}
    {% if msgs %}
      <div class="flash">
        <img src="{{ url_for('static', filename='icons/svg/light/warning-circle-light.svg') }}" alt="!" style="width:20px;margin-right:6px;vertical-align:middle;">
        {% for cat, msg in msgs %}
          {{ msg }}
        {% endfor %}
      </div>
    {% endif %}
  {% endwith %}
  <form method="post" class="login-form">
    <label for="username">Username</label>
    <input id="username" name="username" type="text" required>
    <label for="password">Password</label>
    <input id="password" name="password" type="password" required>
    <button type="submit" class="btn btn-primary wide-btn">Login</button>
  </form>
</div>
{% endblock %}


---
## templates/main.html
---
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script>
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = savedTheme || (prefersDark ? 'dark' : 'light');
        document.documentElement.classList.add('theme-' + theme);
    </script>
    <title>{% block title %}ArtNarrator{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">
    
</head>
<body data-analysis-status-url="{{ url_for('artwork.analysis_status') }}" data-openai-ok="{{ 'true' if openai_configured else 'false' }}" data-google-ok="{{ 'true' if google_configured else 'false' }}">
    <!-- Site Header -->
    <header class="site-header">
        <div class="header-left">
            <a href="{{ url_for('artwork.home') }}" class="site-logo">
                <img src="{{ url_for('static', filename='icons/svg/light/palette-light.svg') }}" alt="" class="logo-icon icon">ArtNarrator
            </a>
        </div>
        <div class="header-center">
            <button id="menu-toggle" class="menu-toggle-btn" aria-label="Open menu">
                Menu
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd"/></svg>
            </button>
        </div>
        <div class="header-right">
            <button id="theme-toggle" class="theme-toggle-btn" aria-label="Toggle theme">
                <svg class="sun-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.106a.75.75 0 011.06-1.06l1.591 1.59a.75.75 0 01-1.06 1.06l-1.59-1.59zM21.75 12a.75.75 0 01-.75.75h-2.25a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.894 17.894a.75.75 0 01-1.06 1.06l-1.59-1.591a.75.75 0 111.06-1.06l1.59 1.59zM12 18.75a.75.75 0 01-.75.75v2.25a.75.75 0 011.5 0V19.5a.75.75 0 01-.75-.75zM6.106 18.894a.75.75 0 01-1.06-1.06l1.59-1.59a.75.75 0 011.06 1.06l-1.59 1.59zM3.75 12a.75.75 0 01.75-.75h2.25a.75.75 0 010 1.5H4.5a.75.75 0 01-.75-.75zM6.106 5.046a.75.75 0 011.06 1.06l-1.59 1.591a.75.75 0 01-1.06-1.06l1.59-1.59z"/></svg>
                <svg class="moon-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" d="M9.528 1.718a.75.75 0 01.162.819A8.97 8.97 0 009 6a9 9 0 009 9 8.97 8.97 0 003.463-.69a.75.75 0 001.981.981A10.503 10.503 0 0118 18a10.5 10.5 0 01-10.5-10.5c0-1.25.22-2.454.622-3.574a.75.75 0 01.806-.162z" clip-rule="evenodd"/></svg>
            </button>
        </div>
    </header>

    <!-- Overlay Menu -->
    <div id="overlay-menu" class="overlay-menu">
        <div class="overlay-header">
            <div class="header-left">
                <a href="{{ url_for('artwork.home') }}" class="site-logo">
                    <img src="{{ url_for('static', filename='icons/svg/light/palette-light.svg') }}" alt="" class="logo-icon icon">ArtNarrator
                </a>
            </div>
            <div class="header-center">
                <button id="menu-close" class="menu-close-btn" aria-label="Close menu">
                    Close
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M14.78 11.78a.75.75 0 0 1-1.06 0L10 8.06l-3.72 3.72a.75.75 0 1 1-1.06-1.06l4.25-4.25a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06Z" clip-rule="evenodd"/></svg>
                </button>
            </div>
            <div class="header-right"></div>
        </div>
        <nav class="overlay-nav">
            <div class="nav-column">
                <h3>Artwork &amp; Gallery</h3>
                <ul>
                    <li><a href="{{ url_for('artwork.upload_artwork') }}">Upload Artwork</a></li>
                    <li><a href="{{ url_for('artwork.artworks') }}">All Artworks</a></li>
                    <li><a href="{{ url_for('artwork.finalised_gallery') }}">Finalised</a></li>
                    <li><a href="{{ url_for('artwork.locked_gallery') }}">Locked</a></li>
                </ul>
            </div>
            <div class="nav-column">
                <h3>Workflow &amp; Tools</h3>
                <ul>
                    <li><a href="{{ url_for('artwork.select') }}">Composites Preview</a></li>
                    <li><a href="{{ url_for('mockup_admin.dashboard') }}">Mockup Admin</a></li> </ul>
                    <li><a href="{{ url_for('coordinate_admin.dashboard') }}">Coordinate Generator</a></li> </ul>
                    <li><a href="{{ url_for('artwork.select') }}">Mockup Selector</a></li>
                </ul>
            </div>
            <div class="nav-column">
                <h3>Exports &amp; Admin</h3>
                <ul>
                    <li><a href="{{ url_for('exports.sellbrite_exports') }}">Sellbrite Exports</a></li>
                    <li><a href="{{ url_for('admin.dashboard') }}">Admin Dashboard</a></li>
                    <li><a href="{{ url_for('admin.security_page') }}">Admin Security</a></li>
                    <li><a href="{{ url_for('gdws_admin.editor') }}">Description Editor (GDWS)</a></li>
                    <li><a href="{{ url_for('auth.login') }}">Login</a></li>
                </ul>
            </div>
        </nav>
    </div>

    <!-- Main Content -->
    <main>
        <div class="container">
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    <div class="flash">
                        {% for m in messages %}{{ m }}{% endfor %}
                    </div>
                {% endif %}
            {% endwith %}
            {% block content %}{% endblock %}
        </div>
    </main>

    <!-- Gemini Modal -->
    <div id="gemini-modal" class="gemini-modal">
        <div class="gemini-modal-content">
            <span class="gemini-modal-close">&times;</span>
            <h3 id="gemini-modal-title">AI Generation</h3>
            <div id="gemini-modal-body" class="gemini-modal-body"></div>
            <div class="gemini-modal-actions">
                <button id="gemini-copy-btn" class="btn-action">Copy</button>
            </div>
        </div>
    </div>

    <!-- Analysis Progress Modal -->
    <div id="analysis-modal" class="analysis-modal" role="dialog" aria-modal="true">
        <div class="analysis-box" tabindex="-1">
            <button id="analysis-close" class="modal-close" aria-label="Close">&times;</button>
            <img src="{{ url_for('static', filename='icons/svg/light/palette-light.svg') }}" class="progress-icon" alt="">
            <h3>Analyzing Artwork...</h3>
            <div class="analysis-progress" aria-label="analysis progress">
                <div id="analysis-bar" class="analysis-progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
            </div>
            <div id="analysis-status" class="analysis-status" aria-live="polite"></div>
            <div class="analysis-friendly">This can take up to a couple of minutes. Go have a coffee while the AI works its magic! ☕️</div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="site-footer">
        <div class="footer-grid">
            <div class="footer-column">
                <h4>Navigate</h4>
                <ul>
                    <li><a href="{{ url_for('artwork.home') }}">Home</a></li>
                    <li><a href="{{ url_for('auth.login') }}">Login</a></li>
                </ul>
            </div>
            <div class="footer-column">
                <h4>Artwork &amp; Gallery</h4>
                <ul>
                    <li><a href="{{ url_for('artwork.upload_artwork') }}">Upload Artwork</a></li>
                    <li><a href="{{ url_for('artwork.artworks') }}">Artworks</a></li>
                    <li><a href="{{ url_for('artwork.finalised_gallery') }}">Finalised</a></li>
                    <li><a href="{{ url_for('artwork.locked_gallery') }}">Locked</a></li>
                </ul>
            </div>
            <div class="footer-column">
                <h4>Workflow &amp; Tools</h4>
                <ul>
                    <li><a href="{{ url_for('artwork.select') }}">Composites Preview</a></li>
                    <li><a href="{{ url_for('artwork.select') }}">Mockups</a></li>
                </ul>
            </div>
            <div class="footer-column">
                <h4>Exports &amp; Admin</h4>
                <ul>
                    <li><a href="{{ url_for('exports.sellbrite_exports') }}">Sellbrite Exports</a></li>
                    <li><a href="{{ url_for('admin.dashboard') }}">Admin Dashboard</a></li>
                    <li><a href="{{ url_for('admin.security_page') }}">Admin Security</a></li>
                    <li><a href="{{ url_for('gdws_admin.editor') }}">Description Editor (GDWS)</a></li>
                    {# Removed broken menu link: Admin Users (no such route exists) #}
                </ul>
            </div>
        </div>
        <div class="copyright-bar">
            © Copyright 2025 ART Narrator All rights reserved | <a href="https://artnarrator.com">artnarrator.com</a> designed and built by Robin Custance.
        </div>
    </footer>

    <!-- JavaScript -->
    <script src="{{ url_for('static', filename='js/main-overlay-test.js') }}"></script>
    <script src="{{ url_for('static', filename='js/analysis-modal.js') }}"></script>
</body>
</html>


---
## templates/missing_endpoint.html
---
{% extends "main.html" %}
{% block title %}Invalid Link{% endblock %}
{% block content %}
<div class="container" style="text-align: center;">
    <h1>Oops! A Link is Broken</h1>
    <p>The link or button you clicked points to a page that doesn't exist.</p>
    <p>This is usually a small typo in the code. I've logged the details so it can be fixed.</p>
    <div style="background: #eee; color: #333; padding: 1em; margin: 1em 0; text-align: left; font-family: monospace;">
        <strong>Error Details:</strong><br>
        {{ error }}
    </div>
    <a href="{{ url_for('artwork.home') }}" class="btn btn-primary">Return to Homepage</a>
</div>
{% endblock %}

---
## templates/mockup_selector.html
---
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}Select Mockups | ArtNarrator{% endblock %}
{% block content %}
<div class="container">
<h1>🖼️ Select Your Mockup Lineup</h1>
<div class="grid">
  {% for slot, options in zipped %}
  <div class="item">
    {% if slot.image %}
      <img src="{{ url_for('artwork.mockup_img', category=slot.category, filename=slot.image) }}" alt="{{ slot.category }}" />
    {% else %}
      <p>No images for {{ slot.category }}</p>
    {% endif %}
    <strong>{{ slot.category }}</strong>
    <form method="post" action="{{ url_for('artwork.regenerate') }}">
      <input type="hidden" name="slot" value="{{ loop.index0 }}" />
      <button type="submit">🔄 Regenerate</button>
    </form>
    <form method="post" action="{{ url_for('artwork.swap') }}">
      <input type="hidden" name="slot" value="{{ loop.index0 }}" />
      <select name="new_category">
        <!-- DEBUG: Options for slot {{ loop.index0 }}: {{ options|join(", ") }} -->
        {% for c in options %}
        <option value="{{ c }}" {% if c == slot.category %}selected{% endif %}>{{ c }}</option>
        {% endfor %}
      </select>
      <button type="submit">🔁 Swap</button>
    </form>
  </div>
  {% endfor %}
</div>
<form method="post" action="{{ url_for('artwork.proceed') }}">
  <button class="composite-btn" type="submit">✅ Generate Composites</button>
</form>
<div style="text-align:center;margin-top:1em;">
  {% if session.latest_seo_folder %}
    <a href="{{ url_for('artwork.composites_specific', seo_folder=session.latest_seo_folder) }}" class="composite-btn" style="background:#666;">👁️ Preview Composites</a>
  {% else %}
    <a href="{{ url_for('artwork.composites_preview') }}" class="composite-btn" style="background:#666;">👁️ Preview Composites</a>
  {% endif %}
</div>
</div>
{% endblock %}


---
## templates/review.html
---
{# Use blueprint-prefixed endpoints like 'artwork.home' in url_for #}
{% extends "main.html" %}
{% block title %}Review | ArtNarrator{% endblock %}
{% block content %}
<div class="container">
<h1>Review &amp; Approve Listing</h1>
<section class="review-artwork">
  <h2>{{ artwork.title }}</h2>
  <div class="artwork-images">
    <img src="{{ url_for('static', filename='outputs/processed/' ~ artwork.seo_name ~ '/' ~ artwork.main_image) }}"
         alt="Main artwork" class="main-art-img" style="max-width:360px;">
    <img src="{{ url_for('static', filename='outputs/processed/' ~ artwork.seo_name ~ '/' ~ artwork.thumb) }}"
         alt="Thumbnail" class="thumb-img" style="max-width:120px;">
  </div>
  <h3>Description</h3>
  <div class="art-description" style="max-width:431px;">
    <pre style="white-space: pre-wrap; font-family:inherit;">{{ artwork.description }}</pre>
  </div>
  <h3>Mockups</h3>
  <div class="grid">
    {% for slot in slots %}
    <div class="item">
      <img src="{{ url_for('artwork.mockup_img', category=slot.category, filename=slot.image) }}" alt="{{ slot.category }}">
      <strong>{{ slot.category }}</strong>
    </div>
    {% endfor %}
  </div>
</section>
<form method="get" action="{{ url_for('artwork.select') }}">
  <input type="hidden" name="reset" value="1">
  <button class="composite-btn" type="submit">Start Over</button>
</form>
<div style="text-align:center;margin-top:1.5em;">
  <a href="{{ url_for('artwork.composites_specific', seo_folder=artwork.seo_name) }}" class="composite-btn" style="background:#666;">Preview Composites</a>
</div>
</div>
{% endblock %}


---
## templates/sellbrite_csv_preview.html
---
{% extends "main.html" %}
{% block title %}Preview {{ csv_filename }}{% endblock %}
{% block content %}
<div class="container">
<h1>Preview {{ csv_filename }}</h1>
<p><a class="btn-black" href="{{ url_for('exports.download_sellbrite', csv_filename=csv_filename) }}">Download Full CSV</a></p>
<div class="csv-preview">
  <table class="exports-table">
    <thead>
      <tr>
        {% for h in header %}<th>{{ h }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
      {% endfor %}
    </tbody>
  </table>
</div>
</div>
{% endblock %}


---
## templates/sellbrite_exports.html
---
{% extends "main.html" %}
{% block title %}Sellbrite Exports{% endblock %}
{% block content %}
<div class="container">
<h1>Sellbrite Exports</h1>
<p class="help-tip">Review all previous exports below. Warnings show missing fields or short descriptions.</p>
<div class="export-actions">
  <form method="post" action="{{ url_for('exports.run_sellbrite_export') }}" style="display:inline">
    <button type="submit" class="btn-black">Export Now (All)</button>
  </form>
  <form method="post" action="{{ url_for('exports.run_sellbrite_export', locked=1) }}" style="display:inline">
    <button type="submit" class="btn-black">Export Now (Locked)</button>
  </form>
</div>
<table class="exports-table">
  <thead>
    <tr><th>Date</th><th>Type</th><th>CSV</th><th>Preview</th><th>Log</th></tr>
  </thead>
  <tbody>
  {% for e in exports %}
    <tr>
      <td>{{ e.mtime.strftime('%Y-%m-%d %H:%M') }}</td>
      <td>{{ e.type }}</td>
      <td><a href="{{ url_for('exports.download_sellbrite', csv_filename=e.name) }}">{{ e.name }}</a></td>
      <td><a href="{{ url_for('exports.preview_sellbrite_csv', csv_filename=e.name) }}">Preview</a></td>
      <td>{% if e.log %}<a href="{{ url_for('exports.view_sellbrite_log', log_filename=e.log) }}">Log</a>{% else %}-{% endif %}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endblock %}


---
## templates/sellbrite_log.html
---
{% extends "main.html" %}
{% block title %}Export Log{% endblock %}
{% block content %}
<div class="container">
<h1>Export Log {{ log_filename }}</h1>
<pre class="export-log">{{ log_text }}</pre>
</div>
{% endblock %}


---
## templates/test_description.html
---
{% extends "main.html" %}
{% block title %}Test Combined Description{% endblock %}
{% block content %}
<div class="container">
<h1>Test Combined Description</h1>
<div class="desc-text" style="white-space: pre-wrap;border:1px solid #ccc;padding:10px;">
  {{ combined_description }}
</div>
</div>
{% endblock %}


---
## templates/upload.html
---
{% extends "main.html" %}
{% block title %}Upload Artwork{% endblock %}
{% block content %}
<div class="container">
  <div class="home-hero" >
    <h1><img src="{{ url_for('static', filename='icons/svg/light/number-circle-one-light.svg') }}" class="hero-step-icon" alt="Step 1: Upload" />Upload New Artwork</h1>
  </div>
  <form id="upload-form" method="post" enctype="multipart/form-data">
    <input id="file-input" type="file" name="images" accept="image/*" multiple hidden>
    <div id="dropzone" class="upload-dropzone">
      Drag & Drop images here or click to choose files
    </div>
    <ul id="upload-list" class="upload-list"></ul>
  </form>
</div>

<div id="upload-modal" class="analysis-modal" role="dialog" aria-modal="true">
  <div class="analysis-box" tabindex="-1">
    <img src="{{ url_for('static', filename='icons/svg/light/upload-light.svg') }}" class="progress-icon" alt="">
    <h3>Uploading...</h3>
    <div id="upload-filename" style="margin-bottom: 0.5em; font-size: 0.9em; color: #555;"></div>
    <div class="analysis-progress" aria-label="upload progress">
        <div id="upload-bar" class="analysis-progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
    </div>
    <div id="upload-status" class="analysis-status" aria-live="polite">0%</div>
  </div>
</div>

<script src="{{ url_for('static', filename='js/upload.js') }}"></script>
{% endblock %}

---
## templates/upload_results.html
---
{% extends "main.html" %}
{% block title %}Upload Results{% endblock %}
{% block content %}
<div class="container">
<h2 class="mb-3">Upload Summary</h2>
<ul>
  {% for r in results %}
    <li>{% if r.success %}✅ {{ r.original }}{% else %}❌ {{ r.original }}: {{ r.error }}{% endif %}</li>
  {% endfor %}
</ul>
<a href="{{ url_for('artwork.artworks') }}" class="btn btn-primary">Return to Gallery</a>
</div>
{% endblock %}


---
## tests/test_admin_security.py
---
import os
import sys
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("OPENAI_API_KEY", "test")


def setup_app(tmp_path):
    os.environ['LOGS_DIR'] = str(tmp_path / 'logs')
    os.environ['DATA_DIR'] = str(tmp_path / 'data')
    for mod in ('config', 'db', 'utils.security', 'utils.user_manager', 'routes.auth_routes', 'routes.admin_security', 'app'):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    if 'app' not in sys.modules:
        import app  # type: ignore
    app_module = importlib.import_module('app')
    return app_module.app


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)


def test_role_required_admin(tmp_path):
    app = setup_app(tmp_path)
    client = app.test_client()
    resp = login(client, 'viewer', 'viewer123')
    assert resp.status_code == 302
    resp = client.get('/admin/', follow_redirects=False)
    assert resp.status_code == 302
    client.get('/logout')
    resp = login(client, 'robbie', 'kangaroo123')
    assert resp.status_code == 302
    resp = client.get('/admin/', follow_redirects=False)
    assert resp.status_code == 200


def test_no_cache_header(tmp_path):
    app = setup_app(tmp_path)
    client = app.test_client()
    admin_login = login(client, 'robbie', 'kangaroo123')
    assert admin_login.status_code == 302
    client.post('/admin/security', data={'action': 'nocache_on', 'minutes': '1'})
    resp = client.get('/')
    assert resp.headers.get('Cache-Control') == 'no-store, no-cache, must-revalidate, max-age=0'


def test_login_lockout(tmp_path):
    app = setup_app(tmp_path)
    client = app.test_client()
    admin_login = login(client, 'robbie', 'kangaroo123')
    assert admin_login.status_code == 302
    client.post('/admin/security', data={'action': 'disable', 'minutes': '1'})
    client.get('/logout')
    resp = login(client, 'viewer', 'viewer123')
    assert resp.status_code == 403



---
## tests/test_analysis_status_file.py
---
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes.utils import load_json_file_safe


def test_load_json_file_safe_missing(tmp_path, caplog):
    test_file = tmp_path / 'missing.json'
    with caplog.at_level(logging.WARNING):
        data = load_json_file_safe(test_file)
    assert data == {}
    assert test_file.exists()
    assert test_file.read_text() == '{}'
    assert 'created new empty file' in caplog.text


def test_load_json_file_safe_empty(tmp_path, caplog):
    test_file = tmp_path / 'empty.json'
    test_file.write_text('   ')
    with caplog.at_level(logging.WARNING):
        data = load_json_file_safe(test_file)
    assert data == {}
    assert test_file.read_text() == '{}'
    assert 'reset to {}' in caplog.text


def test_load_json_file_safe_invalid(tmp_path, caplog):
    test_file = tmp_path / 'invalid.json'
    test_file.write_text('{bad json')
    with caplog.at_level(logging.ERROR):
        data = load_json_file_safe(test_file)
    assert data == {}
    assert test_file.read_text() == '{}'
    assert 'Invalid JSON' in caplog.text


def test_load_json_file_safe_valid(tmp_path):
    test_file = tmp_path / 'valid.json'
    content = {'a': 1}
    test_file.write_text(json.dumps(content))
    data = load_json_file_safe(test_file)
    assert data == content


---
## tests/test_analyze_api.py
---
import io
import json
from pathlib import Path
from PIL import Image
import sys
import os

os.environ.setdefault("OPENAI_API_KEY", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config
from unittest import mock
from utils import session_tracker
import routes.utils as routes_utils


def test_analyze_api_json(tmp_path):
    client = app.test_client()
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    client.post(
        "/login",
        data={"username": "robbie", "password": "kangaroo123"},
        follow_redirects=True,
    )
    # Ensure an image exists in the unanalysed folder
    config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    img_path = config.UNANALYSED_ROOT / "dummy.jpg"
    Image.new("RGB", (10, 10), "blue").save(img_path)

    seo_folder = "dummy-artwork"
    processed_dir = tmp_path
    listing_path = processed_dir / f"{seo_folder}-listing.json"
    listing_path.write_text(json.dumps({"title": "t"}))

    dummy_entry = {
        "seo_name": seo_folder,
        "processed_folder": str(processed_dir),
    }

    with mock.patch(
        "routes.artwork_routes._run_ai_analysis", return_value=dummy_entry
    ), mock.patch("routes.artwork_routes._generate_composites"), mock.patch(
        "routes.artwork_routes.utils.find_aspect_filename_from_seo_folder",
        return_value=("square", f"{seo_folder}.jpg"),
    ):
        resp = client.post(
            "/analyze-openai/dummy.jpg",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"]


def test_analyze_api_strip_bytes(tmp_path, monkeypatch):
    client = app.test_client()
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    client.post(
        "/login",
        data={"username": "robbie", "password": "kangaroo123"},
        follow_redirects=True,
    )
    config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    img_path = config.UNANALYSED_ROOT / "byte.jpg"
    Image.new("RGB", (10, 10), "blue").save(img_path)

    seo_folder = "byte-art"
    processed_dir = tmp_path
    (processed_dir / f"{seo_folder}-listing.json").write_text("{}")

    dummy_entry = {
        "seo_name": seo_folder,
        "processed_folder": str(processed_dir),
        "blob": b"bigdata",
    }

    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(routes_utils, "LOGS_DIR", tmp_path)

    with mock.patch(
        "routes.artwork_routes._run_ai_analysis", return_value=dummy_entry
    ), mock.patch("routes.artwork_routes._generate_composites"), mock.patch(
        "routes.artwork_routes.utils.find_aspect_filename_from_seo_folder",
        return_value=("square", f"{seo_folder}.jpg"),
    ):
        resp = client.post(
            "/analyze-openai/byte.jpg",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert "blob" not in json.dumps(data)


def test_analyze_api_error_bytes(tmp_path, monkeypatch):
    client = app.test_client()
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    client.post(
        "/login",
        data={"username": "robbie", "password": "kangaroo123"},
        follow_redirects=True,
    )
    config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    img_path = config.UNANALYSED_ROOT / "err.jpg"
    Image.new("RGB", (10, 10), "blue").save(img_path)

    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(routes_utils, "LOGS_DIR", tmp_path)

    with mock.patch(
        "routes.artwork_routes._run_ai_analysis", side_effect=RuntimeError(b"oops")
    ), mock.patch("routes.artwork_routes._generate_composites"), mock.patch(
        "routes.artwork_routes.utils.find_aspect_filename_from_seo_folder",
        return_value=("square", "err.jpg"),
    ):
        resp = client.post(
            "/analyze-openai/err.jpg",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )

    assert resp.status_code == 500
    text = resp.get_data(as_text=True)
    assert "oops" not in text
    assert "b'" not in text


---
## tests/test_analyze_artwork.py
---
import json
import os
from pathlib import Path
import sys
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "scripts"))
from config import UNANALYSED_ROOT
from unittest import mock
os.environ.setdefault("OPENAI_API_KEY", "test")
import analyze_artwork as aa


def dummy_openai_response(content):
    class Choice:
        def __init__(self, text):
            self.message = type('m', (), {'content': text})
    class Resp:
        def __init__(self, text):
            self.choices = [Choice(text)]
    return Resp(content)


def run_test():
    sample_json = json.dumps({
        "seo_filename": "test-artwork-by-robin-custance-rjc-0001.jpg",
        "title": "Test Artwork – High Resolution Digital Aboriginal Print",
        "description": "Test description " * 50,
        "tags": ["test", "digital art"],
        "materials": ["Digital artwork", "High resolution JPEG file"],
        "primary_colour": "Black",
        "secondary_colour": "Brown"
    })
    with mock.patch.object(aa.client.chat.completions, 'create', return_value=dummy_openai_response(sample_json)):
        system_prompt = aa.read_onboarding_prompt()
        img = next(UNANALYSED_ROOT.rglob('*.jpg'))
        status = []
        entry = aa.analyze_single(img, system_prompt, None, status)
        print(json.dumps(entry, indent=2)[:200])


if __name__ == '__main__':
    run_test()



---
## tests/test_logger_utils.py
---
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from utils.logger_utils import log_action


def test_log_action_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    log_action("upload", "test.jpg", "alice", "uploaded test.jpg")
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H")
    log_file = tmp_path / "upload" / f"{stamp}.log"
    assert log_file.exists()
    text = log_file.read_text()
    assert "user: alice" in text
    assert "action: upload" in text
    assert "file: test.jpg" in text
    assert "status: success" in text


def test_log_action_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    log_action("upload", "bad.jpg", None, "failed", status="fail", error="oops")
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H")
    log_file = tmp_path / "upload" / f"{stamp}.log"
    lines = log_file.read_text().strip().splitlines()
    assert any("status: fail" in l for l in lines)
    assert any("error: oops" in l for l in lines)


---
## tests/test_registry.py
---
import os
import importlib
import json
from pathlib import Path
import sys


def test_move_and_registry(tmp_path, monkeypatch):
    monkeypatch.setenv('ART_PROCESSING_DIR', str(tmp_path / 'ap'))
    monkeypatch.setenv('OUTPUT_JSON', str(tmp_path / 'ap' / 'reg.json'))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import config
    importlib.reload(config)
    from routes import utils
    importlib.reload(utils)

    folder = utils.create_unanalysed_subfolder()
    dummy = folder / 'img.jpg'
    dummy.write_text('x')
    uid = 'u1'
    utils.register_new_artwork(uid, 'img.jpg', folder, ['img.jpg'], 'unanalysed', 'img')

    dest = Path(tmp_path / 'processed' / 'img.jpg')
    utils.move_and_log(dummy, dest, uid, 'processed')

    assert not dummy.exists()
    assert dest.exists()
    reg = json.loads(Path(config.OUTPUT_JSON).read_text())
    rec = reg[uid]
    assert rec['status'] == 'processed'
    assert dest.name in rec['assets']

    vault = Path(tmp_path / 'vault')
    vault.mkdir()
    utils.update_status(uid, vault, 'vault')
    reg = json.loads(Path(config.OUTPUT_JSON).read_text())
    assert reg[uid]['status'] == 'vault'



---
## tests/test_routes.py
---
import re
from html.parser import HTMLParser
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href":
                    self.links.append(v)

def collect_template_endpoints():
    pattern = re.compile(r"url_for\(['\"]([^'\"]+)['\"]")
    endpoints = set()
    for path in config.TEMPLATES_DIR.rglob('*.html'):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        endpoints.update(pattern.findall(content))
    return endpoints

def test_template_endpoints_valid():
    registered = {r.endpoint for r in app.url_map.iter_rules()}
    templated = collect_template_endpoints()
    missing = [e for e in templated if e not in registered and not e.startswith('static')]
    assert not missing, f"Unknown endpoints referenced: {missing}"

def test_routes_and_navigation():
    client = app.test_client()
    client.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=True)
    to_visit = ['/']
    visited = set()
    while to_visit:
        url = to_visit.pop()
        if url in visited:
            continue
        resp = client.get(url)
        if url == '/logout' and resp.status_code == 302:
            continue
        if url == '/composites' and resp.status_code == 302:
            resp = client.get(resp.headers['Location'])
        assert resp.status_code == 200, f"Failed loading {url}"
        visited.add(url)
        parser = LinkParser()
        parser.feed(resp.get_data(as_text=True))
        for link in parser.links:
            if link.startswith('http') or link.startswith('mailto:'):
                continue
            if link.startswith('/static') or '//' in link[1:]:
                continue
            if link == '#' or link.startswith('#') or link == '/logout':
                continue
            link = link.split('?')[0]
            if link not in visited:
                to_visit.append(link)


---
## tests/test_session_limits.py
---
import os
import sys
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ["ADMIN_USERNAME"] = "robbie"
os.environ["ADMIN_PASSWORD"] = "kangaroo123"


def setup_app(tmp_path):
    os.environ['LOGS_DIR'] = str(tmp_path / 'logs')
    for mod in ('config', 'utils.session_tracker', 'routes.auth_routes', 'app'):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    if 'app' not in sys.modules:
        import app  # type: ignore
    app_module = importlib.import_module('app')
    return app_module.app


def test_session_limit_enforced(tmp_path):
    app = setup_app(tmp_path)
    clients = []
    for _ in range(5):
        c = app.test_client()
        resp = c.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=True)
        assert resp.status_code == 200
        clients.append(c)
    extra = app.test_client()
    resp = extra.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=False)
    assert resp.status_code == 403
    assert b'Maximum login limit' in resp.data

    clients[0].get('/logout', follow_redirects=True)
    resp = extra.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=True)
    assert resp.status_code == 200


---
## tests/test_sku_assigner.py
---
import json
from pathlib import Path

from utils.sku_assigner import get_next_sku, peek_next_sku


def test_peek_does_not_increment(tmp_path):
    tracker = tmp_path / "tracker.json"
    tracker.write_text(json.dumps({"last_sku": 2}))
    peek = peek_next_sku(tracker)
    assert peek == "RJC-0003"
    assert json.loads(tracker.read_text())['last_sku'] == 2


def test_get_next_sku_increments(tmp_path):
    tracker = tmp_path / "tracker.json"
    tracker.write_text(json.dumps({"last_sku": 10}))
    first = get_next_sku(tracker)
    second = get_next_sku(tracker)
    assert first == "RJC-0011"
    assert second == "RJC-0012"
    assert json.loads(tracker.read_text())['last_sku'] == 12


def test_cancel_does_not_consume(tmp_path):
    tracker = tmp_path / "tracker.json"
    tracker.write_text(json.dumps({"last_sku": 5}))
    preview = peek_next_sku(tracker)
    assert preview == "RJC-0006"
    # no assignment yet
    assert json.loads(tracker.read_text())['last_sku'] == 5
    final = get_next_sku(tracker)
    assert final == preview
    assert json.loads(tracker.read_text())['last_sku'] == 6


---
## tests/test_sku_tracker.py
---
import json
import os
import shutil
from pathlib import Path
import sys
from PIL import Image
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("SKU_TRACKER_PATH", str(Path("/tmp/sku_tracker_default.json")))
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "scripts"))
from config import UNANALYSED_ROOT, PROCESSED_ROOT
from unittest import mock
import analyze_artwork as aa
from routes import utils


class DummyChoice:
    def __init__(self, text):
        self.message = type('m', (), {'content': text})

class DummyResp:
    def __init__(self, text):
        self.choices = [DummyChoice(text)]


SAMPLE_JSON1 = json.dumps({
    "title": "First Artwork",
    "description": "Test description",
    "tags": ["tag"],
    "materials": ["mat"],
    "primary_colour": "Black",
    "secondary_colour": "Brown"
})

SAMPLE_JSON2 = json.dumps({
    "title": "Second Artwork",
    "description": "Test description",
    "tags": ["tag"],
    "materials": ["mat"],
    "primary_colour": "Black",
    "secondary_colour": "Brown"
})


def test_sequential_sku_assignment(tmp_path):
    tracker = tmp_path / 'sku_tracker.json'
    tracker.write_text(json.dumps({"last_sku": 80}))
    os.environ['SKU_TRACKER_PATH'] = str(tracker)
    aa.SKU_TRACKER = Path(os.environ['SKU_TRACKER_PATH'])

    # remove any pre-existing output folders from previous runs
    for folder in ('first-artwork', 'second-artwork'):
        shutil.rmtree(PROCESSED_ROOT / folder, ignore_errors=True)

    img_iter = UNANALYSED_ROOT.rglob('*.jpg')
    img_src = next(img_iter, None)
    if img_src is None:
        UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
        img_src = UNANALYSED_ROOT / 'sample.jpg'
        Image.new('RGB', (10, 10), 'red').save(img_src)
    img1 = tmp_path / 'a.jpg'
    img2 = tmp_path / 'b.jpg'
    shutil.copy2(img_src, img1)
    shutil.copy2(img_src, img2)

    responses = [DummyResp(SAMPLE_JSON1), DummyResp(SAMPLE_JSON2)]
    with mock.patch.object(aa.client.chat.completions, 'create', side_effect=responses):
        system_prompt = aa.read_onboarding_prompt()
        status = []
        entry1 = aa.analyze_single(img1, system_prompt, None, status)
        entry2 = aa.analyze_single(img2, system_prompt, None, status)

    # Analysis stage only previews the next SKU
    assert entry1['sku'] == 'RJC-0081'
    assert entry2['sku'] == 'RJC-0081'
    assert json.loads(tracker.read_text())['last_sku'] == 80

    # Finalising assigns sequential SKUs
    utils.assign_or_get_sku(Path(entry1['processed_folder']) / f"{entry1['seo_name']}-listing.json", tracker, force=True)
    utils.assign_or_get_sku(Path(entry2['processed_folder']) / f"{entry2['seo_name']}-listing.json", tracker, force=True)

    assert json.loads(tracker.read_text())['last_sku'] == 82

    with mock.patch.object(aa.client.chat.completions, 'create', return_value=DummyResp(SAMPLE_JSON1)):
        system_prompt = aa.read_onboarding_prompt()
        status = []
        shutil.copy2(img_src, img1)
        entry1b = aa.analyze_single(img1, system_prompt, None, status)

    assert entry1b['sku'] == 'RJC-0081'


---
## tests/test_sku_utils.py
---
import json
from pathlib import Path
from routes import utils


def test_assign_or_get_sku(tmp_path):
    tracker = tmp_path / 'sku.json'
    tracker.write_text(json.dumps({"last_sku": 5}))
    listing = tmp_path / 'art-listing.json'
    listing.write_text(json.dumps({"title": "Test"}))

    sku = utils.assign_or_get_sku(listing, tracker)
    assert sku == 'RJC-0006'
    assert json.loads(listing.read_text())['sku'] == sku
    assert json.loads(tracker.read_text())['last_sku'] == 6

    # Calling again should keep same SKU
    sku2 = utils.assign_or_get_sku(listing, tracker)
    assert sku2 == sku
    assert json.loads(tracker.read_text())['last_sku'] == 6


def test_assign_sku_updates_seo_filename(tmp_path):
    tracker = tmp_path / 'sku.json'
    tracker.write_text(json.dumps({"last_sku": 1}))
    listing = tmp_path / 'listing.json'
    listing.write_text(json.dumps({
        "title": "Test",
        "seo_filename": "Test-Artwork-by-Robin-Custance-RJC-0000.jpg"
    }))

    sku = utils.assign_or_get_sku(listing, tracker)
    data = json.loads(listing.read_text())
    assert sku == 'RJC-0002'
    assert data['sku'] == sku
    assert data['seo_filename'].endswith(f"{sku}.jpg")

    sku2 = utils.assign_or_get_sku(listing, tracker)
    data2 = json.loads(listing.read_text())
    assert sku2 == sku
    assert data2['seo_filename'].endswith(f"{sku}.jpg")
    assert json.loads(tracker.read_text())['last_sku'] == 2


def test_validate_all_skus(tmp_path):
    tracker = tmp_path / 'sku.json'
    tracker.write_text(json.dumps({"last_sku": 2}))

    good = [{"sku": "RJC-0001"}, {"sku": "RJC-0002"}]
    assert utils.validate_all_skus(good, tracker) == []

    dup = [{"sku": "RJC-0001"}, {"sku": "RJC-0001"}]
    assert any('Duplicate' in e for e in utils.validate_all_skus(dup, tracker))

    gap = [{"sku": "RJC-0001"}, {"sku": "RJC-0003"}]
    assert any('Gap' in e for e in utils.validate_all_skus(gap, tracker))

    missing = [{}, {"sku": "RJC-0002"}]
    assert any('invalid' in e for e in utils.validate_all_skus(missing, tracker))


---
## tests/test_upload.py
---
import io
import json
from pathlib import Path
import os
import sys
from PIL import Image
os.environ.setdefault("OPENAI_API_KEY", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config
import scripts.analyze_artwork as aa
from unittest import mock
from utils import session_tracker


def dummy_openai_response(text):
    class C:
        def __init__(self, t):
            self.message = type('m', (), {'content': t})
    class R:
        def __init__(self, t):
            self.choices = [C(t)]
    return R(text)

SAMPLE_JSON = json.dumps({
    "seo_filename": "uploaded-artwork-by-robin-custance-rjc-9999.jpg",
    "title": "Test",
    "description": "desc",
    "tags": ["tag"],
    "materials": ["mat"],
    "primary_colour": "Black",
    "secondary_colour": "Brown"
})


def test_upload_single(tmp_path):
    client = app.test_client()
    img_iter = config.UNANALYSED_ROOT.rglob('*.jpg')
    img_path = next(img_iter, None)
    if img_path is None:
        config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
        img_path = config.UNANALYSED_ROOT / 'sample.jpg'
        Image.new('RGB', (10, 10), 'red').save(img_path)
    data = img_path.read_bytes()
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': (io.BytesIO(data), 'test.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()



def test_upload_reject_corrupt(tmp_path):
    client = app.test_client()
    bad = io.BytesIO(b'notanimage')
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': (bad, 'bad.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()


def test_upload_batch(tmp_path):
    client = app.test_client()
    img_iter = config.UNANALYSED_ROOT.rglob('*.jpg')
    img_path = next(img_iter, None)
    if img_path is None:
        config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
        img_path = config.UNANALYSED_ROOT / 'sample.jpg'
        Image.new('RGB', (10, 10), 'red').save(img_path)
    good = img_path.read_bytes()
    bad = io.BytesIO(b'bad')
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': [(io.BytesIO(good), 'good.jpg'), (bad, 'bad.jpg')]}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()


def test_upload_json_response(tmp_path):
    client = app.test_client()
    for s in session_tracker.active_sessions('robbie'):
        session_tracker.remove_session('robbie', s['session_id'])
    client.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=True)
    config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    img = config.UNANALYSED_ROOT / 'json-sample.jpg'
    Image.new('RGB', (10, 10), 'green').save(img)
    data = img.read_bytes()
    with mock.patch.object(aa.client.chat.completions, 'create'):
        resp = client.post('/upload',
            data={'images': (io.BytesIO(data), 'sample.jpg')},
            content_type='multipart/form-data',
            headers={'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 200
    arr = resp.get_json()
    assert isinstance(arr, list) and arr[0]['success']




---
## tests/test_utils_cleaning.py
---
import pytest
from routes import utils
from routes.artwork_routes import validate_listing_fields
import config


def test_clean_terms():
    cleaned, changed = utils.clean_terms(["te-st", "b@d"])
    assert cleaned == ["test", "bd"]
    assert changed


def test_read_generic_text():
    txt = utils.read_generic_text("4x5")
    assert txt.strip() != ""


def test_validate_generic_error_message():
    generic = utils.read_generic_text("4x5")
    data = {
        "title": "t",
        "description": "short description",
        "tags": ["tag"],
        "materials": ["mat"],
        "primary_colour": "Black",
        "secondary_colour": "Brown",
        "seo_filename": "Test-Artwork-by-Robin-Custance-RJC-0001.jpg",
        "price": "17.88",
        "sku": "RJC-0001",
        "images": [str(config.FINALISED_ROOT / 'test' / 'test.jpg')],
    }
    errors = validate_listing_fields(data, generic)
    joined = " ".join(errors)
    assert "correct generic context block" in joined


def test_validate_generic_present_with_whitespace():
    generic = utils.read_generic_text("4x5")
    base = "word " * 400
    desc = base + "\n\n" + generic + "\n   extra words after"  # within 50 words
    data = {
        "title": "t",
        "description": desc,
        "tags": ["tag"],
        "materials": ["mat"],
        "primary_colour": "Black",
        "secondary_colour": "Brown",
        "seo_filename": "Test-Artwork-by-Robin-Custance-RJC-0001.jpg",
        "price": "17.88",
        "sku": "RJC-0001",
        "images": [str(config.FINALISED_ROOT / 'test' / 'test.jpg')],
    }
    errors = validate_listing_fields(data, generic)
    joined = " ".join(errors)
    assert "correct generic context block" not in joined



---
## utils/__init__.py
---
"""Utility module exports for easy imports."""

from .logger_utils import log_action, strip_binary

__all__ = ["log_action", "strip_binary"]


---
## utils/ai_services.py
---
# utils/ai_services.py

import os
from openai import OpenAI
import config

# Initialize the OpenAI client using configuration from config.py
client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    project=config.OPENAI_PROJECT_ID,
)

def call_ai_to_generate_title(paragraph_content: str) -> str:
    """Uses AI to generate a short, compelling title for a block of text."""
    try:
        prompt = (
            f"Generate a short, compelling heading (5 words or less) for the following paragraph. "
            f"Respond only with the heading text, nothing else.\n\nPARAGRAPH:\n\"{paragraph_content}\""
        )
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        title = response.choices[0].message.content.strip().strip('"')
        return title
    except Exception as e:
        print(f"AI title generation error: {e}")
        return "AI Title Generation Failed"

def call_ai_to_rewrite(prompt: str, provider: str = "openai") -> str:
    """
    Calls the specified AI provider to rewrite text based on a prompt.
    Currently only supports OpenAI.
    """
    if provider != "openai":
        return "Error: Only OpenAI is currently supported for rewriting."

    try:
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,  # Use the primary model from config
            messages=[
                {"role": "system", "content": "You are an expert copywriter. Rewrite the following text based on the user's instruction. Respond only with the rewritten text, without any extra commentary."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        new_text = response.choices[0].message.content.strip()
        return new_text
    except Exception as e:
        print(f"AI service error: {e}")
        return f"Error during AI regeneration: {e}"
    
    

---
## utils/auth_decorators.py
---
"""Authentication and authorization decorators."""

from __future__ import annotations

from functools import wraps
from flask import session, redirect, url_for, request


def role_required(role: str):
    """Ensure the logged-in user has the specified role."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                return redirect(url_for("auth.login", next=request.path))
            return func(*args, **kwargs)

        return wrapper

    return decorator



---
## utils/logger_utils.py
---
from __future__ import annotations

"""Utility for structured audit logging.

This module provides the :func:`log_action` helper used by routes to
record user actions in hour-based log files under ``config.LOGS_DIR``.
"""

import contextlib
import fcntl
from pathlib import Path
from datetime import datetime
import os
from typing import Any

import config


_ACTION_DIRS = {
    "upload": "upload",
    "analyse-openai": "analyse-openai",
    "analyse-google": "analyse-google",
    "edits": "edits",
    "finalise": "finalise",
    "lock": "lock",
    "sellbrite-exports": "sellbrite-exports",
}


def strip_binary(obj: Any) -> Any:
    """Recursively remove bytes objects from ``obj`` for safe logging."""
    if isinstance(obj, dict):
        return {
            k: strip_binary(v)
            for k, v in obj.items()
            if not isinstance(v, (bytes, bytearray))
        }
    if isinstance(obj, list):
        return [strip_binary(v) for v in obj if not isinstance(v, (bytes, bytearray))]
    if isinstance(obj, (bytes, bytearray)):
        return f"<{len(obj)} bytes>"
    return obj


def sanitize_blob_data(obj: Any) -> Any:
    """Return ``obj`` with any obvious binary or base64 blobs summarised."""

    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            if k in {"image", "image_url", "image_data", "content"}:
                clean[k] = "<image data>"
            else:
                clean[k] = sanitize_blob_data(v)
        return clean
    if isinstance(obj, list):
        return [sanitize_blob_data(v) for v in obj]
    if isinstance(obj, (bytes, bytearray)):
        return f"<{len(obj)} bytes>"
    if isinstance(obj, str) and len(obj) > 300 and "base64" in obj:
        return "<base64 data>"
    return obj


def _log_path(action: str) -> Path:
    """Return folder path for the given action."""
    folder = _ACTION_DIRS.get(action, action)
    path = config.LOGS_DIR / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_action(
    action: str,
    filename: str,
    user: str | None,
    details: str,
    *,
    status: str = "success",
    error: str | None = None,
) -> None:
    """Append a formatted line to the audit log for ``action``."""

    log_dir = _log_path(action)
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H")
    log_file = log_dir / f"{stamp}.log"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    user_id = user or "unknown"

    parts = [
        timestamp,
        f"user: {user_id}",
        f"action: {action}",
        f"file: {filename}",
        f"status: {status}",
    ]
    if details:
        parts.append(f"detail: {details}")
    if error:
        parts.append(f"error: {error}")
    line = " | ".join(parts)

    with open(log_file, "a", encoding="utf-8") as f:
        with contextlib.suppress(OSError):
            fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line + "\n")


---
## utils/security.py
---
"""Site security helpers backed by the SQLite database."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from db import SessionLocal, SiteSettings


def _get_settings(session: Session) -> SiteSettings:
    settings = session.query(SiteSettings).first()
    if not settings:
        settings = SiteSettings()
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def login_required_enabled() -> bool:
    """Return True if login is currently required."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        if not settings.login_enabled:
            if settings.login_override_until and settings.login_override_until <= datetime.utcnow():
                settings.login_enabled = True
                settings.login_override_until = None
                session.commit()
        return settings.login_enabled


def disable_login_for(minutes: int) -> None:
    """Disable login for all non-admins for a period."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.login_enabled = False
        settings.login_override_until = datetime.utcnow() + timedelta(minutes=minutes)
        session.commit()


def enable_login() -> None:
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.login_enabled = True
        settings.login_override_until = None
        session.commit()


def remaining_minutes() -> int | None:
    """Return minutes left until login re-enables or None."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        if settings.login_override_until:
            delta = settings.login_override_until - datetime.utcnow()
            return max(int(delta.total_seconds() // 60), 0)
        return None


def force_no_cache_enabled() -> bool:
    """Return True if no-cache headers should be sent."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        if settings.force_no_cache and settings.force_no_cache_until and settings.force_no_cache_until <= datetime.utcnow():
            settings.force_no_cache = False
            settings.force_no_cache_until = None
            session.commit()
        return settings.force_no_cache


def enable_no_cache(minutes: int) -> None:
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.force_no_cache = True
        settings.force_no_cache_until = datetime.utcnow() + timedelta(minutes=minutes)
        session.commit()


def disable_no_cache() -> None:
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.force_no_cache = False
        settings.force_no_cache_until = None
        session.commit()


def no_cache_remaining() -> int | None:
    with SessionLocal() as session:
        settings = _get_settings(session)
        if settings.force_no_cache and settings.force_no_cache_until:
            delta = settings.force_no_cache_until - datetime.utcnow()
            return max(int(delta.total_seconds() // 60), 0)
        return None


---
## utils/session_tracker.py
---
"""Utilities for tracking active user sessions with a device limit."""
from __future__ import annotations

import json
import threading
import datetime
from pathlib import Path
import contextlib
import fcntl

import config

REGISTRY_FILE = config.LOGS_DIR / "session_registry.json"
_LOCK = threading.Lock()
MAX_SESSIONS = 5
TIMEOUT_SECONDS = 7200  # 2 hours


def _load_registry() -> dict:
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_FILE.write_text("{}")
        return {}
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            with contextlib.suppress(OSError):
                fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
    except Exception:
        REGISTRY_FILE.unlink(missing_ok=True)
        return {}
    return data


def _save_registry(data: dict) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_FILE.with_suffix(".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(REGISTRY_FILE)


def _cleanup_expired(data: dict) -> dict:
    now = datetime.datetime.utcnow()
    changed = False
    for user in list(data.keys()):
        sessions = [
            s
            for s in data[user]
            if now - datetime.datetime.fromisoformat(s["timestamp"]) < datetime.timedelta(seconds=TIMEOUT_SECONDS)
        ]
        if len(sessions) != len(data[user]):
            changed = True
        if sessions:
            data[user] = sessions
        else:
            data.pop(user)
            changed = True
    if changed:
        _save_registry(data)
    return data


def register_session(username: str, session_id: str) -> bool:
    with _LOCK:
        data = _load_registry()
        data = _cleanup_expired(data)
        sessions = data.get(username, [])
        if len(sessions) >= MAX_SESSIONS:
            return False
        sessions.append({"session_id": session_id, "timestamp": datetime.datetime.utcnow().isoformat()})
        data[username] = sessions
        _save_registry(data)
    return True


def remove_session(username: str, session_id: str) -> None:
    with _LOCK:
        data = _load_registry()
        data = _cleanup_expired(data)
        if username in data:
            data[username] = [s for s in data[username] if s.get("session_id") != session_id]
            if not data[username]:
                data.pop(username, None)
        _save_registry(data)


def touch_session(username: str, session_id: str) -> bool:
    with _LOCK:
        data = _load_registry()
        data = _cleanup_expired(data)
        for s in data.get(username, []):
            if s.get("session_id") == session_id:
                s["timestamp"] = datetime.datetime.utcnow().isoformat()
                _save_registry(data)
                return True
    return False


def active_sessions(username: str) -> list[dict]:
    data = _load_registry()
    data = _cleanup_expired(data)
    return data.get(username, [])


def all_sessions() -> dict:
    data = _load_registry()
    data = _cleanup_expired(data)
    return data


---
## utils/sku_assigner.py
---
# === [ ArtNarrator: SKU Assigner ] ====================================
# File: utils/sku_assigner.py  (or wherever fits your project layout)

import json
from pathlib import Path
import threading
import sys

SKU_PREFIX = "RJC-"
SKU_DIGITS = 4  # e.g., 0122 for 122

_LOCK = threading.Lock()  # for thread/process safety

def get_next_sku(tracker_path: Path) -> str:
    """Safely increment and return the next sequential SKU."""
    with _LOCK:
        # 1. Load or create tracker file
        if tracker_path.exists():
            with open(tracker_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_sku = int(data.get("last_sku", 0))
        else:
            last_sku = 0

        # 2. Increment
        next_sku_num = last_sku + 1
        next_sku_str = f"{SKU_PREFIX}{next_sku_num:0{SKU_DIGITS}d}"

        # 3. Write back to tracker
        data = {"last_sku": next_sku_num}
        with open(tracker_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return next_sku_str

def peek_next_sku(tracker_path: Path) -> str:
    """Return what the next SKU would be without incrementing."""
    if tracker_path.exists():
        with open(tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            last_sku = int(data.get("last_sku", 0))
    else:
        last_sku = 0

    next_sku_num = last_sku + 1
    next_sku_str = f"{SKU_PREFIX}{next_sku_num:0{SKU_DIGITS}d}"
    return next_sku_str

---
## utils/user_manager.py
---
"""Database-backed user management utilities."""

from __future__ import annotations

from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from db import SessionLocal, User


def load_users() -> list[User]:
    """Return all users."""
    with SessionLocal() as session:
        return session.query(User).all()


def add_user(username: str, role: str = "viewer", password: str = "changeme") -> None:
    """Create a new user if not exists."""
    with SessionLocal() as session:
        if session.query(User).filter_by(username=username).first():
            return
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
        )
        session.add(user)
        session.commit()


def delete_user(username: str) -> None:
    """Delete a user by username."""
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user:
            session.delete(user)
            session.commit()


def set_role(username: str, role: str) -> None:
    """Update a user's role."""
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user:
            user.role = role
            session.commit()

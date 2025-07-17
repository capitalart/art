"""ART Narrator Flask Entrypoint — Robbie Mode™ (July 2025)"""

from __future__ import annotations

import logging
import os
import json
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.routing import BuildError
from dotenv import load_dotenv
import uuid
import datetime
import menu_loader

# ==== Modular Imports ====
from config import LOGS_DIR
from routes.artwork_routes import bp as artwork_bp
from routes.sellbrite_service import bp as sellbrite_bp
from routes.export_routes import bp as exports_bp
from routes.admin_debug import bp as admin_bp
from routes.admin_routes import bp as admin_routes_bp
from routes.gdws_admin_routes import bp as gdws_admin_bp
from routes.aigw_routes import bp as aigw_bp
from routes.mockup_routes import bp as mockups_bp
from routes.prompt_options import bp as prompt_options_bp
from routes.prompt_ui import bp as prompt_ui_bp
from routes.prompt_whisperer import bp as whisperer_bp
from routes.documentation_routes import bp as documentation_bp
from auth import bp as auth_bp
from routes.legal_routes import bp as info_bp
import no_cache_toggle
from routes.session_tracker import is_active as session_is_active
import login_bypass

# ==== Versioning & Env ====
APP_VERSION = "2.5.1"
load_dotenv()

# ==== Flask App Initialization ====
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "mockup-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["TEMPLATES_AUTO_RELOAD"] = True  # Always reload templates on change
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # Flask disables static file cache
if os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true":
    app.config["SESSION_COOKIE_SECURE"] = True
app.permanent_session_lifetime = datetime.timedelta(days=14)

# ==== Version Check ====
def check_versions() -> None:
    print("--- Running System Version Check ---")
    version_file = Path(__file__).parent / "version.json"
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            expected = json.load(f)
    except FileNotFoundError:
        print("\u26A0\uFE0F WARNING: version.json not found. Skipping version check.")
        return

    import config
    loaded = {
        "app_version": APP_VERSION,
        "config_version": getattr(config, "CONFIG_VERSION", "Not Set"),
        "env_version": os.getenv("ENV_VERSION", "Not Set"),
        "openai_primary_model": config.OPENAI_PRIMARY_MODEL,
        "openai_fallback_model": config.OPENAI_FALLBACK_MODEL,
        "gemini_primary_model": config.GEMINI_PRIMARY_MODEL,
    }
    for key, expected_val in expected.items():
        loaded_val = loaded.get(key, "Not Set")
        if str(loaded_val) != str(expected_val):
            print(f"\u274C MISMATCH: {key} - Expected '{expected_val}', but found '{loaded_val}'")
        else:
            print(f"\u2705 MATCH: {key} - Version '{loaded_val}'")
    print("--- Version Check Complete ---")
check_versions()

# ==== Logging ====
logging.basicConfig(
    filename=LOGS_DIR / "composites-workflow.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ==== Blueprint Registration ====
for bp in [
    artwork_bp, sellbrite_bp, exports_bp, admin_bp, admin_routes_bp,
    gdws_admin_bp, aigw_bp, mockups_bp, info_bp, auth_bp, prompt_options_bp,
    prompt_ui_bp, whisperer_bp, documentation_bp,
]:
    app.register_blueprint(bp)

# ==== Context Processors for Cache-Busting & Admin Status ====
@app.context_processor
def inject_login_bypass():
    remaining = login_bypass.remaining_str()
    return {"login_bypass_remaining": remaining or None}

@app.context_processor
def inject_no_cache():
    def url_for_static(endpoint: str, **values):
        url = url_for(endpoint, **values)
        # Hard cache bust: always append version or uuid
        if endpoint == "static" and no_cache_toggle.is_enabled() and values.get("filename") != "favicon.ico":
            url += f"?v={uuid.uuid4()}"
        elif endpoint == "static" and "filename" in values and not values.get("filename", "").startswith("favicon"):
            # Always bust cache even if toggle is off: append short version
            url += f"?v={APP_VERSION}"
        return url
    return {
        "url_for_static": url_for_static,
        "forced_no_cache_active": no_cache_toggle.is_enabled(),
        "forced_no_cache_remaining": no_cache_toggle.remaining_str(),
    }

@app.context_processor
def inject_config():
    """Make selected config options available in templates."""
    import config
    return {"config": config}


@app.context_processor
def inject_mega_menu():
    """Provide mega menu data to all templates."""
    return {"mega_menu": menu_loader.MENU_DATA}

# ==== Flask Pre-Request: Login Required, Session Validation, Auto-Reload for Dev ====
@app.before_request
def require_login():
    if request.endpoint is None or request.endpoint.startswith("static"):
        return
    if request.endpoint in {"auth.login", "auth.logout"} or request.endpoint.startswith("prompt_options."):
        return
    if not session.get("user"):
        if login_bypass.is_active() and not request.path.startswith("/admin"):
            return
        return redirect(url_for("auth.login", next=request.url))
    if not session_is_active(session.get("user"), session.get("token", "")):
        session.clear()
        flash("Session expired or revoked", "warning")
        return redirect(url_for("auth.login", next=request.url))
    # Force reload of templates if under dev/debug or if .touch file is present (for Gunicorn hot reload workaround)
    if app.config.get("TEMPLATES_AUTO_RELOAD", False):
        try:
            import importlib
            importlib.reload(current_app.jinja_env)
        except Exception:
            pass

# ==== Error Handling ====
@app.errorhandler(BuildError)
def handle_build_error(err):
    app.logger.error("BuildError: %s", err)
    return render_template("missing_endpoint.html", error=err), 500

# ==== Healthcheck Endpoint ====
@app.route("/healthz")
def healthz():
    return "OK"

# ==== Gunicorn Stale Process Auto-Killer (Only Runs if Main) ====
def kill_gunicorn_zombies():
    """Force kill all old gunicorn procs for stale cache/hanging reload prevention."""
    import subprocess
    try:
        out = subprocess.check_output("pgrep -f gunicorn", shell=True)
        for pid in out.decode().strip().splitlines():
            # Don't kill our own process
            if int(pid) != os.getpid():
                os.system(f"kill -9 {pid}")
    except Exception:
        pass

# ==== Flask Factory for WSGI ====
def create_app() -> Flask:
    return app

# ==== Entrypoint: Always Purge Python Bytecode, Gunicorn Kill, Start Clean ====
if __name__ == "__main__":
    print("🧹 Purging all __pycache__ and *.pyc files for fresh start...")
    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                try:
                    fullpath = os.path.join(root, d)
                    os.system(f"rm -rf {fullpath}")
                except Exception:
                    pass
        for f in files:
            if f.endswith(".pyc") or f.endswith(".pyo"):
                try:
                    os.remove(os.path.join(root, f))
                except Exception:
                    pass
    # Kill stale Gunicorn procs if any
    kill_gunicorn_zombies()
    port = int(os.getenv("PORT", 8070))
    debug = os.getenv("DEBUG", "true").lower() == "true"
    print(f"\U0001f3a8 Starting ART Narrator UI at http://0.0.0.0:{port}/ ...")
    app.run(debug=debug, host="0.0.0.0", port=port)

# app.py
"""
ArtNarrator application entrypoint.

This file initializes the Flask application, sets up configurations,
registers all blueprints (routes), defines security hooks, and runs
the development server.

INDEX
-----
1.  Imports & Initialisation
2.  Flask App Setup
3.  Application Configuration
4.  Request Hooks & Security
5.  Blueprint Registration
6.  Error Handlers & Health Checks
7.  Main Execution Block
"""

# ===========================================================================
# 1. Imports & Initialisation
# ===========================================================================

from __future__ import annotations
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.routing import BuildError

# --- [ 1.1: Local Application Imports ] ---
import config
import db
from utils import security, session_tracker

# --- [ 1.2: Route (Blueprint) Imports ] ---
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
from routes.edit_listing_routes import bp as edit_listing_bp


# ===========================================================================
# 2. Flask App Setup
# ===========================================================================

# --- [ 2.1: Initialise App and Database ] ---
app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
db.init_db()

# --- [ 2.2: Setup Logging ] ---
# Ensure logs directory and session registry file exist before logging
config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
session_registry_file = config.LOGS_DIR / "session_registry.json"
if not session_registry_file.exists():
    session_registry_file.write_text("{}", encoding="utf-8")

# Note: This basic logging will be replaced by the centralized logging utility.
logging.basicConfig(
    filename=config.LOGS_DIR / "composites-workflow.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ===========================================================================
# 3. Application Configuration
# ===========================================================================

# --- [ 3.1: Set API Key Config Flags ] ---
app.config["OPENAI_CONFIGURED"] = bool(config.OPENAI_API_KEY)
app.config["GOOGLE_CONFIGURED"] = bool(config.GOOGLE_API_KEY)
if not app.config["OPENAI_CONFIGURED"]:
    logging.warning("OPENAI_API_KEY not configured in environment/.env")
if not app.config["GOOGLE_CONFIGURED"]:
    logging.warning("GOOGLE_API_KEY not configured in environment/.env")

# --- [ 3.2: Inject API Status into Templates ] ---
@app.context_processor
def inject_api_status():
    """Makes API configuration status available to all templates."""
    return dict(
        openai_configured=app.config.get("OPENAI_CONFIGURED", False),
        google_configured=app.config.get("GOOGLE_CONFIGURED", False),
    )


# ===========================================================================
# 4. Request Hooks & Security
# ===========================================================================

@app.before_request
def require_login() -> None:
    """Enforce login for all routes except designated public endpoints."""
    public_endpoints = {"auth.login", "static"}
    public_paths = {"/health", "/healthz"}

    if request.path in public_paths or request.endpoint in public_endpoints:
        return

    if not session.get("logged_in") and security.login_required_enabled():
        return redirect(url_for("auth.login", next=request.path))

    # Validate session for logged-in users
    username = session.get("username")
    sid = session.get("session_id")
    if username and sid and not session_tracker.touch_session(username, sid):
        session.clear()
        if security.login_required_enabled():
            return redirect(url_for("auth.login", next=request.path))


@app.after_request
def apply_no_cache(response):
    """Attach no-cache headers when admin mode requires it."""
    if security.force_no_cache_enabled():
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


# ===========================================================================
# 5. Blueprint Registration
# ===========================================================================
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
app.register_blueprint(edit_listing_bp)


# ===========================================================================
# 6. Error Handlers & Health Checks
# ===========================================================================

@app.errorhandler(404)
def page_not_found(e):
    app.logger.error(f"Page not found (404): {request.url}")
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"Internal Server Error (500): {e}")
    return render_template("500.html"), 500


@app.errorhandler(BuildError)
def handle_build_error(err):
    app.logger.error("BuildError (missing endpoint): %s", err)
    return render_template("missing_endpoint.html", error=err), 500


@app.route("/health")
@app.route("/healthz")
def health_check():
    """Basic health check endpoint for monitoring."""
    return "OK", 200


# ===========================================================================
# 7. Main Execution Block
# ===========================================================================

def create_app() -> Flask:
    """Factory function for application creation (e.g., for Gunicorn)."""
    return app


if __name__ == "__main__":
    logging.info(f"ArtNarrator app starting up at {datetime.now()}")
    if config.DEBUG and config.HOST not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Refusing to run in debug mode on a public interface.")
    
    print(f"🎨 Starting ArtNarrator UI at http://{config.HOST}:{config.PORT}/ ...")
    try:
        app.run(debug=config.DEBUG, host=config.HOST, port=config.PORT)
    finally:
        logging.info(f"ArtNarrator app shut down at {datetime.now()}")
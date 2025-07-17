"""ArtNarrator application entrypoint."""

from __future__ import annotations

import logging
import os
from flask import Flask, render_template, request, redirect, url_for, session
from utils import security, session_tracker
from werkzeug.routing import BuildError
from dotenv import load_dotenv
from datetime import datetime

# ---- Modular Imports ----
from routes import utils
from config import LOGS_DIR
from routes.artwork_routes import bp as artwork_bp  # <-- Blueprint import
from routes.sellbrite_service import bp as sellbrite_bp
from routes.export_routes import bp as exports_bp
from routes.auth_routes import bp as auth_bp
from routes.admin_security import bp as admin_bp

# ---- Load .env Configuration ----
load_dotenv()

# ---- Initialize Flask App ----
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "mockup-secret-key")


@app.before_request
def require_login() -> None:
    """Enforce login for all routes except the login page and static files."""
    allowed = {"auth.login", "static"}
    if request.endpoint in allowed or request.endpoint is None:
        return
    if not session.get("logged_in"):
        if security.login_required_enabled():
            return redirect(url_for("auth.login", next=request.path))
        return
    username = session.get("username")
    sid = session.get("session_id")
    if not session_tracker.touch_session(username, sid):
        session.clear()
        if security.login_required_enabled():
            return redirect(url_for("auth.login", next=request.path))

# ---- Logging Setup ----
logging.basicConfig(
    filename=LOGS_DIR / "composites-workflow.log",  # log file for workflow events
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Additional logging setup for app startup/shutdown
log_file = LOGS_DIR / "app_start_stop.log"
logging.basicConfig(
    filename=log_file, 
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---- File size max ----
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB (adjust as needed)

# ---- URL Length Validation Route ----
@app.route('/<path:url>')
def dynamic_page(url):
    # Check the length of the URL path
    if len(url) > 30:
        app.logger.warning(f"URL exceeded max length: {url}")
        return render_template('404.html'), 404  # Render 404 error page if URL length exceeds 30
    # Handle normal route logic here
    return f'You requested the URL: {url}'

# ---- Register Blueprints ----
app.register_blueprint(auth_bp)
app.register_blueprint(artwork_bp)
app.register_blueprint(sellbrite_bp)
app.register_blueprint(exports_bp)
app.register_blueprint(admin_bp)

# ---- Error Handlers ----
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

# ---- Healthcheck Route ----
@app.route("/healthz")
def healthz():
    return "OK"

# ---- Logging app start and stop events ----
if __name__ == "__main__":
    # Log the startup event
    logging.info(f"ArtNarrator app started at {datetime.now()}")

    port = int(os.getenv("PORT", 7777))  # Default to 7777 if no port is specified
    debug = os.getenv("DEBUG", "true").lower() == "true"  # Default to True if DEBUG is not set
    print(f"\U0001F3A8 Starting ArtNarrator UI at http://localhost:{port}/ ...")
    
    try:
        app.run(debug=debug, port=port)
    finally:
        # Log the shutdown event
        logging.info(f"ArtNarrator app stopped at {datetime.now()}")

# ---- Factory for WSGI ----
def create_app() -> Flask:
    return app

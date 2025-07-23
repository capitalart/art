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
app.register_blueprint(test_bp)
app.register_blueprint(api_bp)

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

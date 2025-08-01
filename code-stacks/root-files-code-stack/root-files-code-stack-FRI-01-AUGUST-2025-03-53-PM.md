# ROOT FILES CODE STACK (FRI-01-AUGUST-2025-03-53-PM)


---
## CHANGELOG.md
---
# Changelog

## [Unreleased]
- Standardised UI colour variables and button styles.
- Added keyboard accessible mockup carousel modal on edit listing page.
- Fixed locked gallery thumbnails by including main image data.


---
## CODEX-README.md
---
⸻


# DreamArtMachine CODEX-README.md

Welcome, Codex (or any AI developer)!  
**Before you start, read and follow ALL instructions in this document.**

---

## 🚩 Project Quick Overview

**DreamArtMachine** is a pro-grade, AI-powered art listing, curation, and export system—purpose-built for Robbie Custance (Aboriginal Aussie Artist), with a focus on:
- Automated artwork analysis (OpenAI Vision, GPT, and/or Gemini)
- Batch mockup generation & management
- Pulitzer-worthy, SEO-rich, culturally aware listing creation
- Robust file/folder structure (strict naming, versioned)
- Automated JSON exports for Etsy, Nembol, Gelato, and partners
- FastAPI backend, Jinja2 admin UI, SQLite+SQLAlchemy, and shell scripts

**Key Tech:**  
Python 3.11+, FastAPI, SQLAlchemy, OpenAI API, Jinja2, Pillow, Bash, minimal HTML/CSS

---

## 📂 Code & File Structure

- `routes/` — FastAPI or Flask route modules (upload, analyze, mockup, export, etc.)
- `services/` — Core business logic (AI analysis, prompt gen, workflows)
- `utils/` — File handling, helpers, templates, content blocks
- `core/` — Global config, settings, constants
- `templates/` — Jinja2 HTML templates, organized by menu/subfolder
- `static/` — CSS, icons, images
- `mockup-generator/` — Mockup templates, coordinates, category folders
- `data/` — SQLite DB and settings
- `master_listing_templates/` — Master OpenAI prompt templates (e.g., `etsy_master_template.txt`)
- `exports/` — logs, JSONs
- `/CODEX-LOGS/` — All AI audit logs (see below)

**Entry Point:**  
- `main.py` (imports all routers, sets up app, configures templates & error handlers)

---

## 🔥 Collaboration & Coding Rules

**You must:**
- Write **production-quality**, professionally sectioned and fully commented code.
- Use clear section headers and permanent section/subsection codes for every file.
- Never break, regress, or remove existing functionality without explicit instruction.
- If rewriting, always do **full-file rewrites** (not fragments) unless otherwise stated.
- Add or improve documentation, comments, and file TOC as needed.

**Sectioning:**  
- Each code file must have a Table of Contents at the top, mapping all section/subsection codes.
- Example codes: `analyze-routes-py-2a`.
- All functions/classes must have docstrings.

**When in doubt, ask for clarification before proceeding!**

---

## 🛠️ Core Workflows (Do NOT Break)

- **Artwork upload** → temp-processing dir, DB entry
- **AI analysis** (OpenAI/Gemini Vision + GPT) → generate title, description, attributes, tags (see templates)
- **Mockup generation** → batch create, strict naming (`{seo_filename}-MU-01.jpg` etc), review/finalise
- **Finalisation** → all files moved to `/finalised-artwork/{seo_folder}/`, DB paths updated, QA checks
- **JSON export** → only finalized artwork, strict Etsy/Nembol compliance, image URLs generated
- **Audit/QA scripts** → health checks, folder scans, export summaries, error reporting

---

## 🧠 AI/Prompt Engineering

- **All AI calls use master prompt templates** (e.g., `etsy_master_template.txt`, profiles in `settings.json`)
- Prompts must:
  - Exceed 400+ words, Pulitzer-worthy, culturally aware
  - Use proper SEO, avoid banned phrases, respect protocols
  - Output plain text (JSON safe), no HTML
  - Pull in relevant content blocks (dot art history, aspect ratio) where needed
- **Log every prompt, model, and result for traceability.**

---

## 📦 File/Folder/Naming Conventions

- All finalized images/files: `/finalised-artwork/{seo_folder}/`
  - Main: `{seo_filename}.jpg`
  - Mockups: `{seo_filename}-MU-01.jpg`, …`-MU-10.jpg`
  - Thumb: `{seo_filename}-thumb.jpg`
  - OpenAI: `{seo_filename}-openai.jpg`
  - JSON/sidecar: `{seo_filename}-listing.json`
- Temp uploads use unique batch folders, auto-cleaned on finalize
- Image URLs must be absolute/public for export (e.g. `/static/finalised-artwork/...`)

---

## 🚦 Quality Control & Testing

- All flows covered by audit/reporting scripts—never break audit compatibility.
- Add/extend pytest coverage for all new logic.
- All export flows (JSON) must pass strict pre-export checks.
- All code changes must be linted, formatted, and reviewed for:  
  - Security (input validation, permissions)  
  - Performance (efficient I/O, no memory leaks)  
  - Maintainability (readable, modular, DRY code)  
  - Accessibility/UX for any frontend changes

---

## 🔑 Security & Permissions

- All admin, delete, or finalize actions must check for role/permission.
- User/session logic must be robust, multi-user ready.
- API keys, passwords, and sensitive info only in `.env` or config (never hardcoded).

---

## 🧭 How to Extend/Integrate

- **To add a new route/module:**  
  - Follow existing structure, sectioning, and comments  
  - Register router in `main.py`
  - Place templates in the correct folder for menu auto-discovery

- **To add AI providers:**  
  - Abstract provider logic, allow model/version switch via config
  - Document API calls and fallbacks

- **To add menu items:**  
  - Place HTML templates in the relevant subfolder; system auto-discovers for menu

---

## 🧑‍💻 Codex CLI – Professional AI Workflow

### General Codex Usage

- Be **explicit and detailed** in every prompt: what, why, constraints, desired outcome.
- **Provide context:** current file structure, errors, configs.
- **Demand professional output:** modular, commented, and readable.
- **Test all code in the target environment** before merging.
- If Codex’s answer is incomplete or unclear, **revise the prompt and ask again**.

### Codex-Driven Log & Audit Trail

- **Every AI-assisted coding session or PR must have a Markdown log in `/CODEX-LOGS/`.**
- Each log must include:
  - Date/time for each key step and action
  - Files added/modified/deleted
  - What was changed and *why*
  - Key AI prompts used (summarize if not pasted)
  - Output from important commands/scripts/tests
  - Problems encountered & solutions
  - PR/issue number (if any)
  - Any TODOs or next steps

  **Save as:** `/CODEX-LOGS/YYYY-MM-DD-CODEX-LOG.md`  
  *Reference the log file in every PR/commit!*

#### Example Log Entry

```markdown
# Codex Log for PR #52

**Date:** 2025-07-22

## Actions
- Refactored utils.py into modules
- Fixed image blob handling for Flask backend
- Updated all image path references

## QA & Testing
- Uploaded images, verified analysis workflow
- Ran pytest suite, all pass

## Problems & Solutions
- TypeError in registry (fixed: enforced dict)
- 404 for processed images (fixed path logic)

## Prompts
> Codex, refactor utils.py and update all references, then explain each change in this log.

## TODO
- Modularize further
- Harden error handling

## PR: #52, https://github.com/yourorg/yourrepo/pull/52

Log Generation Prompt Example

Codex, after all tasks, generate a Markdown file (/CODEX-LOGS/YYYY-MM-DD-CODEX-LOG.md) detailing:
	•	Each action (file, description, reason)
	•	Time/date stamps
	•	Problems & solutions
	•	PR/commit links
	•	All commands, scripts, and prompts used
	•	Anything relevant for traceability or review

⸻

📋 Commit & PR Guidelines
	•	Commits must be atomic (one logical change per commit).
	•	Include the log file path from /CODEX-LOGS/ in every PR or major commit.
	•	Summarize the “why” in PR descriptions, not just the “what.”
	•	Always test before merge.
	•	Prefer pull requests over direct pushes to main/master.

⸻

🏷️ Directory Conventions
	•	/CODEX-LOGS/ — All AI audit logs (as Markdown)
	•	/docs/ — Main project documentation
	•	/tests/ — Unit/integration tests
	•	/routes/ — FastAPI/Flask routes
	•	/static/ — Frontend assets
	•	/templates/ — Jinja2/HTML templates
	•	/scripts/ — CLI tools
	•	/art-processing/ — Image pipeline directories
        •       /logs/ — Hourly audit logs per action

⸻

💡 Project Owner’s Tips
	•	“Full file rewrites, clear sectioning, real comments, always QA after changes”
	•	“When unsure, ask! Don’t break what works.”
	•	“Keep it neat, keep it professional, keep it Robbie Mode™.”

⸻

🏆 Pro Tips & Professional QA
	•	Never settle for vague or half-baked AI output—refine prompts until output meets standards.
	•	Document every deviation or manual patch—explain why in the log.
	•	Ask Codex to explain all changes in plain language.
	•	Use reviewer checklists for logs, QA, and docs.

⸻

END OF CODEX-README

Before starting, Codex must:
	1.	Read this file fully
	2.	Reference it for all decisions, file changes, or additions
	3.	Double-check that all logic, standards, and naming conventions are followed
	4.	Save a full Markdown log for every PR/task to /CODEX-LOGS/
	5.	Ensure all work is QA’d, production-grade, and fully documented

⸻

This README is your contract for world-class results.
If you need Codex CLI starter templates, advanced prompts, or CI samples—just ask.

⸻

End of CODEX-README.md


---
## README.md
---
# 🎨 ArtNarrator Mockup Generator

Welcome to **ArtNarrator**, a lightweight yet powerful mockup generation system designed to categorise, preview, and finalise high-quality mockups for digital artworks — all from the comfort of your local environment or server.

This system helps artists like me (Robin Custance — Aboriginal Aussie artist and part-time Kangaroo whisperer 🦘🎨) bulk-organise, intelligently analyse, and preview professional product mockups for marketplaces like Etsy.

---

## 🔧 Project Features

- ✅ **Mockup Categorisation** using OpenAI Vision (gpt-4o / gpt-4-turbo)
- ✅ **Automatic Folder Sorting** based on AI-detected room types
- ✅ **Flask UI** to preview randomly selected mockups (1 per category)
- ✅ **Swap / Regenerate** functionality for better aesthetic control
- ✅ **Ready for Composite Generation** and final publishing
- ✅ Designed to support multiple **aspect ratios** like 4:5, 1:1, etc.

---

## 📁 Folder Structure

```bash
Artnarrator-Mockup-Generator/
├── Input/
│   └── Mockups/
│       ├── 4x5/
│       └── 4x5-categorised/
│           ├── Living Room/
│           ├── Bedroom/
│           ├── Nursery/
│           └── ...
├── Output/
│   └── Composites/
└── mockup_selector_ui.py

pip install -r requirements.txt



Flask
openai
python-dotenv
Pillow
requests


🧩 In Development
🖼 Composite Generator (overlay artwork onto mockups)

🧼 Finalisation Script (move print files, create web preview)

📦 Sellbrite Exporter

🖼 Aspect Ratio Selector Support

🇦🇺 About the Artist
Hi, I’m Robin Custance — proud Aboriginal Aussie artist and storyteller through colour and dots. I live on Kaurna Country in Adelaide, with ancestral ties to the Boandik people of Naracoorte.

This project supports my mission to share stories through art while helping my family thrive. ❤️

⚡ Contact
💌 rob@asbcreative.com.au

🌐 robincustance.etsy.com

📷 Insta coming soon...
## 🆕 Running the Modular App

The Flask application is now launched via `app.py` which registers feature blueprints. Start the server with:

```bash
python app.py
```

Routes from `artnarrator.py` were moved to `routes/artwork_routes.py`. More modules will follow as the project evolves.

### Blueprint Endpoint Names

All templates must reference routes using their blueprint-prefixed endpoint names. For example, use `url_for('artwork.home')` instead of `url_for('home')`. This avoids `BuildError` when looking up URLs.

### Logging & Image Responses

Routes never return raw `bytes` or base64 data. Images are served exclusively with `send_file` or `send_from_directory` so the browser receives the correct mime type. Log entries strip any binary fields using `utils.strip_binary` before writing, ensuring audit logs and JSON responses remain readable.

### Sellbrite Field Mapping

The helper `generate_sellbrite_json()` in `routes/sellbrite_export.py` converts
our artwork listing data to the fields expected by Sellbrite's Listings API.

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


Use `--json-dir` to read from the finalised artwork folders instead.


### Environment Variables

Create a `.env` file based on `.env.example` and set the following values:

```
OPENAI_API_KEY=your-key-here
OPENAI_PRIMARY_MODEL=gpt-4o
OPENAI_FALLBACK_MODEL=gpt-4-turbo
FLASK_SECRET_KEY=your-flask-secret
DEBUG=true
PORT=5050
SELLBRITE_TOKEN=your-sellbrite-token
SELLBRITE_SECRET=your-sellbrite-secret
```

These credentials enable OpenAI features and allow authenticated calls to the
Sellbrite API.

### SKU Assignment

All new listings receive a sequential SKU tracked in the JSON file defined by
`config.SKU_TRACKER` (defaults to `config.SETTINGS_DIR / "sku_tracker.json"`).
SKUs are allocated only when an artwork is finalised using
`utils.sku_assigner.get_next_sku(SKU_TRACKER)`. During analysis a preview of the
next SKU may be obtained with `peek_next_sku(SKU_TRACKER)` and is available via
the `/next-sku` route for admins.
The preview value is injected into the OpenAI prompt as `assigned_sku` so the AI
never invents a SKU. Listing pages display the SKU as a read-only field sourced
from the JSON file.

### Running the Unit Tests

After installing dependencies with `pip install -r requirements.txt`, run the repository's tests using:

```bash
pytest
```

This command executes all tests under the `tests/` directory to ensure routes and artwork analysis behave correctly.

### Admin Suite & Roles

The application now stores users and site settings in `data/artnarrator.sqlite3`.
Three roles are supported:

- **admin** – full access to `/admin` tools
- **editor** – manage artworks and listings
- **viewer** – read-only access

Admins may manage users and security settings from `/admin`. Login can be temporarily disabled for non-admins, and cache headers can be forced across the site. Use the user management page to add or remove users and set their roles.



---
## app.py
---
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

---
## artnarrator-report.sh
---
#!/bin/bash

# ======================================================================================
# 🔄 Codex Merge & Check Engine 💥
#
# Version: 1.0
# Author: Robbie (Adapted for ArtNarrator, with Codex Precision)
#
# This script is designed for ultimate precision and safety. It does the following:
# 1. Checks for any broken routes, packages, or links before pulling updates.
# 2. Creates an encrypted, detailed backup of the ArtNarrator system.
# 3. Pulls the latest changes from the Git remote repository.
# 4. Checks again for broken links/routes or any discrepancies after the pull.
#
# ======================================================================================

# Usage examples:
#   ./codex-merge.sh --full-auto       # Runs non-interactively, performs full backup, pull, checks before and after
#   ./codex-merge.sh --dry-run         # Shows what would be done, no actual changes
#   ./codex-merge.sh --no-pre-backup   # Skip backup/cloud sync
#   ./codex-merge.sh --no-pull         # Skip git pull
#   ./codex-merge.sh --no-report       # Skip project report generation
#   ./codex-merge.sh --no-restart      # Skip server restart

# ======================================================================================

# === [ SECTION 1: SETUP & CONFIGURATION ] ===========================================
set -euo pipefail

PROJECT_ROOT_DIR="$(pwd)"
LOG_DIR="${PROJECT_ROOT_DIR}/logs"
BACKUP_DIR="${PROJECT_ROOT_DIR}/backups"
DB_FILE="${PROJECT_ROOT_DIR}/data/artnarrator.db"
GDRIVE_RCLONE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="artnarrator-backups"
CLOUD_RETENTION_COUNT=300  # Number of backups to keep in the cloud

NOW=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/codex-merge-${NOW}.log"
DB_DUMP_FILE="$BACKUP_DIR/pre-pull-db_dump_${NOW}.sql"
BACKUP_ZIP="$BACKUP_DIR/codex-merge-backup_${NOW}.zip"
PULL_DIFF_REPORT="$BACKUP_DIR/codex-merge-diff-report_${NOW}.md"

GUNICORN_PID_FILE="/tmp/artnarrator-gunicorn.pid"
GUNICORN_CMD="${PROJECT_ROOT_DIR}/venv/bin/gunicorn"
GUNICORN_BIND_ADDRESS="0.0.0.0:7777"
GUNICORN_WORKERS=4
GUNICORN_APP_MODULE="app:app"

# Default flags for the script
AUTO_MODE=false
DRY_RUN=false
ENABLE_PRE_BACKUP=true
ENABLE_PULL=true
ENABLE_RESTART=true
ENABLE_PIP_UPDATE=false
ENABLE_PIP_CHECK=false
ENABLE_SYSTEM_REPORT=true

# === [ SECTION 2: FLAG PARSER ] ======================================================
for arg in "$@"; do
  case $arg in
    --full-auto)     AUTO_MODE=true; shift ;;
    --dry-run)       DRY_RUN=true; shift ;;
    --no-pre-backup) ENABLE_PRE_BACKUP=false; shift ;;
    --no-pull)       ENABLE_PULL=false; shift ;;
    --no-report)     ENABLE_REPORT_SCRIPT=false; shift ;;
    --no-restart)    ENABLE_RESTART=false; shift ;;
    --pip-update)    ENABLE_PIP_UPDATE=true; shift ;;
    --pip-check)     ENABLE_PIP_CHECK=true; shift ;;
    --system-report) ENABLE_SYSTEM_REPORT=true; shift ;;
    *) echo -e "❌ Unknown option: $arg"; exit 1 ;;
  esac
done

# === [ SECTION 3: LOGGING & UTILITY FUNCTIONS ] =======================================
mkdir -p "$LOG_DIR"

log() {
  local type="$1"
  local msg="$2"
  local color='\033[0;36m'
  case "$type" in
    SUCCESS) color='\033[0;32m' ;;
    WARN)    color='\033[0;33m' ;;
    ERROR)   color='\033[0;31m' ;;
  esac
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') | ${color}${type^^}:${COL_RESET} ${msg}" | tee -a "$LOG_FILE"
}

die() {
  log "ERROR" "$1"
  exit 1
}

run_cmd() {
  log "EXEC" "$@"
  if ! $DRY_RUN; then
    eval "$@" >> "$LOG_FILE" 2>&1
  fi
}

check_dependencies() {
    log "INFO" "Checking for required tools..."
    for cmd in git zip sqlite3 rclone jq curl; do
        if ! command -v "$cmd" &> /dev/null; then
            die "Required command '$cmd' is not installed. Aborting."
        fi
    done
    log "SUCCESS" "All required tools are present."
}

# === [ SECTION 4: CHECKING AND BACKUP FUNCTIONS ] ===================================
check_for_broken_links() {
  log "INFO" "Checking for broken links and routes..."
  run_cmd "curl -I http://localhost:7777" || log "ERROR" "Local route check failed."
  run_cmd "curl -I http://localhost:7777/api/health" || log "ERROR" "API health route check failed."
}

# --- 4a: Pre-Pull Backup ---
handle_pre_pull_backup() {
  if ! $ENABLE_PRE_BACKUP; then
    log "WARN" "Skipping pre-pull backup as per --no-pre-backup flag."
    return
  fi

  log "INFO" "Starting pre-pull backup process..."

  # --- Database Dump ---
  if [ -f "$DB_FILE" ]; then
    log "INFO" "Creating SQLite database dump..."
    run_cmd "sqlite3 '$DB_FILE' .dump > '$DB_DUMP_FILE'"
    log "SUCCESS" "Database dump created: $DB_DUMP_FILE"
  else
    log "WARN" "Database file not found at $DB_FILE. Skipping dump."
  fi

  # --- ZIP Archive ---
  log "INFO" "Creating full project backup ZIP archive (pre-pull state)..."
  run_cmd "zip -r -q '$BACKUP_ZIP' . \
      -x '.git/*' \
      -x 'venv/*' \
      -x 'node_modules/*' \
      -x '__pycache__/*' \
      -x 'backups/*' \
      -x 'logs/*' \
      -x 'dev_logs/*' \
      -x 'git-update-push-logs/*' \
      -x 'reports/*' \
      -x '*.DS_Store' \
      -x '.env' \
      -x 'inputs/*' \
      -x 'outputs/*' \
      -x 'example-images/*' \
      -x '*.sqlite3' \
      -x '*.pyc' \
      -x '*.pyo' \
      -x 'art-uploads/*' \
      -x 'audit/*' \
      -x 'assets/*' \
      -x 'descriptions/*' \
      -x 'gdws_content/*' \
      -x 'mnt/*'"
  log "SUCCESS" "Pre-pull backup ZIP created: $BACKUP_ZIP"

  # --- Cloud Sync ---
  log "INFO" "Uploading pre-pull backup to Google Drive..."
  run_cmd "rclone copy '$BACKUP_ZIP' '$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER' --progress" || log "ERROR" "Rclone upload failed. Check rclone configuration and network."
}

# --- 4b: Git Pull ---
handle_git_pull() {
  if ! $ENABLE_PULL; then
    log "WARN" "Skipping Git pull as per --no-pull flag."
    return
  fi
  log "INFO" "Pulling the latest changes from the remote repository..."
  run_cmd "git pull origin main --rebase" || die "Git pull failed."
}

# --- 4c: After Pull Check ---
check_after_pull() {
  log "INFO" "Checking for broken links/routes after pulling..."
  check_for_broken_links
}

# --- 4d: Git Push ---
handle_git_push() {
  if $ENABLE_PULL; then
    log "INFO" "Pushing local changes to GitHub..."
    run_cmd "git push origin main" || die "Git push failed."
  fi
}

# === [ SECTION 5: MAIN EXECUTION ] ====================================================

main() {
  mkdir -p "$LOG_DIR" "$BACKUP_DIR"
  log "INFO" "=== 🔄 Codex Merge & Check Engine Initialized ==="

  check_dependencies

  # Execute pre-pull check
  check_for_broken_links

  # Execute the pull & check sequence
  handle_pre_pull_backup
  handle_git_pull
  check_after_pull

  # If not a dry run, push and update packages
  handle_git_push
  pip_update
  pip_check

  log "SUCCESS" "🎉 Codex Merge & Check Engine completed successfully. 💚"
}

# Start the process
main


---
## config.py
---
# config.py — ArtNarrator & DreamArtMachine (Robbie Mode™, July 2025)
# Central config: All core folders, env vars, limits, AI models, templates.
# All code must import config.py and reference only these values!

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Load .env file from project root ---
load_dotenv()

# === PROJECT ROOT ===
BASE_DIR = Path(__file__).resolve().parent

# =============================================================================
# 1. ENV/BRANDING/ADMIN
# =============================================================================
# ... (sections 1-9 remain the same) ...
# --- [ 1.1: Branding ] ---
BRAND_NAME = os.getenv("BRAND_NAME", "Art Narrator")
BRAND_TAGLINE = os.getenv("BRAND_TAGLINE", "Create. Automate. Sell Art.")
BRAND_AUTHOR = os.getenv("BRAND_AUTHOR", "Robin Custance")
BRAND_DOMAIN = os.getenv("BRAND_DOMAIN", "artnarrator.com")
ETSY_SHOP_URL = os.getenv("ETSY_SHOP_URL", "https://www.robincustance.etsy.com")

# --- [ 1.2: Server & Flask ] ---
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "robincustance@gmail.com")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "robbie")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "kangaroo123")
SERVER_PORT = int(os.getenv("SERVER_PORT", "7777"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
HOST = os.getenv("HOST", "127.0.0.1")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "supersecret-key-1234")
PORT = int(os.getenv("PORT", "7777"))


# =============================================================================
# 2. AI/PLATFORM/API MODELS
# =============================================================================

# --- [ 2.1: OpenAI ] ---
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Main model for both text and vision tasks (gpt-4o is multimodal)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_MODEL_FALLBACK = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4-turbo")

# Models specifically for image GENERATION
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
OPENAI_IMAGE_MODEL_FALLBACK = os.getenv("OPENAI_IMAGE_MODEL_FALLBACK", "dall-e-2")
# ... (other OpenAI models) ...

# --- [ 2.2: Google Cloud ] ---
# API Key for authenticating with Google Cloud services
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 

# The single, multimodal model for text and vision tasks
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro-latest")

# You can keep this if other parts of your app use a generic Google API key
# or the Google Project ID, otherwise they can be removed too.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
# ... (other Google models) ...

# --- [ 2.3: Other Integrations ] ---
RCLONE_REMOTE_NAME = os.getenv("RCLONE_REMOTE_NAME", "gdrive")
RCLONE_REMOTE_PATH = os.getenv("RCLONE_REMOTE_PATH", "art-backups")
SELLBRITE_ACCOUNT_TOKEN = os.getenv("SELLBRITE_ACCOUNT_TOKEN")
SELLBRITE_SECRET_KEY = os.getenv("SELLBRITE_SECRET_KEY")
SELLBRITE_API_BASE_URL = os.getenv("SELLBRITE_API_BASE_URL", "https://api.sellbrite.com/v1")

# --- [ 2.4: SMTP Configuration ] --- (NEW SUB-SECTION)
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# =============================================================================
# 3. FOLDER STRUCTURE & CORE PATHS
# =============================================================================

# --- [ 3.1: Core Directories ] ---
SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", BASE_DIR / "scripts"))
SETTINGS_DIR = Path(os.getenv("SETTINGS_DIR", BASE_DIR / "settings"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", BASE_DIR / "logs"))
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
STATIC_DIR = Path(os.getenv("STATIC_DIR", BASE_DIR / "static"))
TEMPLATES_DIR = Path(os.getenv("TEMPLATES_DIR", BASE_DIR / "templates"))

# --- [ 3.2: Art Processing Workflow Directories ] ---
ART_PROCESSING_DIR = Path(os.getenv("ART_PROCESSING_DIR", BASE_DIR / "art-processing"))
UNANALYSED_ROOT = ART_PROCESSING_DIR / "unanalysed-artwork"
PROCESSED_ROOT = ART_PROCESSING_DIR / "processed-artwork"
FINALISED_ROOT = ART_PROCESSING_DIR / "finalised-artwork"
ARTWORK_VAULT_ROOT = ART_PROCESSING_DIR / "artwork-vault"

# --- [ 3.3: Input Asset Directories ] ---
MOCKUPS_INPUT_DIR = Path(os.getenv("MOCKUPS_INPUT_DIR", BASE_DIR / "inputs" / "mockups"))
MOCKUPS_STAGING_DIR = MOCKUPS_INPUT_DIR / "uncategorised"
MOCKUPS_CATEGORISED_DIR = MOCKUPS_INPUT_DIR / "categorised"
MOCKUP_THUMBNAIL_DIR = MOCKUPS_INPUT_DIR / ".thumbnails"
SIGNATURES_DIR = Path(os.getenv("SIGNATURES_DIR", BASE_DIR / "inputs" / "signatures"))
GENERIC_TEXTS_DIR = Path(os.getenv("GENERIC_TEXTS_DIR", BASE_DIR / "generic_texts"))
COORDS_DIR = Path(os.getenv("COORDS_DIR", BASE_DIR / "inputs" / "Coordinates"))
GDWS_CONTENT_DIR = DATA_DIR / "gdws_content"

# --- [ 3.4: Output Directories ] ---
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", BASE_DIR / "outputs"))
COMPOSITES_DIR = OUTPUTS_DIR / "composites"
SELECTIONS_DIR = OUTPUTS_DIR / "selections"
SELLBRITE_DIR = OUTPUTS_DIR / "sellbrite"
SIGNED_DIR = OUTPUTS_DIR / "signed"
CODEX_LOGS_DIR = Path(os.getenv("CODEX_LOGS_DIR", BASE_DIR / "CODEX-LOGS"))

# Additional path aliases for easier imports
MOCKUPS_ROOT = MOCKUPS_INPUT_DIR
CATEGORISED_MOCKUPS_ROOT = MOCKUPS_CATEGORISED_DIR
COMPOSITES_ROOT = COMPOSITES_DIR
THUMB_SUBDIR = "THUMBS"
THUMBS_ROOT = FINALISED_ROOT / THUMB_SUBDIR


# =============================================================================
# 4. HELPER & REGISTRY FILES
# =============================================================================
DB_PATH = DATA_DIR / "artnarrator.sqlite3"
SKU_TRACKER = SETTINGS_DIR / "sku_tracker.json"
ANALYSIS_STATUS_FILE = LOGS_DIR / "analysis_status.json"
SESSION_REGISTRY_FILE = LOGS_DIR / "session_registry.json"
ONBOARDING_PATH = SETTINGS_DIR / "Master-Etsy-Listing-Description-Writing-Onboarding.txt"
MOCKUP_CATEGORISER_PROMPT_PATH = SETTINGS_DIR / "mockup_categoriser_prompt.txt" # <-- NEW VARIABLE
OUTPUT_JSON = ART_PROCESSING_DIR / "master-artwork-paths.json"
MOCKUP_CATEGORISATION_LOG = LOGS_DIR / "mockup_categorisation.log"
PENDING_MOCKUPS_QUEUE_FILE = PROCESSED_ROOT / "pending_mockups.json"


# =============================================================================
# 5. FILENAME TEMPLATES
# =============================================================================
FILENAME_TEMPLATES = {
    "artwork": "{seo_slug}.jpg",
    "mockup": "{seo_slug}-MU-{num:02d}.jpg",
    "thumbnail": "{seo_slug}-THUMB.jpg",
    "analyse": "{seo_slug}-ANALYSE.jpg",
    "listing_json": "{seo_slug}-listing.json",
    "qc_json": "{seo_slug}.qc.json",
}

# =============================================================================
# 6. FILE TYPES, LIMITS, & IMAGE SIZES
# =============================================================================
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png").split(","))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
ANALYSE_MAX_DIM = int(os.getenv("ANALYSE_MAX_DIM", "2400"))
ANALYSE_MAX_MB = int(os.getenv("ANALYSE_MAX_MB", "5"))
THUMB_WIDTH = int(os.getenv("THUMB_WIDTH", "400"))
THUMB_HEIGHT = int(os.getenv("THUMB_HEIGHT", "400"))

# =============================================================================
# 7. APPLICATION CONSTANTS
# =============================================================================
# --- [ 7.1: Artwork & Mockup Defaults ] ---
MOCKUPS_PER_LISTING = 9
DEFAULT_MOCKUP_IMAGE = STATIC_DIR / "img" / "default-mockup.jpg"
ETSY_COLOURS = {
    'Beige': (222, 202, 173), 'Black': (24, 23, 22), 'Blue': (42, 80, 166),
    'Bronze': (140, 120, 83), 'Brown': (110, 72, 42), 'Clear': (240, 240, 240),
    'Copper': (181, 101, 29), 'Gold': (236, 180, 63), 'Grey': (160, 160, 160),
    'Green': (67, 127, 66), 'Orange': (237, 129, 40), 'Pink': (229, 100, 156),
    'Purple': (113, 74, 151), 'Rainbow': (170, 92, 152), 'Red': (181, 32, 42),
    'Rose gold': (212, 150, 146), 'Silver': (170, 174, 179),
    'White': (242, 242, 243), 'Yellow': (242, 207, 46)
}

# --- [ 7.2: Security & Session Management ] ---
MAX_SESSIONS = 5
SESSION_TIMEOUT_SECONDS = 7200  # 2 hours

# --- [ 7.3: SKU Configuration ] ---
SKU_CONFIG = {
    "PREFIX": "RJC-",
    "DIGITS": 4
}

# --- [ 7.4: Sellbrite Export Defaults ] ---
SELLBRITE_DEFAULTS = {
    "QUANTITY": 25,
    "CONDITION": "New",
    "CATEGORY": "Art & Collectibles > Prints > Digital Prints",
    "WEIGHT": 0
}

# --- [ 7.5: Guided Description Writing System (GDWS) Config ] ---
GDWS_CONFIG = {
    # --- MODIFIED: Added the master list of paragraph headings ---
    "PARAGRAPH_HEADINGS": [
        "About the Artist – Robin Custance", "Did You Know? Aboriginal Art & the Spirit of Dot Painting",
        "What You’ll Receive", "Ideal Uses for the", "Printing Tips",
        "Top 10 Print-On-Demand Services for Wall Art & Art Prints", "Important Notes",
        "Frequently Asked Questions", "LET’S CREATE SOMETHING BEAUTIFUL TOGETHER",
        "THANK YOU – FROM MY STUDIO TO YOUR HOME", "EXPLORE MY WORK", "WHY YOU’LL LOVE THIS ARTWORK",
        "HOW TO BUY & PRINT", "Thank You & Stay Connected"
    ],
    "PINNED_START_TITLES": [
        "About the Artist – Robin Custance",
        "Did You Know? Aboriginal Art & the Spirit of Dot Painting",
        "What You’ll Receive",
        "WHY YOU’LL LOVE THIS ARTWORK",
        "HOW TO BUY & PRINT",
    ],
    "PINNED_END_TITLES": [
        "THANK YOU – FROM MY STUDIO TO YOUR HOME",
        "Thank You & Stay Connected",
    ]
}


# =============================================================================
# 8. DYNAMIC CATEGORIES (from filesystem)
# ... (rest of the file is unchanged) ...
# =============================================================================
def get_mockup_categories() -> list[str]:
    override = os.getenv("MOCKUP_CATEGORIES")
    if override:
        return [c.strip() for c in override.split(",") if c.strip()]
    d = MOCKUPS_CATEGORISED_DIR
    if d.exists():
        return sorted([f.name for f in d.iterdir() if f.is_dir()])
    return []

MOCKUP_CATEGORIES = get_mockup_categories()


def resolve_image_url(path: Path) -> str:
    """Convert absolute path to a project-relative URL."""
    return str(path).replace(str(BASE_DIR), "").lstrip("/")

# =============================================================================
# 9. FOLDER AUTO-CREATION
# =============================================================================
_CRITICAL_FOLDERS = [
    ART_PROCESSING_DIR, UNANALYSED_ROOT, PROCESSED_ROOT, FINALISED_ROOT,
    ARTWORK_VAULT_ROOT, OUTPUTS_DIR, COMPOSITES_DIR, SELECTIONS_DIR,
    SELLBRITE_DIR, SIGNED_DIR, MOCKUPS_INPUT_DIR, MOCKUPS_STAGING_DIR,
    MOCKUPS_CATEGORISED_DIR, MOCKUP_THUMBNAIL_DIR, SIGNATURES_DIR,
    GENERIC_TEXTS_DIR, COORDS_DIR, SCRIPTS_DIR, SETTINGS_DIR, LOGS_DIR,
    CODEX_LOGS_DIR, DATA_DIR, STATIC_DIR, TEMPLATES_DIR, GDWS_CONTENT_DIR,
]
for folder in _CRITICAL_FOLDERS:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"Could not create required folder {folder}: {exc}") from exc

# =============================================================================
# 10. SCRIPT PATHS (for automation & CLI)
# =============================================================================
ANALYZE_SCRIPT_PATH = SCRIPTS_DIR / "analyze_artwork.py"
GENERATE_SCRIPT_PATH = SCRIPTS_DIR / "generate_composites.py"
MOCKUP_CATEGORISER_SCRIPT_PATH = SCRIPTS_DIR / "mockup_categoriser.py"
COORDINATE_GENERATOR_SCRIPT_PATH = SCRIPTS_DIR / "generate_coordinates.py"
COORDINATE_GENERATOR_RATIO_SCRIPT_PATH = SCRIPTS_DIR / "generate_coordinates_for_ratio.py" # <-- NEW VARIABLE

# =============================================================================
# 11. URLS & ROUTE PREFIXES
# =============================================================================
# --- [ 11.1: Base URL for Serving Content ] ---
BASE_URL = f"https://{BRAND_DOMAIN}" if ENVIRONMENT == "prod" else f"http://{HOST}:{PORT}"

# --- [ 11.2: URL Paths for Serving Static-like Content via Flask ] ---
STATIC_URL_PREFIX = "static"
PROCESSED_URL_PATH = f"{STATIC_URL_PREFIX}/{PROCESSED_ROOT.relative_to(BASE_DIR).as_posix()}"
FINALISED_URL_PATH = f"{STATIC_URL_PREFIX}/{FINALISED_ROOT.relative_to(BASE_DIR).as_posix()}"
LOCKED_URL_PATH = f"{STATIC_URL_PREFIX}/{ARTWORK_VAULT_ROOT.relative_to(BASE_DIR).as_posix()}"

# --- [ 11.3: Prefixes for Other Dynamic Image Routes ] ---
UNANALYSED_IMG_URL_PREFIX = "unanalysed-img"
MOCKUP_THUMB_URL_PREFIX = "thumbs"
COMPOSITE_IMG_URL_PREFIX = "composite-img"

# =============================================================================
# 12. AUDIT & MARKDOWN FILES
# =============================================================================
QA_AUDIT_INDEX = BASE_DIR / "QA_AUDIT_INDEX.md"
SITEMAP_FILE = BASE_DIR / "SITEMAP.md"
CHANGELOG_FILE = BASE_DIR / "CHANGELOG.md"

# =============================================================================
# 13. LOGGING SETUP
# =============================================================================
# --- [ 13.1: Log File Timestamp Format ] ---
LOG_TIMESTAMP_FORMAT = "%a-%d-%b-%Y-%I-%M-%p"

# --- [ 13.2: Log File Configurations ] ---
LOG_CONFIG = {
    # Core App Lifecycle
    "APP_STARTUP": "app-lifecycle-logs",
    "DATABASE": "database-logs",
    "SECURITY": "security-logs",
    "GUNICORN": "gunicorn",
    # Artwork Workflow Actions
    "UPLOAD": "upload",
    "DELETE": "delete",
    "EDITS": "edits",
    "FINALISE": "finalise",
    "LOCK": "lock",
    # Script & Subprocess Actions
    "ANALYZE_OPENAI": "analyse-openai",
    "ANALYZE_GOOGLE": "analyse-google",
    "COMPOSITE_GEN": "composite-generation-logs",
    # API Integrations
    "SELLBRITE_API": "sellbrite-api-logs",
    # Default/Catch-all
    "DEFAULT": "general-logs",
}

---
## cron-backup.sh
---
#!/bin/bash

# ======================================================================================
# 🛡️ ArtNarrator Automated Backup Engine 🛡️
#
# Version: 1.1
# Author: Robbie (Adapted for ArtNarrator, Enhanced by Gemini)
#
# This script is designed to be run exclusively by cron for automated backups.
# It performs NO Git operations and NO server restarts. Its sole purpose is to:
# 1. Create a secure backup of the application code and database.
# 2. Upload the backup to a cloud remote (Google Drive).
# 3. Apply a retention policy to the cloud backups.
#
# ---
#
# Usage (for cron jobs):
#   /path/to/cron-backup.sh >> /path/to/logs/cron.log 2>&1
#
# Usage (for manual testing):
#   ./cron-backup.sh
#   ./cron-backup.sh --dry-run
#
# ======================================================================================

# === [ SECTION 1: SCRIPT SETUP & CONFIGURATION ] ======================================
set -euo pipefail

# --- Project & Backup Configuration ---
# Change to the ArtNarrator directory to ensure all paths are correct
cd /home/art/art || exit 1

PROJECT_ROOT_DIR="$(pwd)"
LOG_DIR="${PROJECT_ROOT_DIR}/logs"
BACKUP_DIR="${PROJECT_ROOT_DIR}/backups"

# --- Naming Conventions ---
NOW=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/cron-backup-${NOW}.log"
BACKUP_ZIP="$BACKUP_DIR/backup_${NOW}.zip"

# --- Cloud Configuration ---
GDRIVE_RCLONE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="artnarrator-backups"
CLOUD_RETENTION_COUNT=300  # Number of backups to keep in the cloud

# --- Colors for Logging ---
COL_RESET='\033[0m'
COL_INFO='\033[0;36m'
COL_SUCCESS='\033[0;32m'
COL_WARN='\033[0;33m'
COL_ERROR='\033[0;31m'

# --- Flag Parsing ---
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

# === [ SECTION 2: LOGGING & UTILITY FUNCTIONS ] =======================================
log() {
  local type="$1"
  local msg="$2"
  local color="$COL_INFO"
  case "$type" in
    SUCCESS) color="$COL_SUCCESS" ;;
    WARN)    color="$COL_WARN" ;;
    ERROR)   color="$COL_ERROR" ;;
  esac
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') | ${color}${type^^}:${COL_RESET} ${msg}" | tee -a "$LOG_FILE"
}

die() {
  log "ERROR" "$1"
  exit 1
}

run_cmd() {
  log "EXEC" "$@"
  if ! $DRY_RUN; then
    eval "$@" >> "$LOG_FILE" 2>&1
  fi
}

check_dependencies() {
    log "INFO" "Checking for required tools..."
    for cmd in zip sqlite3 rclone; do
        if ! command -v "$cmd" &> /dev/null; then
            die "Required command '$cmd' is not installed. Aborting."
        fi
    done
    log "SUCCESS" "All required tools are present."
}

# === [ SECTION 3: SCRIPT WORKFLOW FUNCTIONS ] =========================================

create_backup_archive() {

    log "INFO" "Creating full project backup ZIP archive..."
    run_cmd "zip -r -q '$BACKUP_ZIP' . \
        -x '.git/*' -x 'venv/*' -x 'node_modules/*' -x '__pycache__/*' \
        -x 'backups/*' -x 'logs/*' -x 'git-update-push-logs/*' -x 'dev-logs/*' \
        -x 'reports/*' -x '*.DS_Store' -x '.env' -x 'inputs/*' -x 'outputs/*' \
        -x 'exports/*' -x 'art-uploads/*' -x 'audit/*' \
        -x 'assets/*' -x 'descriptions/*' -x 'gdws_content/*' -x 'mnt/*'"
    log "SUCCESS" "Backup ZIP created: $BACKUP_ZIP"
}

sync_to_cloud() {
    log "INFO" "Uploading backup to Google Drive ($GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER)..."
    run_cmd "rclone copy '$BACKUP_ZIP' '$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER' --progress" || log "ERROR" "Rclone upload failed. Check rclone configuration and network."

    log "INFO" "Applying cloud retention policy (keeping last $CLOUD_RETENTION_COUNT backups)..."
    local files_to_delete
    files_to_delete=$(rclone lsf "$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER" --format "tp" | sort -r | tail -n +$((CLOUD_RETENTION_COUNT + 1)) | cut -d';' -f2)

    if [[ -n "$files_to_delete" ]]; then
        log "WARN" "The following old backups will be deleted from the cloud:"
        echo "$files_to_delete" | tee -a "$LOG_FILE"
        while IFS= read -r file; do
            run_cmd "rclone delete '$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER/$file'"
        done <<< "$files_to_delete"
        log "SUCCESS" "Cloud retention policy applied."
    else
        log "INFO" "Fewer than $CLOUD_RETENTION_COUNT backups in the cloud. No cleanup needed."
    fi
}

# === [ SECTION 4: MAIN EXECUTION ] ====================================================
main() {
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"
    log "INFO" "=== 🛡️ ArtNarrator Automated Backup Initialized ==="
    if $DRY_RUN; then
        log "WARN" "Dry run mode is enabled. No actual changes will be made."
    fi

    check_dependencies
    create_backup_archive
    sync_to_cloud

    # Clean up the local backup files after successful upload
    log "INFO" "Cleaning up local backup files..."
    run_cmd "rm -f '$BACKUP_ZIP'"

    log "SUCCESS" "🎉 Automated backup workflow completed successfully. 💚"
}

# Kick off the main function
main


---
## generate_folder_tree.py
---
import os
from pathlib import Path

# ============================== [ CONFIGURATION ] ==============================

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR
OUTPUT_FILE = "folder_structure.txt"

# Folders or files to ignore (case insensitive)
# MODIFIED: Added user-specific and tool-specific dotfiles/folders to ignore
IGNORE_NAMES = {
    # Standard dev/tooling ignores
    ".git", "__pycache__", ".venv", "venv", "env", ".idea", ".DS_Store",
    "node_modules", ".nojekyll", ".pytest_cache", ".mypy_cache",
    ".ipynb_checkpoints", ".history", ".cache",
    # User-specific shell/config files from home directory
    ".bash_history", ".bash_logout", ".bashrc", ".profile", ".lesshst",
    ".python_history", ".selected_editor", ".wget-hsts",
    # Tool-specific config/cache folders
    ".codegpt", ".config", ".dotnet", ".local", ".sdkman", ".ssh", ".vscode-server"
}

# File extensions to ignore (add as needed, e.g., '.log', '.tmp')
IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".swp", ".log", ".tmp"
}

# ============================== [ HELPER FUNCTION ] ==============================

def should_ignore(entry):
    # Ignore by exact name (case insensitive)
    if entry.lower() in {x.lower() for x in IGNORE_NAMES}:
        return True
    # Ignore by extension
    _, ext = os.path.splitext(entry)
    if ext.lower() in IGNORE_EXTENSIONS:
        return True
    return False

def generate_tree(start_path: str, prefix: str = "") -> str:
    tree_str = ""
    try:
        entries = sorted(os.listdir(start_path))
    except PermissionError:
        # Skip protected dirs (shouldn’t happen, but just in case)
        return tree_str
    entries = [e for e in entries if not should_ignore(e)]

    for idx, entry in enumerate(entries):
        full_path = os.path.join(start_path, entry)
        connector = "└── " if idx == len(entries) - 1 else "├── "
        tree_str += f"{prefix}{connector}{entry}\n"

        if os.path.isdir(full_path):
            extension = "    " if idx == len(entries) - 1 else "│   "
            tree_str += generate_tree(full_path, prefix + extension)
    return tree_str

# ============================== [ MAIN EXECUTION ] ==============================

if __name__ == "__main__":
    print(f"📂 Generating folder structure starting at: {os.path.abspath(ROOT_DIR)}")
    tree_output = f"{os.path.basename(os.path.abspath(ROOT_DIR))}\n"
    tree_output += generate_tree(str(ROOT_DIR))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(tree_output)

    print(f"✅ Folder structure written to: {OUTPUT_FILE}")

---
## git-update-pull.sh
---
#!/bin/bash

# ======================================================================================
# 🔄 ArtNarrator Git Sync & Pre-Pull Backup Engine 🎨
#
# Version: 1.0
# Author: Robbie (adapted for ArtNarrator, July 2025, with ChatGPT)
#
# This script is designed to run after a PR/merge on the remote Git repo.
# It safely backs up the current state BEFORE pulling in new changes, for easy rollback.
#
# Workflow:
# 1. Backs up the current ArtNarrator code and database
# 2. Uploads this "pre-pull" backup to Google Drive (rclone)
# 3. Pulls latest code from the remote
# 4. Generates a Markdown report of what changed
# 5. Restarts the Gunicorn server to apply new code
#
# Usage examples:
#   ./git-update-pull.sh --full-auto      # Runs non-interactively
#   ./git-update-pull.sh --dry-run        # Only shows what would be done
#   ./git-update-pull.sh --no-pre-backup  # Skip backup/cloud sync
#   ./git-update-pull.sh --no-pull        # Skip git pull
#   ./git-update-pull.sh --no-report      # Skip project report
#   ./git-update-pull.sh --no-restart     # Skip server restart
# ======================================================================================

# === [ SECTION 1: SETUP & CONFIGURATION ] =============================================
set -euo pipefail

PROJECT_ROOT_DIR="$(pwd)"
LOG_DIR="${PROJECT_ROOT_DIR}/logs"
BACKUP_DIR="${PROJECT_ROOT_DIR}/backups"
DB_FILE="${PROJECT_ROOT_DIR}/data/artnarrator.db" # <<== Edit if your DB is elsewhere!
REPORT_SCRIPT="artnarrator-report.py"
GDRIVE_RCLONE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="artnarrator-backups"
CLOUD_RETENTION_COUNT=300

NOW=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/git-update-pull-${NOW}.log"
DB_DUMP_FILE="$BACKUP_DIR/pre-pull-db_dump_${NOW}.sql"
BACKUP_ZIP="$BACKUP_DIR/pre-pull-backup_${NOW}.zip"
PULL_DIFF_REPORT="$BACKUP_DIR/pull-diff-report_${NOW}.md"

# Gunicorn/Server config
GUNICORN_PID_FILE="/tmp/artnarrator-gunicorn.pid"
GUNICORN_CMD="${PROJECT_ROOT_DIR}/venv/bin/gunicorn"
GUNICORN_BIND_ADDRESS="0.0.0.0:7777" # <<== Edit if your port is different!
GUNICORN_WORKERS=4
GUNICORN_APP_MODULE="app:app" # <<== Edit if your WSGI entry is different!

# Colors for logging
COL_RESET='\033[0m'
COL_INFO='\033[0;36m'
COL_SUCCESS='\033[0;32m'
COL_WARN='\033[0;33m'
COL_ERROR='\033[0;31m'

# === [ SECTION 2: SCRIPT FLAGS & DEFAULTS ] ===========================================
AUTO_MODE=false
DRY_RUN=false
ENABLE_PRE_BACKUP=true
ENABLE_PULL=true
ENABLE_REPORT_SCRIPT=true
ENABLE_RESTART=true

# === [ SECTION 3: FLAG PARSER ] ======================================================
for arg in "$@"; do
  case $arg in
    --full-auto)     AUTO_MODE=true; shift ;;
    --dry-run)       DRY_RUN=true; shift ;;
    --no-pre-backup) ENABLE_PRE_BACKUP=false; shift ;;
    --no-pull)       ENABLE_PULL=false; shift ;;
    --no-report)     ENABLE_REPORT_SCRIPT=false; shift ;;
    --no-restart)    ENABLE_RESTART=false; shift ;;
    *) echo -e "${COL_ERROR}❌ Unknown option: $arg${COL_RESET}"; exit 1 ;;
  esac
done

# === [ SECTION 4: LOGGING & UTILITY FUNCTIONS ] =======================================
mkdir -p "$LOG_DIR"

log() {
  local type="$1"
  local msg="$2"
  local color="$COL_INFO"
  case "$type" in
    SUCCESS) color="$COL_SUCCESS" ;;
    WARN)    color="$COL_WARN" ;;
    ERROR)   color="$COL_ERROR" ;;
  esac
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') | ${color}${type^^}:${COL_RESET} ${msg}" | tee -a "$LOG_FILE"
}

die() {
  log "ERROR" "$1"
  exit 1
}

run_cmd() {
  log "EXEC" "$@"
  if ! $DRY_RUN; then
    eval "$@" >> "$LOG_FILE" 2>&1
  fi
}

check_dependencies() {
  log "INFO" "Checking for required tools..."
  local missing_deps=0
  for cmd in git zip sqlite3 rclone; do
    if ! command -v "$cmd" &> /dev/null; then
      log "ERROR" "Required command '$cmd' is not installed."
      missing_deps=$((missing_deps + 1))
    fi
  done
  if [ "$missing_deps" -gt 0 ]; then
    die "Aborting due to missing dependencies."
  fi
  log "SUCCESS" "All required tools are present."
}

# === [ SECTION 5: WORKFLOW FUNCTIONS ] ===============================================

# --- 5a: Pre-Pull Backup ---
handle_pre_pull_backup() {
  if ! $ENABLE_PRE_BACKUP; then
    log "WARN" "Skipping pre-pull backup as per --no-pre-backup flag."
    return
  fi

  log "INFO" "Starting pre-pull backup process..."

  # --- Database Dump ---
  if [ -f "$DB_FILE" ]; then
    log "INFO" "Creating SQLite database dump..."
    run_cmd "sqlite3 '$DB_FILE' .dump > '$DB_DUMP_FILE'"
    log "SUCCESS" "Database dump created: $DB_DUMP_FILE"
  else
    log "WARN" "Database file not found at $DB_FILE. Skipping dump."
  fi

# --- ZIP Archive ---
log "INFO" "Creating full project backup ZIP archive (pre-pull state)..."
run_cmd "zip -r -q '$BACKUP_ZIP' . \
    -x '.git/*' \
    -x 'venv/*' \
    -x 'node_modules/*' \
    -x '__pycache__/*' \
    -x 'backups/*' \
    -x 'logs/*' \
    -x 'dev_logs/*' \
    -x 'git-update-push-logs/*' \
    -x 'reports/*' \
    -x '*.DS_Store' \
    -x '.env' \
    -x 'inputs/*' \
    -x 'outputs/*' \
    -x 'example-images/*' \
    -x '*.sqlite3' \
    -x '*.pyc' \
    -x '*.pyo'"
log "SUCCESS" "Pre-pull backup ZIP created: $BACKUP_ZIP"

  # --- Cloud Sync ---
  log "INFO" "Uploading pre-pull backup to Google Drive..."
  run_cmd "rclone copy '$BACKUP_ZIP' '$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER' --progress" || log "ERROR" "Rclone upload failed. Check rclone configuration and network."
}

# --- 5b: Git Pull ---
handle_git_pull() {
  if ! $ENABLE_PULL; then
    log "WARN" "Skipping Git pull as per --no-pull flag."
    return
  fi

  log "INFO" "Preparing to pull updates from remote repository..."

  # Check for uncommitted changes
  if [[ -n $(git status --porcelain) ]]; then
    die "Working directory is not clean. Please commit or stash your changes before pulling."
  fi

  local pre_pull_hash
  pre_pull_hash=$(git rev-parse HEAD)
  log "INFO" "Current version (HEAD) is $pre_pull_hash"

  log "INFO" "Pulling latest changes from origin/main..."
  run_cmd "git pull origin main --rebase" || die "git pull --rebase failed. Please resolve conflicts manually."

  local post_pull_hash
  post_pull_hash=$(git rev-parse HEAD)
  log "SUCCESS" "Successfully pulled updates. New version (HEAD) is $post_pull_hash"

  # --- Diff Report (Post-Pull) ---
  log "INFO" "Generating report of changes pulled from remote..."
  local diff_content
  diff_content=$(git diff --name-status "$pre_pull_hash" "$post_pull_hash")
  {
    echo "# 🗂️ Git Pull Report — $(date '+%Y-%m-%d %H:%M %p')"
    echo ""
    echo "This report shows the file changes that were just pulled from the remote repository."
    echo ""
    echo "## Update Summary"
    echo "- **Previous Version:** \`$pre_pull_hash\`"
    echo "- **New Version:** \`$post_pull_hash\`"
    echo ""
    echo "## Files Updated"
    echo '```'
    if [[ -n "$diff_content" ]]; then
      echo "$diff_content"
    else
      echo "No new changes were pulled from the remote."
    fi
    echo '```'
  } > "$PULL_DIFF_REPORT"
  log "SUCCESS" "Pull diff report saved: $PULL_DIFF_REPORT"
}

# --- 5c: System Report ---
run_artnarrator_report() {
  if ! $ENABLE_REPORT_SCRIPT; then
    log "WARN" "Skipping ArtNarrator report script as per --no-report flag."
    return
  fi

  if [ -f "./$REPORT_SCRIPT" ]; then
    log "INFO" "Running ArtNarrator system report script..."
    run_cmd "python3 $REPORT_SCRIPT" || log "WARN" "The ArtNarrator report script encountered an error."
    log "SUCCESS" "System report script finished."
  else
    log "WARN" "ArtNarrator report script ('$REPORT_SCRIPT') not found. Skipping."
  fi
}

# --- 5d: Server Restart ---
restart_gunicorn_server() {
  if ! $ENABLE_RESTART; then
    log "WARN" "Skipping Gunicorn restart as per --no-restart flag."
    return
  fi

  log "INFO" "Initiating Gunicorn server restart to apply updates..."

  if [ -f "$GUNICORN_PID_FILE" ]; then
    log "INFO" "Found existing Gunicorn PID file. Attempting to stop the old server..."
    OLD_PID=$(cat "$GUNICORN_PID_FILE")
    if ps -p "$OLD_PID" > /dev/null; then
      run_cmd "kill $OLD_PID"
      log "INFO" "Sent stop signal to Gunicorn process $OLD_PID. Waiting for it to terminate..."
      for _ in {1..10}; do
        if ! ps -p "$OLD_PID" > /dev/null; then
          log "SUCCESS" "Old Gunicorn process has terminated."
          break
        fi
        sleep 1
      done
      if ps -p "$OLD_PID" > /dev/null; then
        log "WARN" "Gunicorn process $OLD_PID did not stop gracefully. Sending force kill."
        run_cmd "kill -9 $OLD_PID"
      fi
    else
      log "WARN" "PID $OLD_PID from PID file does not correspond to a running process. It might be stale."
    fi
    run_cmd "rm -f '$GUNICORN_PID_FILE'"
  else
    log "INFO" "No Gunicorn PID file found. Assuming server is not running."
  fi

  log "INFO" "Starting new Gunicorn server in daemon mode..."
  run_cmd "$GUNICORN_CMD --bind $GUNICORN_BIND_ADDRESS --workers $GUNICORN_WORKERS --daemon --pid '$GUNICORN_PID_FILE' $GUNICORN_APP_MODULE"

  sleep 2

  if [ -f "$GUNICORN_PID_FILE" ]; then
    NEW_PID=$(cat "$GUNICORN_PID_FILE")
    if ps -p "$NEW_PID" > /dev/null; then
      log "SUCCESS" "Gunicorn server restarted successfully. New PID is $NEW_PID."
    else
      die "Failed to start Gunicorn. PID file was created but no process found with PID $NEW_PID."
    fi
  else
    die "Failed to start Gunicorn. No PID file was created."
  fi
}

# === [ SECTION 6: main EXECUTION ] ==================================================
main() {
  mkdir -p "$BACKUP_DIR"
  log "INFO" "=== 🎨  ArtNarrator Sync & Update Script Initialized ==="
  if $DRY_RUN; then
    log "WARN" "Dry run mode is enabled. No actual changes will be made."
  fi

  check_dependencies
  handle_pre_pull_backup
  handle_git_pull
  run_artnarrator_report
  restart_gunicorn_server

  log "SUCCESS" "🎉 All done! ArtNarrator is updated and running. 💚"
}

main


---
## git-update-push.sh
---
#!/bin/bash

# ======================================================================================
# 🔁 ArtNarrator Gitflow Commander & Backup Engine 💥
#
# Version: 2.8
# Author: Robbie (Enhanced for ArtNarrator)
#
# This script automates the Git workflow, creates backups, and generates reports.
#
# ---
#
# Usage:
#   ./git-update-push.sh [options]
#
# Command Examples:
#   ./git-update-push.sh --full-auto      # Runs non-interactively
#   ./git-update-push.sh --dry-run        # Dry run (only shows commands)
#   ./git-update-push.sh --no-git         # Skips all Git operations
#   ./git-update-push.sh --no-zip         # Skips backup creation
#   ./git-update-push.sh --no-report      # Skips the report script
# ======================================================================================

# === [ SECTION 1: SETUP & CONFIGURATION ] ============================================
set -euo pipefail

# --- Project & Backup Configuration ---
PROJECT_ROOT_DIR="$(pwd)"
LOG_DIR="${PROJECT_ROOT_DIR}/logs"
BACKUP_DIR="${PROJECT_ROOT_DIR}/backups"

# --- Naming Conventions ---
NOW=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/git-update-push-${NOW}.log"
BACKUP_ZIP="$BACKUP_DIR/backup_${NOW}.zip"
DIFF_REPORT="$BACKUP_DIR/diff_report_${NOW}.md"
COMMIT_MSG_FILE=".codex-commit-msg.txt"

# --- Server Configuration ---
GUNICORN_PID_FILE="/tmp/artnarrator-gunicorn.pid"
GUNICORN_CMD="${PROJECT_ROOT_DIR}/venv/bin/gunicorn"
GUNICORN_BIND_ADDRESS="0.0.0.0:7777"
GUNICORN_WORKERS=4
GUNICORN_APP_MODULE="app:app"

# --- Colors for Logging ---
COL_RESET='\033[0m'
COL_INFO='\033[0;36m'
COL_SUCCESS='\033[0;32m'
COL_WARN='\033[0;33m'
COL_ERROR='\033[0;31m'

# === [ SECTION 2: SCRIPT FLAGS & DEFAULTS ] =========================================
AUTO_MODE=false
DRY_RUN=false
ENABLE_GIT=true
ENABLE_ZIP=true
ENABLE_REPORT_SCRIPT=true
ENABLE_RESTART=true

# === [ SECTION 3: FLAG PARSER ] =======================================================
for arg in "$@"; do
  case $arg in
    --full-auto)    AUTO_MODE=true; shift ;;
    --dry-run)      DRY_RUN=true; shift ;;
    --no-git)       ENABLE_GIT=false; shift ;;
    --no-zip)       ENABLE_ZIP=false; shift ;;
    --no-report)    ENABLE_REPORT_SCRIPT=false; shift ;;
    --no-restart)   ENABLE_RESTART=false; shift ;;
    *)              echo -e "${COL_ERROR}❌ Unknown option: $arg${COL_RESET}"; exit 1 ;;
  esac
done

# === [ SECTION 4: LOGGING & UTILITY FUNCTIONS ] =======================================
mkdir -p "$LOG_DIR"

log() {
  local type="$1"
  local msg="$2"
  local color="$COL_INFO"
  case "$type" in
    SUCCESS) color="$COL_SUCCESS" ;;
    WARN)    color="$COL_WARN" ;;
    ERROR)   color="$COL_ERROR" ;;
  esac
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') | ${color}${type^^}:${COL_RESET} ${msg}" | tee -a "$LOG_FILE"
}

die() {
  log "ERROR" "$1"
  exit 1
}

run_cmd() {
  log "EXEC" "$@"
  if ! $DRY_RUN; then
    eval "$@" >> "$LOG_FILE" 2>&1
  fi
}

check_dependencies() {
  log "INFO" "Checking for required tools..."
  local missing_deps=0
  for cmd in git zip sqlite3; do
    if ! command -v "$cmd" &> /dev/null; then
      log "ERROR" "Required command '$cmd' is not installed."
      missing_deps=$((missing_deps + 1))
    fi
  done
  if [ "$missing_deps" -gt 0 ]; then
    die "Aborting due to missing dependencies."
  fi
  log "SUCCESS" "All required tools are present."
}

# === [ SECTION 5: WORKFLOW FUNCTIONS ] ===============================================

# --- 5a: Git Operations ---
handle_git_operations() {
    if ! $ENABLE_GIT; then
        log "WARN" "Skipping all Git operations as per --no-git flag."
        return
    fi

    log "INFO" "Starting Git operations..."
    if [[ -z $(git status --porcelain) ]]; then
        log "SUCCESS" "Git working directory is clean. Nothing to commit."
        return
    fi

    run_cmd "git add ."

    local commit_msg
    if $AUTO_MODE; then
        if [[ -s "$COMMIT_MSG_FILE" ]]; then
            commit_msg=$(cat "$COMMIT_MSG_FILE")
            log "INFO" "Using automated commit message from $COMMIT_MSG_FILE."
        else
            commit_msg="Auto-commit: Routine system snapshot and updates on ${NOW}"
            log "INFO" "Using default automated commit message."
        fi
    else
        read -rp "📝 Enter commit message: " commit_msg
        if [[ -z "$commit_msg" ]]; then
            die "Commit message cannot be empty in interactive mode."
        fi
    fi

    run_cmd "git commit -m \"$commit_msg\""
    [[ -s "$COMMIT_MSG_FILE" ]] && rm -f "$COMMIT_MSG_FILE"

    log "INFO" "Pulling latest changes from origin/main..."
    run_cmd "git pull origin main --rebase" || die "git pull --rebase failed. Please resolve conflicts manually."

    log "INFO" "Pushing changes to origin/main..."
    run_cmd "git push origin main" || die "git push failed. Check remote repository and permissions."

    log "SUCCESS" "Git operations completed successfully."
}

# --- 5b: Backup and Reporting ---
create_backup_archive() {
    if $ENABLE_ZIP; then
        log "INFO" "Creating full project backup ZIP archive..."
        run_cmd "zip -r -q '$BACKUP_ZIP' . \
            -x '.git/*' \
            -x 'venv/*' \
            -x 'node_modules/*' \
            -x '__pycache__/*' \
            -x 'backups/*' \
            -x 'logs/*' \
            -x 'git-update-push-logs/*' \
            -x 'dev-logs/*' \
            -x 'reports/*' \
            -x '*.DS_Store' \
            -x '.env' \
            -x 'inputs/*' \
            -x 'outputs/*' \
            -x 'exports/*' \
            -x 'art-uploads/*' \
            -x 'audit/*' \
            -x 'assets/*' \
            -x 'descriptions/*' \
            -x 'gdws_content/*' \
            -x 'mnt/*'"
        log "SUCCESS" "Backup ZIP created: $BACKUP_ZIP"
    else
        log "WARN" "Skipping ZIP archive creation as per --no-zip flag."
    fi

    log "INFO" "Generating markdown diff report..."
    local diff_content
    if git rev-parse -q --verify HEAD~1 >/dev/null 2>&1; then
        diff_content=$(git diff --name-status HEAD~1 HEAD)
    else
        diff_content="Initial commit or no parent commit found."
    fi

    {
        echo "# 🗂️ Diff Report — $(date '+%Y-%m-%d %H:%M %p')"
        echo ""
        echo "This report shows the file changes included in this commit and backup."
        echo ""
        echo "## Summary"
        echo "- **Commit Message:** \`$(git log -1 --pretty=%B)\`"
        echo "- **Backup Archive:** \`$(basename "$BACKUP_ZIP")\`"
        echo ""
        echo "## Changed Files"
        echo '```'
        if [[ -n "$diff_content" ]]; then
            echo "$diff_content"
        else
            echo "No file changes detected in the last commit."
        fi
        echo '```'
    } > "$DIFF_REPORT"
    log "SUCCESS" "Markdown diff report saved: $DIFF_REPORT"
}

# --- 5c: Run ArtNarrator Report ---
run_artnarrator_report() {
    if ! $ENABLE_REPORT_SCRIPT; then
        log "WARN" "Skipping ArtNarrator report script as per --no-report flag."
        return
    fi

    log "INFO" "Running ArtNarrator system report script..."
    if [ -f "./artnarrator-report.sh" ]; then
        run_cmd "./artnarrator-report.sh" || log "WARN" "The ArtNarrator report script encountered an error."
        log "SUCCESS" "ArtNarrator report script finished."
    else
        log "WARN" "ArtNarrator report script ('artnarrator-report.sh') not found. Skipping."
    fi
}

# --- 5d: Server Restart ---
restart_gunicorn_server() {
    if ! $ENABLE_RESTART; then
        log "WARN" "Skipping Gunicorn restart as per --no-restart flag."
        return
    fi

    log "INFO" "Initiating Gunicorn server restart..."
    run_cmd "find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null"
    run_cmd "find . -type f -name '*.pyc' -delete"

    if [ -f "$GUNICORN_PID_FILE" ]; then
        log "INFO" "Found existing Gunicorn PID file. Attempting graceful restart..."
        local pid
        pid=$(cat "$GUNICORN_PID_FILE")
        run_cmd "kill -HUP $pid"
        sleep 2
        if ps -p "$pid" > /dev/null; then
            log "SUCCESS" "Gunicorn gracefully reloaded with new code (PID: $pid)."
            return
        else
            log "WARN" "Gunicorn process with PID $pid was not found. Proceeding with full restart."
            rm -f "$GUNICORN_PID_FILE"
        fi
    fi

    log "INFO" "Performing a full stop-and-start of Gunicorn."
    pkill -f "$GUNICORN_APP_MODULE" || log "INFO" "No running Gunicorn processes to kill."
    sleep 2

    log "INFO" "Starting new Gunicorn instance..."
    local gunicorn_start_cmd="nohup $GUNICORN_CMD --workers $GUNICORN_WORKERS --bind $GUNICORN_BIND_ADDRESS --pid $GUNICORN_PID_FILE $GUNICORN_APP_MODULE"
    run_cmd "$gunicorn_start_cmd &"
    sleep 3

    if [ -f "$GUNICORN_PID_FILE" ] && ps -p "$(cat $GUNICORN_PID_FILE)" > /dev/null; then
        log "SUCCESS" "Gunicorn server restarted successfully (PID: $(cat $GUNICORN_PID_FILE))."
    else
        die "Gunicorn failed to start. Check logs for details."
    fi
}


# === [ SECTION 6: MAIN EXECUTION ] ====================================================
main() {
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"
    log "INFO" "=== 🟢 ArtNarrator Sync & Update Script Initialized ==="
    if $DRY_RUN; then
        log "WARN" "Dry run mode is enabled. No actual changes will be made."
    fi

    check_dependencies
    handle_git_operations
    create_backup_archive
    run_artnarrator_report
    restart_gunicorn_server

    log "SUCCESS" "🎉 All done, Robbie! Workflow completed successfully. 💚"
}

# Kick off the main function
main


---
## package-lock.json
---
{
  "name": "artnarrator",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {}
}


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
fastapi==0.111.0
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
pytest==8.4.1
ImageHash==4.3.2
starlette==0.37.2
pathspec==0.12.1

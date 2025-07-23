# ROOT FILES CODE STACK (WED-23-JULY-2025-11-40-AM)


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
- Automated CSV/JSON exports for Etsy, Nembol, Gelato, and partners
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
- `exports/` — Output CSVs, logs, JSONs
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
- **CSV/JSON export** → only finalized artwork, strict Etsy/Nembol compliance, image URLs generated
- **Audit/QA scripts** → health checks, folder scans, export summaries, error reporting

---

## 🧠 AI/Prompt Engineering

- **All AI calls use master prompt templates** (e.g., `etsy_master_template.txt`, profiles in `settings.json`)
- Prompts must:
  - Exceed 400+ words, Pulitzer-worthy, culturally aware
  - Use proper SEO, avoid banned phrases, respect protocols
  - Output plain text (CSV/JSON safe), no HTML
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
- All export flows (CSV, JSON) must pass strict pre-export checks.
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

📦 Sellbrite/Nembol CSV Exporter

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

### Sellbrite CSV Export Script

The `scripts/sellbrite_csv_export.py` tool converts Etsy CSV exports or
finalised listing JSON files into a Sellbrite ready CSV. Provide the
Sellbrite template for the header and specify your input files:

```bash
python scripts/sellbrite_csv_export.py template.csv output.csv --etsy exported.csv
```

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_MODEL_FALLBACK = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4-turbo")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")

# --- Google Cloud ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", "art-narrator")
GOOGLE_VISION_MODEL_NAME = os.getenv("GOOGLE_VISION_MODEL_NAME", "builtin/stable")
GOOGLE_GEMINI_PRO_VISION_MODEL_NAME = os.getenv("GOOGLE_GEMINI_PRO_VISION_MODEL_NAME", "gemini-pro-vision")

# --- Other Integrations ---
RCLONE_REMOTE_NAME = os.getenv("RCLONE_REMOTE_NAME", "gdrive")
RCLONE_REMOTE_PATH = os.getenv("RCLONE_REMOTE_PATH", "art-backups")
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

# -----------------------------------------------------------------------------
# 4. HELPER/REGISTRY FILES (ONLY WHAT'S USED)
# -----------------------------------------------------------------------------
SKU_TRACKER = SETTINGS_DIR / "sku_tracker.json"
ANALYSIS_STATUS_FILE = LOGS_DIR / "analysis_status.json"
ONBOARDING_PATH = SETTINGS_DIR / "Master-Etsy-Listing-Description-Writing-Onboarding.txt"
OUTPUT_JSON = OUTPUTS_DIR / "artwork_listing_master.json"

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
IGNORE_NAMES = {
    ".git", "__pycache__", ".venv", "venv", "env", ".idea", ".DS_Store",
    "node_modules", ".nojekyll", ".pytest_cache", ".mypy_cache", 
    ".ipynb_checkpoints", ".history"
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
Flask==3.1.1
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
threadpoolctl==3.6.0
tqdm==4.67.1
typing-inspection==0.4.1
typing_extensions==4.14.0
tzdata==2025.2
urllib3==2.5.0
Werkzeug==3.1.3
gunicorn
google-generativeai==0.5.0
google-cloud-vision==3.10.2
SQLAlchemy==2.0.30
passlib==1.7.4

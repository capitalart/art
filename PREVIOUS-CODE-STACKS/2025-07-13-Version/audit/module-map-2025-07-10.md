# ART Narrator Module Map Audit (2025-07-10)

This document lists the major modules in the ART Narrator codebase, summarises the key files for each, and describes how they interact. Files used across multiple modules are listed in **Shared/Core Files**. Potentially unused or obsolete files are noted separately.

## Upload Module

### Backend / Python Files
- `routes/artwork_routes.py` – `upload_artwork` route handles image uploads, processes each file and redirects after success【F:routes/artwork_routes.py†L194-L223】

### Templates
- `templates/upload.html` – upload form UI.
- `templates/upload_results.html` – shows per-file results.
- `templates/artworks.html` – gallery page displaying ready, processed and finalised artworks【F:routes/artwork_routes.py†L224-L232】.

### Connection Map
- `upload.html` submits to `/upload` which invokes `_process_upload_file` in `artwork_routes.py`, storing files under `inputs/` and logging results.

## Analyze Module

### Backend / Python Files
- `routes/artwork_routes.py` – `analyze_artwork_route` executes `scripts/analyze_artwork.py` and logs OpenAI analysis results【F:routes/artwork_routes.py†L308-L336】.
- `scripts/analyze_artwork.py` – command line script performing artwork analysis with OpenAI【F:scripts/analyze_artwork.py†L1-L17】.

### Templates
- `templates/review.html` – displays AI-generated listing and mockup previews.

### Connection Map
- `/analyze/<aspect>/<filename>` runs the script and redirects to `/review` once the composite generation completes.

## Edit Listing Module

### Backend / Python Files
- `routes/artwork_routes.py` – `edit_listing` loads listing JSON, allows updates, and saves changes【F:routes/artwork_routes.py†L519-L555】.

### Templates
- `templates/edit_listing.html` – form to edit metadata, preview images, and finalise listings.

### Connection Map
- Links from gallery and finalised pages call `/edit-listing/<aspect>/<filename>`; form submissions post back to the same endpoint for validation and saving.

## Finalised Module

### Backend / Python Files
- `routes/artwork_routes.py` – `finalised_gallery` builds a list of finalised artworks from `outputs/finalised-artwork` and renders the page【F:routes/artwork_routes.py†L905-L956】.

### Templates
- `templates/finalised.html` – gallery view for completed listings.

### Connection Map
- After finalisation actions, routes redirect to `/finalised` to show locked items and download-ready images.

## GDWS (Generic Description Writing System)

### Backend / Python Files
- `routes/gdws_admin_routes.py` – manages paragraph templates in `gdws_content/` and provides AI rewriting via `utils.ai_services`【F:routes/gdws_admin_routes.py†L1-L34】【F:routes/gdws_admin_routes.py†L72-L100】.

### Templates
- `templates/dws_editor.html` – main editor with drag‑and‑drop interface.
- `templates/gdws_base_editor.html` – page for editing base paragraph text.

### Config / Data Files
- `gdws_content/` – JSON files storing paragraph variations.

### Connection Map
- Admin pages under `/admin/gdws/*` load paragraph JSON, allow regeneration via AI, then save back to `gdws_content/`.

## Mockup Generation Module

### Backend / Python Files
- `routes/mockup_routes.py` – upload and categorise mockups using OpenAI vision【F:routes/mockup_routes.py†L1-L32】【F:routes/mockup_routes.py†L68-L109】.
- `scripts/generate_composites.py` – generates artwork composites based on coordinate JSON【F:scripts/generate_composites.py†L1-L29】【F:scripts/generate_composites.py†L88-L116】.

### Templates
- `templates/mockups/upload.html` – admin upload form.
- `templates/mockups/gallery.html` – list of categories per aspect.
- `templates/mockups/detail.html` – edit metadata for a single mockup.

### Config / Data Files
- `inputs/Coordinates/` – corner coordinates used for compositing.

### Connection Map
- Uploaded mockups are saved under `inputs/mockups/<aspect>-categorised/<category>` with corresponding coords JSON. Composite generation script uses these to overlay artworks.

## Export / CSV Module

### Backend / Python Files
- `routes/export_routes.py` – admin interface to run Sellbrite CSV exports【F:routes/export_routes.py†L60-L106】.
- `scripts/sellbrite_csv_export.py` – maps artwork JSON data to Sellbrite CSV format【F:scripts/sellbrite_csv_export.py†L1-L28】【F:scripts/sellbrite_csv_export.py†L161-L216】.

### Templates
- `templates/sellbrite_exports.html` – lists generated CSV files.
- `templates/sellbrite_csv_preview.html` – preview a CSV table before download.
- `templates/sellbrite_log.html` – view export warnings.

### Connection Map
- `/exports/sellbrite/run` gathers finalised listings and calls `sellbrite_csv_export.py`, saving CSVs under `outputs/sellbrite/`.

## Admin / Tools Module

### Backend / Python Files
- `routes/admin_routes.py` – admin pages for prompt options, security toggles, and session management【F:routes/admin_routes.py†L1-L33】【F:routes/admin_routes.py†L52-L78】.
- `routes/admin_debug.py` – debugging utilities including AI parse tester and system status【F:routes/admin_debug.py†L1-L32】【F:routes/admin_debug.py†L34-L43】.
- `login_bypass.py` – temporary login bypass state manager【F:login_bypass.py†L1-L28】【F:login_bypass.py†L30-L38】.
- `no_cache_toggle.py` – global cache-busting toggle for static files【F:no_cache_toggle.py†L1-L18】【F:no_cache_toggle.py†L40-L54】.
- `routes/session_tracker.py` – tracks active admin sessions to enforce limits【F:routes/session_tracker.py†L1-L28】【F:routes/session_tracker.py†L29-L60】.

### Templates
- `templates/admin/git_log.html`, `templates/admin/security.html`, `templates/admin/cache_control.html`, `templates/admin/sessions.html`, `templates/debug_parse_ai.html`, `templates/debug_status.html`.

### Connection Map
- All admin pages require the `admin` role. Security tools write state files under `logs/` and affect behaviour in `app.py` via context processors.

## AIGW / Prompt Modules

### Backend / Python Files
- `routes/aigw_routes.py` – AI image prompt builder with selectable options【F:routes/aigw_routes.py†L4-L21】【F:routes/aigw_routes.py†L191-L205】.
- `routes/prompt_whisperer.py` – generates short prompts for inspiration via OpenAI【F:routes/prompt_whisperer.py†L1-L34】【F:routes/prompt_whisperer.py†L52-L79】.
- `routes/prompt_options.py` – API endpoint serving JSON option lists【F:routes/prompt_options.py†L1-L11】.

### Templates
- `templates/aigw.html` – AI prompt builder form.
- `templates/prompt_whisperer.html` – one-click prompt generator UI.
- `templates/prompt_generator.html` – static page referencing prompt options.

### Config / Data Files
- `config/ai_prompt_options/*.json` – genre, style, palette and other option lists.
- `static/data/art_categories.json` – categories for prompt whisperer dropdown.

### Connection Map
- These routes allow admins to craft AI prompts, save them under `outputs/aigw_prompts/`, and fetch selectable options via `/api/prompt-options/<category>`.

## Shared/Core Files

- `app.py` – main Flask entrypoint registering all blueprints and injecting cache/login helpers【F:app.py†L14-L30】【F:app.py†L40-L59】.
- `config.py` – global path and setting definitions used by scripts and routes【F:config.py†L20-L48】【F:config.py†L68-L96】.
- `auth.py` – login/logout logic with session tracking【F:auth.py†L1-L28】【F:auth.py†L30-L43】.
- `routes/utils.py` – shared helper functions for listings, mockup handling and SKU management【F:routes/utils.py†L1-L34】【F:routes/utils.py†L240-L318】.
- `utils/sku_assigner.py` – sequential SKU allocation utilities【F:utils/sku_assigner.py†L7-L30】.
- `utils/ai_services.py` – wrapper functions to call OpenAI or Gemini for text rewriting【F:utils/ai_services.py†L1-L30】【F:utils/ai_services.py†L36-L63】.
- `static/css/base.css`, `static/css/layout.css`, `static/css/components.css`, `static/css/theme.css` – core stylesheets【F:static/css/base.css†L1-L5】.
- `static/js/main.js` – theme toggle and navigation logic【F:static/js/main.js†L1-L6】.

## Obsolete/Unreferenced Files

- `static/css/legacy_style_unused.css` – old stylesheet not referenced by templates.
- `assets/style.css` – standalone CSS file seemingly unused in current templates.
- `mockup_categoriser.py`, `smart_sign_artwork.py`, `smart_sign_test01.py`, `sort_and_prepare_midjourney_images.py` – standalone scripts not imported by the Flask app.

---

# ✅ Codex Prompt QA & Handover Protocol (Robbie Mode™ Standard)

### 1. 📄 Description of Work
- Compiled a full module map summarising backend scripts, templates and assets for each functional area.
- Listed how uploads, analysis, mockup generation, editing, finalisation, CSV export, admin tools and prompt utilities connect.
- Flagged unused files and identified shared/core modules.

### 2. 🔐 Security & Permissions
- Notes routes requiring the `admin` role (`/admin/*`, `/exports/*`).
- Session tracking via `routes/session_tracker.py` prevents excessive logins.
- Login bypass and cache toggles are restricted to admins.

### 3. 🧪 Testing Coverage
- No new tests added for this documentation-only task. Existing tests remain under `tests/` for routes, uploads and SKU logic.

### 4. 🧠 Logic & Flow Checks
- Verified major workflow routes: upload → analyze → review/edit → finalise/export.
- Confirmed error handling in `analyze_artwork_route` and `edit_listing` for missing files or invalid data.

### 5. 🎨 Frontend/UI Consistency
- Templates extend `main.html` and use shared CSS/JS.
- Dark mode toggle handled in `static/js/main.js` and `theme.css`.

### 6. 🧹 Housekeeping
- Identified unused scripts and legacy stylesheets for potential cleanup.
- Core helpers centralised in `routes/utils.py` and `config.py`.

### 7. 🧭 Navigation & Discovery
- Sidebar/navigation built via `get_menu()` in `routes/utils.py` ensures links to gallery, mockups, and admin tools.

### 8. 🧾 Logging & Audit Trails
- Analysis and composite scripts log to `logs/` via paths set in `config.LOGS_DIR`.
- Admin actions (login bypass, cache control) append entries to their respective history logs.

### 9. 🧰 DevOps & Deployment
- No deployment scripts modified. Environment variables read from `.env` as documented in `README.md`.

### 10. 🧠 Metadata & Tracking
- CHANGELOG and QA reports remain unchanged for this audit. Output saved to `audit/module-map-2025-07-10.md` for reference.


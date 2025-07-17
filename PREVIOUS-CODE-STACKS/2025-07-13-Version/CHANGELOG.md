## 2025-07-06
- Added admin debug blueprint with `/admin/debug/status`, `/admin/debug/parse-ai` and `/admin/debug/next-sku` endpoints.
- New templates `debug_status.html` and `debug_parse_ai.html` with navigation link from `main.html`.
- Expanded `config.py` with folder constants such as `DEV_LOGS_DIR`, `PARSE_FAILURE_DIR` and `GIT_LOG_DIR`; all critical folders created on import.
- Updated `app.py` to register the admin blueprint and handle missing endpoints.
- Tests now cover admin debug routes and ensure template URLs are valid.
- Refactored `art_narrator_total_rundown.py` to rely on `DEV_LOGS_DIR` from `config`.
- Added TODO note for securing admin debug endpoints.

## 2025-07-07
- Sellbrite export now includes Materials and DWS columns and populates Tags and Materials from listing JSON.
- Updated `sellbrite_template.csv` header to match new columns.
- CSV rows now reflect locked status and digital wall size when present.

## 2025-07-08
- Added dark/light mode toggle with persistent preference and accessible colour palettes.
- Refactored `style.css` into modular `base.css`, `layout.css`, `components.css` and `theme.css`.
- Updated all templates to load modular CSS and include theme toggle.
- Docs updated with usage notes.
- *AI commit*

## 2025-07-09
- Theme toggle now uses SVG icons from the Phosphor set with persistent user preference.
- Updated `main.js` logic for loading theme and showing the correct icon.
- Added README note about icon locations and CHANGELOG reminders.

## 2025-07-10
- Polished theme toggle icons with better accessibility and removed inline sizing.

## 2025-07-11
- Updated Sellbrite CSV template path to `docs/csv_product_template.csv`.
- CSV exports now quote all fields for Sellbrite/Etsy compatibility.
- Added `docs/CSV_EXPORT.md` and referenced it from README.
- Removed old template copy from repo root.

## 2025-07-12
- Added AI Image Generator Whisperer UI with genre/style selectors and summary panel.
- New blueprint `aigw_routes.py`, template `aigw.html`, and navigation link.
- Config updated with `AIGW_PROMPTS_DIR` and `AIGW_OPTIONS_FILE` constants.

## 2025-07-13
- Improved banner contrast for login bypass notice.
- Updated export sidebar link labels for clarity.

## 2025-07-14
- Removed legacy sidebar templates and scripts.
- Added feature flag `ENABLE_UPGRADE` for subscription links.
- Navigation cleaned up with admin tools in profile menu and new Docs dropdown.
- Created module-specific How-To pages and navigation overview docs.

## 2025-07-15
- Finalised Society6-style top navigation order and removed Analyze link.
- Account, Upgrade and Admin links now visible only for admins.
- Updated How-To Guides index and navigation docs.
- Added automated tests for nav visibility.

## 2025-07-16
- Integrated Sellbrite API for product creation when locking artworks.
- Added `utils/sellbrite_api.py` and manual push endpoint.
- New documentation `SELLBRITE_INTEGRATION.md`.
## 2025-07-17
- Added systemd service files `artnarrator.service` and `ezygallery.service` for Gunicorn deployment.
- Updated nginx config to proxy `artnarrator.com` to port 8070 and `ezygallery.com` to port 8080.
- Documented systemd deployment steps in README.
## 2025-07-18
- Added `systemd/` directory with template service units and a new
  `scripts/setup_systemd_services.sh` installer.
- Updated README with installation instructions for the services.
- *AI commit*

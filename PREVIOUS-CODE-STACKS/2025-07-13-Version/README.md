# 🎨 ART Narrator Mockup Generator

Welcome to **ART Narrator** — a modular, AI-powered mockup generation and listing system for digital artists, creators, and print-on-demand pros.

> **Built by Robin Custance — proud Aboriginal Aussie artist and part-time Kangaroo whisperer 🦘🎨**

This project helps you **bulk-organise, analyse, and preview** professional mockups for platforms like Etsy, with future-proof features and strong cultural integrity.

---

## 🔧 Project Features

- ✅ **Mockup Categorisation** using OpenAI Vision (GPT-4.1 / GPT-4o)
- ✅ **Automatic Folder Sorting** by AI-detected room type (Living Room, Bedroom, Nursery, etc.)
- ✅ **Flask UI** to preview random mockups (1 per category)
- ✅ **Swap/Regenerate** to get the best match for your artwork
- ✅ **Composite Generation Ready** for finalising mockups with your art
- ✅ **Multi-Aspect Support** (4:5, 1:1, more coming)
- ✅ **Mockup Categoriser Admin UI** for uploading and reviewing mockups
- ✅ **Sellbrite/Nembol CSV Exporter** and platform field mapping
- ✅ **SKU Assignment** logic for seamless listing management
- ✅ **Admin/debug tools** and robust audit trail (now with `/admin/debug/git-log`)
- ✅ **Admin-only login with persistent sessions**
- ✅ **Production-ready audit/report scripts** for system health and codebase snapshots
- ✅ **Dark/Light Mode Toggle** with persistent preference
- ✅ **AI Image Generator Whisperer** with genre and style selectors

---

## 📚 **Essential Docs & Reference Files**

> **ALL CONTRIBUTORS (human or AI) must review these before making changes.**  
> `README.md` and `CHANGELOG.md` MUST be updated with every code, logic, config, or template change.

- **Full System Blueprint:**  
  [`mnt/data/Full-Rundown.txt`](mnt/data/Full-Rundown.txt)
- **Codebase & Folder Tree Snapshot:**  
  [`mnt/data/report_code_snapshot_reports-08-jul-2025-10-35pm.md`](mnt/data/report_code_snapshot_reports-08-jul-2025-10-35pm.md)
- **Live Folder Structure:**  
  [`mnt/data/folder_structure.txt`](mnt/data/folder_structure.txt)
- **CHANGELOG:**  
  [`CHANGELOG.md`](CHANGELOG.md) — **Update on EVERY CHANGE!**

- **Mockup templates, scripts, and config:**  
  See `/mnt/data/master_listing_templates/`, `/mnt/data/scripts/`, `/mnt/data/config.py`

---

## 📁 Folder Structure

See the **full current structure** in [`mnt/data/folder_structure.txt`](mnt/data/folder_structure.txt).

```bash
ART-Narrator-Mockup-Generator/
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
├── reports/
├── scripts/
├── routes/
├── static/
├── templates/
├── config.py
├── app.py
├── CHANGELOG.md
├── README.md
└── ...
🆕 Running the Modular App
The Flask application is launched via app.py, which registers modular feature blueprints.


pip install -r requirements.txt
python app.py
Set your environment variables in .env (see .env.example)

Main UI: http://localhost:5050/

Admin/debug endpoints: /admin/debug/*
  - `/admin/debug/git-log` shows recent commits

See routes/artwork_routes.py for main route definitions

### Systemd Deployment
Two Gunicorn services keep the apps running in production:
- **artnarrator.service** — serves `app:app` on port **8070**.
- **ezygallery.service** — serves `app:app` on port **8080**.

Template unit files live in the repo under `systemd/` and are
installed to `/etc/systemd/system/` using
`scripts/setup_systemd_services.sh`. Each service runs from the project
virtual environment at `venv/`.

Nginx proxies `artnarrator.com` to `127.0.0.1:8070` and `ezygallery.com`
to `127.0.0.1:8080`.


⚡️ Contributor & Codex Rules
README.md and CHANGELOG.md must be updated with EVERY code or config change
(Document: date, section/file, summary, author/AI)

All changes must follow naming, folder, and sectioning rules from mnt/data/Full-Rundown.txt

No partial edits or code snippets — always full files or clear section rewrites

All code files must have TOC, docstrings, and permanent section codes

No HTML in CSV/exports; all outputs must be CSV-safe and platform compliant

🔥 Project Usage Details
Blueprint Endpoint Names
All templates use blueprint-prefixed endpoints (e.g., url_for('artwork.home') not url_for('home')) to avoid BuildError.

### Dark/Light Mode & Themed CSS
The UI ships with a theme toggle in the main navigation. Your preferred theme is stored in `localStorage` and applied on every visit without flashing. All styles now come from the consolidated `theme.css` under `static/css/`.
The navigation bar collapses into a hamburger menu below 700&nbsp;px for a fully mobile experience.
Icon assets for this button live in `static/icons/svg/light/` (`sun-dim-light.svg` and `moon-light.svg`). Replace these icons to customise the look and always log changes in `CHANGELOG.md`.
Add new theme variables inside `theme.css` and extend components as needed.

Navigation links keep a consistent weight on hover for smoother interaction.
The header bar uses `--nav-bg` to remain pale grey in light mode and black in
dark mode. Theme toggle icons automatically invert when dark mode is active.

Sellbrite Field Mapping
See generate_sellbrite_json() in routes/sellbrite_export.py:

JSON field	Sellbrite field
title	name
description	description
tags	tags
materials	materials
primary_colour	primary_colour
secondary_colour	secondary_colour
seo_filename	seo_filename
sku	sku
price	price
images	images

Sellbrite CSV Export Script

python scripts/sellbrite_csv_export.py template.csv output.csv --etsy exported.csv
Or use --json-dir to read from finalised folders.

Environment Variables
Set via .env (see .env.example):


OPENAI_API_KEY=your-key-here
OPENAI_PRIMARY_MODEL=gpt-4o
OPENAI_FALLBACK_MODEL=gpt-4.1
FLASK_SECRET_KEY=your-flask-secret
DEBUG=true
PORT=5050
SELLBRITE_TOKEN=your-sellbrite-token
SELLBRITE_SECRET=your-sellbrite-secret
ADMIN_USER=robbie
ADMIN_PASS=changeme

See `SELLBRITE_INTEGRATION.md` for details on the API workflow.

The application automatically falls back to `gpt-4.1` and then `gpt-4-turbo` if the configured
primary model isn't available.

The web UI requires authentication. Visit `/login` and use the credentials above.
SKU Assignment
Sequential SKUs tracked in settings/sku_tracker.json (config.SKU_TRACKER)

SKUs assigned only at finalisation; previewed in analysis

/next-sku route shows next available SKU for admins

OpenAI prompt gets assigned_sku so AI never invents a SKU

Running Unit Tests

Runs all tests under tests/ to verify core logic.

## How-To & Documentation Pages

The UI exposes simple help pages for each module. They can be reached from the
"Docs" dropdown in the top navigation:

- `/docs/howto-home`
- `/docs/howto-upload`
- `/docs/howto-analyze`
- `/docs/howto-gallery`
- `/docs/howto-exports`
- `/docs/howto-whisperer`

Additional general info lives under `/docs/faq`, `/privacy`, `/terms` and `/about`.
Set `ENABLE_UPGRADE=true` in your environment to show the `/upgrade` page link.

### Top Navigation Order
The header follows a Society6‑style layout:

1. Artwork Home (logo)
2. Upload
3. Gallery
4. Finalised
5. Exports
6. Prompt Whisperer
7. Docs dropdown (How‑To, FAQ, About, Terms, Privacy)
8. Profile menu (Login/Logout and admin tools)

## Dynamic Mega Menu
All templates are auto-discovered at startup and grouped by folder.
Click the **Menu** button in the header to open a fullscreen overlay
listing every page. Add a new `.html` file anywhere under `templates/`
and the menu will include it after the next restart. Custom logic lives
in `menu_loader.py` and can be overridden with an optional `menu.json`.

🛠️ In Development
🖼 Composite Generator (artwork overlay onto mockups)

🧼 Finalisation Script (move print files, generate web preview)

📦 Sellbrite/Nembol CSV Exporter

🖼 Aspect Ratio Selector support

📱 Mobile/responsive UI

👨‍🎨 About the Artist
Hi, I’m Robin Custance — proud Aboriginal Aussie artist and art technologist, living on Kaurna Country (Adelaide), with Boandik roots (Naracoorte).
This project helps share stories, support family, and bring ethical art automation to life.

💌 Contact
rob@asbcreative.com.au
robincustance.etsy.com

📢 Need Help or Reporting Issues?
Check mnt/data/Full-Rundown.txt and CHANGELOG.md first

Contact Robin directly or file an issue with details

QA Reports for each folder are automatically generated. See `QA_MASTER.md` for a consolidated index.

Legend’s note:
If any file, doc, or script goes missing, always check /mnt/data/ and run the latest code snapshot or QA script to restore full context.

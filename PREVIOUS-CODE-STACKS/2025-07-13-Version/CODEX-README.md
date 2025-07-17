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

- `routes/` — FastAPI route modules (upload, analyze, mockup, export, etc)
- `services/` — Core logic (AI analysis, prompt generation, business workflows)
- `utils/` — File handling, helpers, templates, content blocks
- `core/` — Global config, settings, environment vars, constants
- `templates/` — Jinja2 HTML templates, organized by subfolders for menus
- `static/` — CSS, icons, images (served statically)
- `mockup-generator/` — Mockup templates, coordinates, category folders
- `data/` — SQLite database and settings.json
- `master_listing_templates/` — Master OpenAI prompt templates (e.g. etsy_master_template.txt)
- `exports/` — Output CSVs, logs, JSONs

**Entry Point:**  
- `main.py` (imports all routers, sets up app, configures templates & error handlers)

---

## 🔥 Collaboration & Coding Rules

**You must:**
- Write **production-quality**, professionally sectioned and fully commented code
- Use clear section headers and permanent section/subsection codes for every file (see below)
- Never break, regress, or remove existing functionality without explicit instruction
- If rewriting, always do **full-file rewrites** (not fragments) unless otherwise stated
- Add or improve documentation, comments, and file TOC as needed

**Sectioning:**  
- Each code file must have a Table of Contents at the top, mapping all section/subsection codes.
- Example codes: `analyze-routes-py-2a` (see Full-Rundown for details).
- All functions/classes must have proper docstrings.

**When in doubt, ask for clarification before proceeding!**

---

## 🛠️ Core Workflows (Do NOT Break)

- **Artwork upload** → temp-processing dir, DB entry
- **AI analysis** (OpenAI/Gemini Vision + GPT) → generate title, description, attributes, tags (see `etsy_master_template.txt`)
- **Mockup generation** → batch create, strict naming (`{seo_filename}-MU-01.jpg` etc), review/finalise
- **Finalisation** → all files moved to `/finalised-artwork/{seo_folder}/`, DB paths updated, QA checks
- **CSV/JSON export** → only finalized artwork, strict Etsy/Nembol compliance, image URLs generated
- **Audit/QA scripts** → health checks, folder scans, export summaries, error reporting

---

## 🧠 AI/Prompt Engineering

- **AI calls always use master templates** (`etsy_master_template.txt`, profiles in `settings.json`)
- All OpenAI prompts must:  
  - Hit 400+ words, Pulitzer-worthy, Aussie wit, proper curation analysis  
  - Use proper SEO, avoid banned phrases, respect cultural protocols  
  - Exclude HTML, always output plain text/CSV-safe content  
  - Reference relevant content blocks (aspect ratio, dot art history) as needed

- **Model/version is set in config or env**—fallback to last known good if error.
- All prompt logic, settings, and version must be logged for traceability.

---

## 📦 File/Folder/Naming Conventions

- All finalized images and files must live under `/finalised-artwork/{seo_folder}/`
  - Main: `{seo_filename}.jpg`
  - Mockups: `{seo_filename}-MU-01.jpg`, ... `-MU-10.jpg`
  - Thumb: `{seo_filename}-thumb.jpg`
  - OpenAI: `{seo_filename}-openai.jpg`
  - JSON/sidecar: `{seo_filename}-listing.json`
- Temp uploads use unique batch folders, auto-cleaned on finalize
- Image URLs must be absolute/public for export (e.g. `/static/finalised-artwork/...`)

---

## 🚦 Quality Control & Testing

- All major flows are covered by audit/reporting scripts—never break audit compatibility.
- Add/extend pytest coverage for all new logic.
- All export flows (CSV, JSON) must pass strict pre-export checks.

---

## 🔑 Security & Permissions

- All admin, delete, or finalize actions must check for role/permission.
- User/session logic must be robust and ready for future multi-user expansion.
- API keys, passwords, and sensitive info only in .env or config (never hardcoded).

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

## 💡 Project Owner’s Tips

- “Full file rewrites, clear sectioning, real comments, always QA after changes”
- “When unsure, ask! Don’t break what works.”
- “Keep it neat, keep it professional, keep it Robbie Mode™.”

---

# END OF CODEX-README

Before starting, Codex must:
1. Read this file fully
2. Reference it when making any decisions, file changes, or additions
3. Double check that all logic, standards, and naming conventions are followed

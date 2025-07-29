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

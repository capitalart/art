---
```markdown
# ✅ Codex Prompt QA & Handover Protocol (Robbie Mode™ Standard)
This file defines the **official project-wide QA checklist** and **handover documentation format** required for all Codex-generated tasks, patches, and pull requests across ART Narrator or any future system using Robbie Mode™.

---

## codex-prompts/README-CODEX-PROMPT-ACTIONS.md

## 🧠 Purpose
Codex must include this structure as a **QA signoff sheet** and attach it as a `.md` file for every prompt it runs. It is designed for:

- ✅ Human-readable code reviews
- ✅ Automated changelog generation
- ✅ Git history documentation
- ✅ QA auditing and deployment prep

This file is **generic** and must never reference a specific feature.

---

## 🔁 When to Apply
Every Codex prompt **must append this structure** to its `.md` output:
- Whether creating, refactoring, debugging, or optimizing.
- Whether the task affects backend, frontend, devops, or docs.
- Whether the request was large or small.

---

## 📌 Format (Always Use This Structure)

### 1. 📄 Description of Work
- Concise summary of what was built, fixed, removed, or upgraded.
- Reference any files, templates, routes, or modules affected.
- Explain *why* the change was needed or what problem it solves.

---

### 2. 🔐 Security & Permissions
- Confirm if any routes, pages, forms, or actions require user roles (`admin`, `user`, etc).
- Ensure all authentication and role-based access checks were implemented.
- Mention if CSRF or session logic was updated or verified.
- Document any login/session-based constraints or logic (e.g. session limits, bypass toggles).

---

### 3. 🧪 Testing Coverage
- Confirm if unit tests were added or updated.
- Mention any `tests/` coverage added (including what it verifies).
- List manual browser tests, CLI tests, or curl/postman tests if applicable.

---

### 4. 🧠 Logic & Flow Checks
- Validate core logic paths (e.g. conditional checks, fallbacks).
- Confirm graceful error handling and user feedback on all forms/buttons.
- State if error flash messages, redirects, or 404/403s were added or verified.

---

### 5. 🎨 Frontend/UI Consistency
- Ensure templates match `theme.css`, mobile responsiveness, and layout hierarchy.
- Mention if any new `.css`, `.js`, or `main.html` includes were required.
- Validate if UI components (alerts, buttons, toggles) are visible and responsive.

---

### 6. 🧹 Housekeeping
- Remove any debugging code, unused imports, or leftover comments.
- Apply code style formatting (e.g. `black`, `flake8`, or system formatter).
- Follow section headers and file structure rules (e.g. `# === SECTION ===` style).
- Use shared constants (e.g. `config.LOGS_DIR`, `settings.json`) where available.

---

### 7. 🧭 Navigation & Discovery
- If user-facing, confirm feature is accessible in the UI (e.g. via sidebar, admin menu).
- Confirm proper active state logic is applied (e.g. `active` class for nav).
- Validate breadcrumbs or contextual hints (e.g. page titles, hints, tooltips).

---

### 8. 🧾 Logging & Audit Trails
- Mention where logs are saved (`logs/*.log`, `.json`, or `.txt`).
- Confirm logs are human-readable and redact sensitive data.
- State log event structure: timestamps, user/session info, action types.

---

### 9. 🧰 DevOps & Deployment
- List any changes to `.env`, Docker, or deployment scripts.
- Confirm if new files should be added or excluded from `.gitignore`.
- If new config keys were added, confirm fallback values and defaults.
- Mention if CRON jobs, rclone uploads, or background workers were triggered or changed.

---

### 10. 🧠 Metadata & Tracking
- Confirm updates to:
  - `QA_AUDIT_INDEX.md`
  - `CHANGELOG.md`
  - `SITEMAP.md`
  - `task_list.md`
- Confirm version bump in `version.json` if applicable.
- Mention if `.md` documentation was created or updated.

---

## 📁 Filename Convention for Codex Prompt Handover
Codex must save each completed task handover using the following format:

```

XX-\[Feature-Title]-\[DD-MMMM-YYYY-HH-MM-AMPM].md

```

Example:
```

52-Force-No-Cache-System-With-Admin-Toggle-Auto-Expiry-10-July-2025-11-40PM.md

```

Where `XX` is the task number, tracked in `QA_AUDIT_INDEX.md`.

---

## 📎 File Storage Location
All `.md` prompt handovers must be saved into:

```

/codex-prompts/

```

---

## 🧷 Final Notes
- Codex should **never modify this file** unless explicitly requested.
- Codex must refer to this in every PR and `.md` output.
- Codex should apply the full 10-point QA check automatically and include it in prompt output, review logs, and audit trails.

---

💚 Powered by Robbie Mode™ — codex with conscience, structure, and artfulness.
```

---

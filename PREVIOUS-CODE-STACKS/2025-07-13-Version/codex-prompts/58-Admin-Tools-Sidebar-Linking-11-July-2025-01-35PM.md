# 58-Admin-Tools-Sidebar-Linking-11-July-2025-01-35PM

**System:** ART Narrator / ArtNarrator  
**Task:** Ensure all admin/toggle/tool pages are discoverable via sidebar and navigation  
**Author:** Robbie Custance  
**QA Steps:** `/codex-prompts/README-CODEX-PROMPT-ACTIONS.md`

---

## 🟢 Task Description

You are Codex.  
Your job is to audit all admin/tool/toggle routes and templates in the ART Narrator project and ensure every admin tool page is accessible via the sidebar and/or a visible admin dropdown in the main navigation, **but only for users with the `admin` role**.

**Goal:**  
- All implemented admin features (cache control, login bypass, git log, sessions, debug status, etc.) must be accessible to admins via the web UI.
- All navigation links must use the proper Flask/Jinja routes.
- All changes must be fully documented in the QA reports, with before/after navigation maps.

---

## 🟢 Required Actions

1. **Scan backend and templates** for all admin/tool/toggle pages:
    - `/admin/cache-control`
    - `/admin/security` or `/admin/login-bypass`
    - `/admin/git-log`
    - `/admin/sessions`
    - `/admin/debug-status`
    - Any others found in `routes/admin_routes.py`, `routes/admin_debug.py`, etc.

2. **Edit `templates/components/sidebar.html`:**
    - Add sidebar links for all admin/tool/toggle pages.
    - Group admin tools in a clear “Admin Tools” section, visible only to users with the `admin` role (e.g., `if session.get('role') == 'admin'`).
    - Use human-readable names: “Cache Control”, “Login Bypass”, “Git Log”, “Active Sessions”, “Debug Status”, etc.

3. *(Optional)* **Update top nav in `templates/main.html`:**
    - Add an “Admin” dropdown (or link) if you want admin tools in the main nav as well, using the same role-check.

4. **Ensure all navigation uses Flask’s `url_for` function.**

5. **Test that each linked page loads, is protected by admin checks, and matches its function.**

6. **Update QA documentation:**
    - In `/QA_REPORT.md` and `/QA_MASTER.md`, update the “Navigation & Discovery” section to show the new sidebar/menu structure.
    - Document the new/updated links and any changes to access logic.
    - Append the full QA checklist from `/codex-prompts/README-CODEX-PROMPT-ACTIONS.md`.

---

## 🟢 Output Format

- Paste the full, updated content of:
    - `templates/components/sidebar.html` (with all new admin links)
    - Any other templates you touch (e.g., `main.html`)
    - `/QA_REPORT.md` (and `/QA_MASTER.md` if changed)
- Show **before/after** navigation/sidebars as a code block in the QA report for easy diffing.
- Append the completed QA checklist for all changed files.

---

## 🟢 Extra Instructions

- Do NOT remove any existing admin links unless confirmed obsolete.
- Keep all admin tools grouped together for clarity.
- Use `{% if session.get('role') == 'admin' %}` (or your site’s standard) to protect admin sections.
- Use `url_for('admin.cache_control')`, `url_for('admin.security')`, etc., to generate links.
- If a route or template is missing or misnamed, flag it in the QA and suggest a fix.

---

## 🟢 Example Admin Tools Section (Sidebar)

```jinja
{% if session.get('role') == 'admin' %}
  <div class="sidebar-section">
    <h4>Admin Tools</h4>
    <ul>
      <li><a href="{{ url_for('admin.cache_control') }}">Cache Control</a></li>
      <li><a href="{{ url_for('admin.security') }}">Login Bypass</a></li>
      <li><a href="{{ url_for('admin.git_log') }}">Git Log</a></li>
      <li><a href="{{ url_for('admin.sessions') }}">Active Sessions</a></li>
      <li><a href="{{ url_for('admin.debug_status') }}">Debug Status</a></li>
    </ul>
  </div>
{% endif %}
```

*Codex must discover all implemented admin tools and link them using the correct route names.*

---

## 🟢 QA Reference

MANDATORY:
Append and complete the QA checklist from `/codex-prompts/README-CODEX-PROMPT-ACTIONS.md` for all changed files.

---

**Now: scan, update, and connect all admin pages in the sidebar/nav, and bring the frontend up to true Robbie Mode™ discoverability!**


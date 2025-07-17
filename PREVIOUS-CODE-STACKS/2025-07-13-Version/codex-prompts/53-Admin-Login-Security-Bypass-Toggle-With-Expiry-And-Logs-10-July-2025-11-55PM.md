🧠 Codex Prompt — Admin Login Security Bypass Toggle (With Expiry & Logs)
Prompt title: 53-Admin-Login-Security-Bypass-Toggle-With-Expiry-And-Logs-10-July-2025-11-55PM.md

🧾 Prompt Description:
You are Codex. You will build and integrate a **secure admin-only toggle system** for temporarily bypassing login protection across the ArtNarrator system (for internal dev use only). This must follow Robbie Mode™ engineering principles and include logging, auto-expiry, context processor injection, UI feedback, and admin panel controls.

---

✅ Functional Requirements

1. **Admin Toggle UI**
    - New admin page: `/admin/login-bypass`
    - Contains toggle ON/OFF button, current status, and expiry time
    - Access only allowed if `session['role'] == 'admin'`

2. **Bypass Mechanism**
    - When enabled, override login-required decorators to **bypass** user authentication site-wide.
    - Only for internal use during debugging/development.

3. **Auto-Disable After 2 Hours**
    - System must automatically revert to "OFF" state after 2 hours.
    - Use UTC time for all comparisons and expiry enforcement.

4. **Session-Based Indicator**
    - When bypass is active, display a banner across the top of all pages:
      - Text: “🟡 Login system is temporarily bypassed by admin”
      - Class: `login-bypass-banner`
    - Banner must not show when bypass is off or expired.

5. **Log History & State**
    - Save current status in `logs/login_bypass_state.json`
    - Append every action to `logs/login_bypass_history.log`
    - Log the following actions:
        * ENABLED
        * DISABLED
        * AUTO-OFF (EXPIRED)

6. **Template Integration**
    - Inject bypass status using Flask context processor:
        - Use `@app.context_processor` to inject `is_login_bypass_enabled()` globally
    - Make sure all templates can access this safely:
        ```jinja
        {% if login_bypass_enabled %}
          <div class="login-bypass-banner">🟡 Login system is temporarily bypassed by admin</div>
        {% endif %}
        ```

---

📁 Required Files

| File | Action |
|------|--------|
| `login_bypass_toggle.py` | Create — logic to manage state, logs, and expiry |
| `routes/admin_routes.py` | Modify — add new route `/admin/login-bypass` |
| `templates/admin/login_bypass.html` | New admin UI template |
| `templates/main.html` | Modify — inject visual banner via `{% if login_bypass_enabled %}` |
| `templates/components/mega_menu.html` | Modify — add new Admin Tools link |
| `logs/` | Append logs to `login_bypass_history.log`, write toggle state to `login_bypass_state.json` |
| `app.py` | Modify — inject context processor and `is_login_bypass_enabled()` |
| `auth_decorator.py` (or wherever login_required is defined) | Modify — wrap login protection check with toggle-aware logic |

---

🧠 Logic Notes

* Bypass only if:
    - Toggle is explicitly ON
    - Current time < 2 hour expiry time
* Ensure logic doesn't apply to:
    - Static file routes
    - Admin routes
* Use UTC timestamps in ISO format in the JSON log file.

---

🔒 Security & Guardrails

* Admin-only access to toggle route
* Auto-expiry enforced at middleware level
* All log files in `logs/` must not expose passwords or credentials
* No scaffold code or placeholder logic

---

✅ Codex Prompt Handover Notes™ (Robbie Mode™ Standard)

🧷 Auto-attach this in the PR:
## ✅ Codex Prompt Handover Notes™: 53-Admin-Login-Security-Bypass-Toggle-With-Expiry-And-Logs-10-July-2025-11-55PM.md

---

### 1. 📄 Description of Work
- Built secure system-wide login bypass feature
- Added UI toggle in `/admin/login-bypass`
- Auto-disables after 2 hours
- Visual banner injected if active

---

### 2. 🔐 Security & Permissions
- Admin-only access
- Decorator or middleware logic safely overrides login if active and unexpired
- Logs actions and expiry to disk

---

### 3. 🧪 Testing Coverage
- Manual toggling confirmed in dev
- Expiry tested with short TTL
- Logs verified in both JSON and plaintext history formats

---

### 4. 🧠 Logic & Flow Checks
- Toggle state read on each page load
- Auto-expiry checks current time
- Banner only displays if truly active

---

### 5. 🎨 Frontend/UI Consistency
- Reused `login-bypass-banner` class
- Admin UI matches rest of admin panel
- Responsive and accessible design

---

### 6. 🧹 Housekeeping
- Logs go to `logs/login_bypass_*`
- All new files documented with `# === SECTION HEADERS ===`
- Fully Robbie Mode™ compliant

---

### 7. 🧭 Navigation & Discovery
- Added to `Admin Tools` in `mega_menu.html` (until sidebar migration complete)

---

### 8. 🧾 Logging & Audit Trails
- JSON + text logs with timestamps and actions
- Auto-off event logged if bypass expires

---

### 9. 🧰 DevOps & Deployment
- No `.env` additions
- Compatible with Gunicorn & production modes
- Backward-safe with login-required logic

---

### 10. 🧠 Metadata & Tracking
- Feature listed in `QA_AUDIT_INDEX.md`
- Available in `SITEMAP.md` if routes are public
- Version incremented if using `version.json`

---

💥 End of Prompt

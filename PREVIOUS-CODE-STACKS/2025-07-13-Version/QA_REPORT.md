# QA Report: .
_Audit date: 2025-07-09 19:00 UTC_

| File | Purpose/Role | Status | Issues |
|------|--------------|--------|--------|
| .env.example | - | ✅ | - |
| .gitignore | =================================================================== | ✅ | - |
| .nojekyll | - | ❌ | File is empty |
| CHANGELOG.md | 2025-07-06 | ⚠️ | Contains TODO/FIXME |
| FETCH_HEAD | - | ❌ | File is empty |
| LICENSE | - | ✅ | - |
| README.md | 🎨 ART Narrator Mockup Generator | ✅ | - |
| app.py | ART Narrator application entrypoint. | ✅ | - |
| auth.py | - | ✅ | - |
| art_narrator_total_rundown.py | !/usr/bin/env python3 | ✅ | - |
| art_narrator.py | !/usr/bin/env python3 | ✅ | - |
| config.py | Central configuration for the ART Narrator project. | ✅ | - |
| csv_product_template.csv | - | ✅ | - |
| folder_structure.txt | - | ✅ | - |
| generate_folder_tree.py | - | ✅ | - |
| git-update-pull.sh | !/bin/bash | ✅ | - |
| git-update-push.sh | !/bin/bash | ✅ | - |
| mockup_categoriser.py | ============================== [ mockup_categoriser.py ] ======================= | ✅ | - |
| package-lock.json | - | ✅ | - |
| requirements.txt | - | ✅ | - |
| run_codex_patch.py | !/usr/bin/env python3 | ✅ | - |
| setup_gunicorn.sh | !/bin/bash | ✅ | - |
| setup_node_sharp.sh | !/usr/bin/env bash | ✅ | - |
| smart_sign_artwork.py | Batch-sign artworks with colour-contrasting signatures. | ✅ | - |
| smart_sign_test01.py | === [ SmartArt Sign System: ART Narrator Lite | by Robin Custance | Robbiefied Edi | ✅ | - |
| sort_and_prepare_midjourney_images.py | - | ✅ | - |
| version.json | - | ✅ | - |

---
## Next Steps
- [ ] Review `.nojekyll`
- [ ] Review `CHANGELOG.md`
- [ ] Review `FETCH_HEAD`

### 1. 📄 Description of Work
- Added comprehensive admin tools menu in `templates/components/sidebar.html` with links to cache control, login bypass, git log, active sessions, prompt options, parse AI, next SKU, and system status.
- Restricted admin links to users with `session['role'] == 'admin'`.
- Footer admin link in `templates/main.html` now only visible to admins.
- **Updated banner contrast and renamed export links for clarity.**

### 7. 🧭 Navigation & Discovery
```diff
-      <li class="has-children">
-        <div class="section-header">Admin / Tools <span class="toggle-icon">▸</span></div>
-        <ul>
-          <li><a href="{{ url_for('admin.debug_status') }}" class="{% if request.path == url_for('admin.debug_status') %}active{% endif %}">Overview / Usage</a></li>
-          <li><a href="#">User Management</a></li>
-          <li><a href="{{ url_for('admin_routes.git_log') }}" class="{% if request.path == url_for('admin_routes.git_log') %}active{% endif %}">QA Audit Tools</a></li>
-          <li><a href="{{ url_for('admin_routes.active_sessions') }}" class="{% if request.path == url_for('admin_routes.active_sessions') %}active{% endif %}">Active Sessions</a></li>
-        </ul>
-      </li>
{% if session.get('role') == 'admin' %}
      <li class="has-children">
        <div class="section-header">Admin Tools <span class="toggle-icon">▸</span></div>
        <ul>
          <li><a href="{{ url_for('admin.debug_status') }}" class="{% if request.path == url_for('admin.debug_status') %}active{% endif %}">System Status</a></li>
          <li><a href="{{ url_for('admin_routes.cache_control') }}" class="{% if request.path == url_for('admin_routes.cache_control') %}active{% endif %}">Cache Control</a></li>
          <li><a href="{{ url_for('admin_routes.security') }}" class="{% if request.path == url_for('admin_routes.security') %}active{% endif %}">Login Bypass</a></li>
          <li><a href="{{ url_for('admin_routes.git_log') }}" class="{% if request.path == url_for('admin_routes.git_log') %}active{% endif %}">Git Log</a></li>
          <li><a href="{{ url_for('admin_routes.active_sessions') }}" class="{% if request.path == url_for('admin_routes.active_sessions') %}active{% endif %}">Active Sessions</a></li>
          <li><a href="{{ url_for('admin_routes.prompt_options_editor') }}" class="{% if request.path == url_for('admin_routes.prompt_options_editor') %}active{% endif %}">Prompt Options</a></li>
          <li><a href="{{ url_for('admin.parse_ai') }}" class="{% if request.path == url_for('admin.parse_ai') %}active{% endif %}">Parse AI</a></li>
          <li><a href="{{ url_for('admin.preview_next_sku_admin') }}" class="{% if request.path == url_for('admin.preview_next_sku_admin') %}active{% endif %}">Next SKU</a></li>
          {# TODO: route missing - user management page #}
        </ul>
      </li>
{% endif %}
```


# 🟢 Sidebar Links Validation Report (Date: 2025-07-11)

## ✅ Existing Links Confirmed
- `admin.debug_status` → templates/debug_status.html
- `admin_routes.git_log` → templates/admin/git_log.html
- `artwork.home` → templates/index.html
- `artwork.upload_artwork` → templates/upload.html
- `artwork.select` → templates/mockup_selector.html
- `artwork.artworks` → templates/artworks.html
- `artwork.finalised_gallery` → templates/finalised.html
- `mockups.index` → templates/mockups/index.html
- `mockups.upload` → templates/mockups/upload.html
- `exports.sellbrite_exports` → templates/sellbrite_exports.html
- `admin_routes.active_sessions` → templates/admin/sessions.html
- `gdws_admin.editor` → templates/dws_editor.html
- `whisperer.index` → templates/prompt_whisperer.html
- `prompt_ui.prompt_generator` → templates/prompt_generator.html
- `gdws_admin.base_editor` → templates/gdws_base_editor.html

## 🆕 New Placeholder Templates Created
- templates/mockups/review.html
- templates/mockups/categories.html
- templates/exports/nembol.html
- templates/admin/user_management.html
- templates/templates_components/email_templates.html
- templates/templates_components/listing_templates.html
- templates/documentation/project_readme.html
- templates/documentation/changelog.html
- templates/documentation/qa_audit_index.html
- templates/documentation/task_list.html
- templates/documentation/delete_candidates.html
- templates/documentation/sitemap.html
- templates/documentation/api_reference.html
- templates/documentation/how_to_guides.html
- templates/documentation/faq.html

## 🚧 Backend Routes Added
- routes/mockup_routes.py – `review()` and `categories()`
- routes/export_routes.py – `nembol()`
- routes/admin_routes.py – `user_management()`
- routes/gdws_admin_routes.py – `email_templates()`, `listing_templates()`
- routes/documentation_routes.py – multiple documentation routes

## 🔗 Sidebar Link Corrections
- `href="#"` → `href="{{ url_for('mockups.review') }}``
- `href="#"` → `href="{{ url_for('mockups.categories') }}``
- `href="#"` → `href="{{ url_for('exports.nembol') }}``
- `href="#"` → `href="{{ url_for('admin_routes.user_management') }}``
- `href="#"` → `href="{{ url_for('gdws_admin.email_templates') }}``
- `href="#"` → `href="{{ url_for('gdws_admin.listing_templates') }}``
- `href="#"` → `href="{{ url_for('documentation.project_readme') }}``
- `href="#"` → `href="{{ url_for('documentation.changelog') }}``
- `href="#"` → `href="{{ url_for('documentation.qa_audit_index') }}``
- `href="#"` → `href="{{ url_for('documentation.task_list') }}``
- `href="#"` → `href="{{ url_for('documentation.delete_candidates') }}``
- `href="#"` → `href="{{ url_for('documentation.sitemap') }}``
- `href="#"` → `href="{{ url_for('documentation.api_reference') }}``
- `href="#"` → `href="{{ url_for('documentation.how_to_guides') }}``
- `href="#"` → `href="{{ url_for('documentation.faq') }}``

## 📝 Notes/Recommendations
- Further enhancement can link documentation pages to real content once available.
- Migrated OpenAI model settings into `config.py` and updated brand to "ART Narrator" across templates.

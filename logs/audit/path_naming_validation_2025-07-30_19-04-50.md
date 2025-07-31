# 🚨 Path & Filename Validation Report
**Generated:** 2025-07-30T19:04:51.139271
**Project Root:** `/home/art`


---
### `gunicorn.conf.py`
- ❌ Hardcoded absolute path: `/home/art/logs/gunicorn/gunicorn-access.log`
- ❌ Hardcoded absolute path: `/home/art/logs/gunicorn/gunicorn-error.log`

---
### `routes/analyze_routes.py`
- ⚠️  Filename has illegal characters/spaces: `{artwork_id}`

---
### `routes/artwork_routes.py`
- ⚠️  Filename has illegal characters/spaces: `<base>`
- ⚠️  Filename has illegal characters/spaces: `<filename>`
- ⚠️  Filename has illegal characters/spaces: `<int:slot_idx>`
- ⚠️  Filename has illegal characters/spaces: `<path:filename>`
- ⚠️  Filename has illegal characters/spaces: `<path:filepath>`
- ⚠️  Filename has illegal characters/spaces: `<seo_folder>`

---
### `routes/export_routes.py`
- ⚠️  Filename has illegal characters/spaces: `<path:log_filename>`

---
### `routes/gdws_admin_routes.py`
- ⚠️  Filename has illegal characters/spaces: `<aspect_ratio>`

---
### `routes/mockup_admin_routes.py`
- ⚠️  Filename has illegal characters/spaces: `<aspect>`
- ⚠️  Filename has illegal characters/spaces: `<path:filename>`

---
### `templates/finalised.html`
- ⚠️  Filename has illegal characters/spaces: `div>
      {% endif %}
      {% if art.images %}
      <details class=`
- ⚠️  Filename has illegal characters/spaces: `div>
<script src=`

---
### `templates/index.html`
- ⚠️  Filename has illegal characters/spaces: `h1>
  <p class=`

---
### `templates/locked.html`
- ⚠️  Filename has illegal characters/spaces: `div>
      {% endif %}
      {% if art.images %}
      <details class=`
- ⚠️  Filename has illegal characters/spaces: `div>
<script src=`

---
### `templates/main.html`
- ⚠️  Filename has illegal characters/spaces: `div>
            <div class=`
- ⚠️  Filename has illegal characters/spaces: `div>
        <div class=`
- ⚠️  Filename has illegal characters/spaces: `header>

    <div id=`
- ⚠️  Filename has illegal characters/spaces: `svg>
                <svg class=`

---
### `templates/partials/topnav.html`
- ⚠️  Filename has illegal characters/spaces: `>
        <circle cx=`
- ⚠️  Filename has illegal characters/spaces: `>
        <path d=`
- ⚠️  Filename has illegal characters/spaces: `a>
    <nav role=`
- ⚠️  Filename has illegal characters/spaces: `div>
  <div class=`
- ⚠️  Filename has illegal characters/spaces: `svg>
      <svg id=`

---
### `tests/test_analyze_artwork.py`
- ⚠️  Filename has illegal characters/spaces: `{filename}`

---
### `tools/audit/path_naming_validator.py`
- ❌ Hardcoded absolute path: `/Users/`
- ❌ Hardcoded absolute path: `/home/`

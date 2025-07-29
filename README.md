# 🎨 ArtNarrator Mockup Generator

Welcome to **ArtNarrator**, a lightweight yet powerful mockup generation system designed to categorise, preview, and finalise high-quality mockups for digital artworks — all from the comfort of your local environment or server.

This system helps artists like me (Robin Custance — Aboriginal Aussie artist and part-time Kangaroo whisperer 🦘🎨) bulk-organise, intelligently analyse, and preview professional product mockups for marketplaces like Etsy.

---

## 🔧 Project Features

- ✅ **Mockup Categorisation** using OpenAI Vision (gpt-4o / gpt-4-turbo)
- ✅ **Automatic Folder Sorting** based on AI-detected room types
- ✅ **Flask UI** to preview randomly selected mockups (1 per category)
- ✅ **Swap / Regenerate** functionality for better aesthetic control
- ✅ **Ready for Composite Generation** and final publishing
- ✅ Designed to support multiple **aspect ratios** like 4:5, 1:1, etc.

---

## 📁 Folder Structure

```bash
Artnarrator-Mockup-Generator/
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
└── mockup_selector_ui.py

pip install -r requirements.txt



Flask
openai
python-dotenv
Pillow
requests


🧩 In Development
🖼 Composite Generator (overlay artwork onto mockups)

🧼 Finalisation Script (move print files, create web preview)

📦 Sellbrite Exporter

🖼 Aspect Ratio Selector Support

🇦🇺 About the Artist
Hi, I’m Robin Custance — proud Aboriginal Aussie artist and storyteller through colour and dots. I live on Kaurna Country in Adelaide, with ancestral ties to the Boandik people of Naracoorte.

This project supports my mission to share stories through art while helping my family thrive. ❤️

⚡ Contact
💌 rob@asbcreative.com.au

🌐 robincustance.etsy.com

📷 Insta coming soon...
## 🆕 Running the Modular App

The Flask application is now launched via `app.py` which registers feature blueprints. Start the server with:

```bash
python app.py
```

Routes from `artnarrator.py` were moved to `routes/artwork_routes.py`. More modules will follow as the project evolves.

### Blueprint Endpoint Names

All templates must reference routes using their blueprint-prefixed endpoint names. For example, use `url_for('artwork.home')` instead of `url_for('home')`. This avoids `BuildError` when looking up URLs.

### Logging & Image Responses

Routes never return raw `bytes` or base64 data. Images are served exclusively with `send_file` or `send_from_directory` so the browser receives the correct mime type. Log entries strip any binary fields using `utils.strip_binary` before writing, ensuring audit logs and JSON responses remain readable.

### Sellbrite Field Mapping

The helper `generate_sellbrite_json()` in `routes/sellbrite_export.py` converts
our artwork listing data to the fields expected by Sellbrite's Listings API.

| JSON field       | Sellbrite field |
|------------------|-----------------|
| title            | name            |
| description      | description     |
| tags             | tags            |
| materials        | materials       |
| primary_colour   | primary_colour  |
| secondary_colour | secondary_colour|
| seo_filename     | seo_filename    |
| sku              | sku             |
| price            | price           |
| images           | images          |


Use `--json-dir` to read from the finalised artwork folders instead.


### Environment Variables

Create a `.env` file based on `.env.example` and set the following values:

```
OPENAI_API_KEY=your-key-here
OPENAI_PRIMARY_MODEL=gpt-4o
OPENAI_FALLBACK_MODEL=gpt-4-turbo
FLASK_SECRET_KEY=your-flask-secret
DEBUG=true
PORT=5050
SELLBRITE_TOKEN=your-sellbrite-token
SELLBRITE_SECRET=your-sellbrite-secret
```

These credentials enable OpenAI features and allow authenticated calls to the
Sellbrite API.

### SKU Assignment

All new listings receive a sequential SKU tracked in the JSON file defined by
`config.SKU_TRACKER` (defaults to `config.SETTINGS_DIR / "sku_tracker.json"`).
SKUs are allocated only when an artwork is finalised using
`utils.sku_assigner.get_next_sku(SKU_TRACKER)`. During analysis a preview of the
next SKU may be obtained with `peek_next_sku(SKU_TRACKER)` and is available via
the `/next-sku` route for admins.
The preview value is injected into the OpenAI prompt as `assigned_sku` so the AI
never invents a SKU. Listing pages display the SKU as a read-only field sourced
from the JSON file.

### Running the Unit Tests

After installing dependencies with `pip install -r requirements.txt`, run the repository's tests using:

```bash
pytest
```

This command executes all tests under the `tests/` directory to ensure routes and artwork analysis behave correctly.

### Admin Suite & Roles

The application now stores users and site settings in `data/artnarrator.sqlite3`.
Three roles are supported:

- **admin** – full access to `/admin` tools
- **editor** – manage artworks and listings
- **viewer** – read-only access

Admins may manage users and security settings from `/admin`. Login can be temporarily disabled for non-admins, and cache headers can be forced across the site. Use the user management page to add or remove users and set their roles.


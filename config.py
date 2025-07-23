"""
config.py — ArtNarrator & DreamArtMachine (Robbie Mode™, July 2025)
Central config: All core folders, env vars, limits, AI models, templates.
All code must import config.py and reference only these values!
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Load .env file from project root ---
load_dotenv()

# === PROJECT ROOT ===
BASE_DIR = Path(__file__).resolve().parent

# -----------------------------------------------------------------------------
# 1. ENV/BRANDING/ADMIN
# -----------------------------------------------------------------------------
BRAND_NAME = os.getenv("BRAND_NAME", "Art Narrator")
BRAND_TAGLINE = os.getenv("BRAND_TAGLINE", "Create. Automate. Sell Art.")
BRAND_AUTHOR = os.getenv("BRAND_AUTHOR", "Robin Custance")
BRAND_DOMAIN = os.getenv("BRAND_DOMAIN", "artnarrator.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "robincustance@gmail.com")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "robbie")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "kangaroo123")
SERVER_PORT = int(os.getenv("SERVER_PORT", "7777"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
HOST = os.getenv("HOST", "127.0.0.1")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "supersecret-key-1234")
PORT = int(os.getenv("PORT", "7777"))

# -----------------------------------------------------------------------------
# 2. AI/PLATFORM/API MODELS
# -----------------------------------------------------------------------------
# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_MODEL_FALLBACK = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4-turbo")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")

# --- Google Cloud ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", "art-narrator")
GOOGLE_VISION_MODEL_NAME = os.getenv("GOOGLE_VISION_MODEL_NAME", "builtin/stable")
GOOGLE_GEMINI_PRO_VISION_MODEL_NAME = os.getenv("GOOGLE_GEMINI_PRO_VISION_MODEL_NAME", "gemini-pro-vision")

# --- Other Integrations ---
RCLONE_REMOTE_NAME = os.getenv("RCLONE_REMOTE_NAME", "gdrive")
RCLONE_REMOTE_PATH = os.getenv("RCLONE_REMOTE_PATH", "art-backups")
SELLBRITE_API_BASE_URL = os.getenv("SELLBRITE_API_BASE_URL", "https://api.sellbrite.com/v1")
ETSY_SHOP_URL = os.getenv("ETSY_SHOP_URL", "https://www.robincustance.etsy.com")

# -----------------------------------------------------------------------------
# 3. FOLDER STRUCTURE & PATHS (STRICTLY WHAT'S LIVE)
# -----------------------------------------------------------------------------
ART_PROCESSING_DIR = Path(os.getenv("ART_PROCESSING_DIR", BASE_DIR / "art-processing"))
UNANALYSED_ROOT = ART_PROCESSING_DIR / "unanalysed-artwork"
PROCESSED_ROOT = ART_PROCESSING_DIR / "processed-artwork"
FINALISED_ROOT = ART_PROCESSING_DIR / "finalised-artwork"
ARTWORK_VAULT_ROOT = ART_PROCESSING_DIR / "artwork-vault"

OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", BASE_DIR / "outputs"))
COMPOSITES_DIR = OUTPUTS_DIR / "composites"
SELECTIONS_DIR = OUTPUTS_DIR / "selections"
SELLBRITE_DIR = OUTPUTS_DIR / "sellbrite"
SIGNED_DIR = OUTPUTS_DIR / "signed"

MOCKUPS_INPUT_DIR = Path(os.getenv("MOCKUPS_INPUT_DIR", BASE_DIR / "inputs" / "mockups"))
SIGNATURES_DIR = Path(os.getenv("SIGNATURES_DIR", BASE_DIR / "inputs" / "signatures"))
GENERIC_TEXTS_DIR = Path(os.getenv("GENERIC_TEXTS_DIR", BASE_DIR / "generic_texts"))
COORDS_DIR = Path(os.getenv("COORDS_DIR", BASE_DIR / "inputs" / "Coordinates"))

SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", BASE_DIR / "scripts"))
SETTINGS_DIR = Path(os.getenv("SETTINGS_DIR", BASE_DIR / "settings"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", BASE_DIR / "logs"))
CODEX_LOGS_DIR = Path(os.getenv("CODEX_LOGS_DIR", BASE_DIR / "CODEX-LOGS"))
STATIC_DIR = Path(os.getenv("STATIC_DIR", BASE_DIR / "static"))
TEMPLATES_DIR = Path(os.getenv("TEMPLATES_DIR", BASE_DIR / "templates"))
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "artnarrator.sqlite3"

# -----------------------------------------------------------------------------
# 4. HELPER/REGISTRY FILES (ONLY WHAT'S USED)
# -----------------------------------------------------------------------------
SKU_TRACKER = SETTINGS_DIR / "sku_tracker.json"
ANALYSIS_STATUS_FILE = LOGS_DIR / "analysis_status.json"
ONBOARDING_PATH = SETTINGS_DIR / "Master-Etsy-Listing-Description-Writing-Onboarding.txt"
OUTPUT_JSON = OUTPUTS_DIR / "artwork_listing_master.json"

# -----------------------------------------------------------------------------
# 5. FILE/FILENAME TEMPLATES
# -----------------------------------------------------------------------------
FILENAME_TEMPLATES = {
    "artwork": "{seo_slug}.jpg",
    "mockup": "{seo_slug}-MU-{num:02d}.jpg",
    "thumbnail": "{seo_slug}-THUMB.jpg",
    "analyse": "{seo_slug}-ANALYSE.jpg",
    "listing_json": "{seo_slug}-listing.json",
    "qc_json": "{seo_slug}.qc.json",
}

# -----------------------------------------------------------------------------
# 6. FILE TYPES, LIMITS, IMAGE SIZES
# -----------------------------------------------------------------------------
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png").split(","))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
ANALYSE_MAX_DIM = int(os.getenv("ANALYSE_MAX_DIM", "2400"))
ANALYSE_MAX_MB = int(os.getenv("ANALYSE_MAX_MB", "5"))
THUMB_WIDTH = int(os.getenv("THUMB_WIDTH", "400"))
THUMB_HEIGHT = int(os.getenv("THUMB_HEIGHT", "400"))

# -----------------------------------------------------------------------------
# 7. MOCKUP CATEGORIES (DYNAMIC)
# -----------------------------------------------------------------------------
def get_mockup_categories() -> list[str]:
    override = os.getenv("MOCKUP_CATEGORIES")
    if override:
        return [c.strip() for c in override.split(",") if c.strip()]
    d = MOCKUPS_INPUT_DIR
    if d.exists():
        return sorted(
            [
                f.name
                for f in d.iterdir()
                if f.is_dir() and f.name.lower() != "uncategorised"
            ]
        )
    return []

MOCKUP_CATEGORIES = get_mockup_categories()

# -----------------------------------------------------------------------------
# 8. FOLDER AUTO-CREATION (STRICT)
# -----------------------------------------------------------------------------
_CRITICAL_FOLDERS = [
    ART_PROCESSING_DIR,
    UNANALYSED_ROOT,
    PROCESSED_ROOT,
    FINALISED_ROOT,
    ARTWORK_VAULT_ROOT,
    OUTPUTS_DIR,
    COMPOSITES_DIR,
    SELECTIONS_DIR,
    SELLBRITE_DIR,
    SIGNED_DIR,
    MOCKUPS_INPUT_DIR,
    SIGNATURES_DIR,
    GENERIC_TEXTS_DIR,
    COORDS_DIR,
    SCRIPTS_DIR,
    SETTINGS_DIR,
    LOGS_DIR,
    CODEX_LOGS_DIR,
    DATA_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
]
for folder in _CRITICAL_FOLDERS:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"Could not create required folder {folder}: {exc}")

# -----------------------------------------------------------------------------
# 9. SCRIPTS (For automation & CLI)
# -----------------------------------------------------------------------------
ANALYZE_SCRIPT_PATH = SCRIPTS_DIR / "analyze_artwork.py"
GENERATE_SCRIPT_PATH = SCRIPTS_DIR / "generate_composites.py"

# -----------------------------------------------------------------------------
# 10. AUDIT/MARKDOWN/QA
# -----------------------------------------------------------------------------
QA_AUDIT_INDEX = BASE_DIR / "QA_AUDIT_INDEX.md"
SITEMAP_FILE = BASE_DIR / "SITEMAP.md"
CHANGELOG_FILE = BASE_DIR / "CHANGELOG.md"

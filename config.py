# config.py — ArtNarrator & DreamArtMachine (Robbie Mode™, July 2025)
# Central config: All core folders, env vars, limits, AI models, templates.
# All code must import config.py and reference only these values!

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Load .env file from project root ---
load_dotenv()

# === PROJECT ROOT ===
BASE_DIR = Path(__file__).resolve().parent

# =============================================================================
# 1. ENV/BRANDING/ADMIN
# =============================================================================
# --- [ 1.1: Branding ] ---
BRAND_NAME = os.getenv("BRAND_NAME", "Art Narrator")
BRAND_TAGLINE = os.getenv("BRAND_TAGLINE", "Create. Automate. Sell Art.")
BRAND_AUTHOR = os.getenv("BRAND_AUTHOR", "Robin Custance")
BRAND_DOMAIN = os.getenv("BRAND_DOMAIN", "artnarrator.com")
ETSY_SHOP_URL = os.getenv("ETSY_SHOP_URL", "https://www.robincustance.etsy.com")

# --- [ 1.2: Server & Flask ] ---
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "robincustance@gmail.com")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "robbie")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "kangaroo123")
SERVER_PORT = int(os.getenv("SERVER_PORT", "7777"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
HOST = os.getenv("HOST", "127.0.0.1")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "supersecret-key-1234")
PORT = int(os.getenv("PORT", "7777"))


# =============================================================================
# 2. AI/PLATFORM/API MODELS
# =============================================================================

# --- [ 2.1: OpenAI ] ---
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Main model for both text and vision tasks (gpt-4o is multimodal)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_MODEL_FALLBACK = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4-turbo")

# Models specifically for image GENERATION
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
OPENAI_IMAGE_MODEL_FALLBACK = os.getenv("OPENAI_IMAGE_MODEL_FALLBACK", "dall-e-2")

# --- [ 2.2: Google Cloud ] ---
# API Key for authenticating with Google Cloud services
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 

# The single, multimodal model for text and vision tasks
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro-latest")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")

# --- [ 2.3: Other Integrations ] ---
RCLONE_REMOTE_NAME = os.getenv("RCLONE_REMOTE_NAME", "gdrive")
RCLONE_REMOTE_PATH = os.getenv("RCLONE_REMOTE_PATH", "art-backups")
SELLBRITE_ACCOUNT_TOKEN = os.getenv("SELLBRITE_ACCOUNT_TOKEN")
SELLBRITE_SECRET_KEY = os.getenv("SELLBRITE_SECRET_KEY")
SELLBRITE_API_BASE_URL = os.getenv("SELLBRITE_API_BASE_URL", "https://api.sellbrite.com/v1")

# --- [ 2.4: SMTP Configuration ] ---
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# =============================================================================
# 3. FOLDER STRUCTURE & CORE PATHS
# =============================================================================

# --- [ 3.1: Core Directories ] ---
SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", BASE_DIR / "scripts"))
SETTINGS_DIR = Path(os.getenv("SETTINGS_DIR", BASE_DIR / "settings"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", BASE_DIR / "logs"))
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
STATIC_DIR = Path(os.getenv("STATIC_DIR", BASE_DIR / "static"))
TEMPLATES_DIR = Path(os.getenv("TEMPLATES_DIR", BASE_DIR / "templates"))

# --- [ 3.2: Art Processing Workflow Directories ] ---
ART_PROCESSING_DIR = Path(os.getenv("ART_PROCESSING_DIR", BASE_DIR / "art-processing"))
UNANALYSED_ROOT = ART_PROCESSING_DIR / "unanalysed-artwork"
PROCESSED_ROOT = ART_PROCESSING_DIR / "processed-artwork"
FINALISED_ROOT = ART_PROCESSING_DIR / "finalised-artwork"
ARTWORK_VAULT_ROOT = ART_PROCESSING_DIR / "artwork-vault"

# ✅ NEW: TEST FOLDERS for Pytest fixtures
UNANALYSED_TEST_DIR = UNANALYSED_ROOT / "tests"
PROCESSED_TEST_DIR = PROCESSED_ROOT / "tests"

# --- [ 3.3: Input Asset Directories ] ---
MOCKUPS_INPUT_DIR = Path(os.getenv("MOCKUPS_INPUT_DIR", BASE_DIR / "inputs" / "mockups"))
MOCKUPS_STAGING_DIR = MOCKUPS_INPUT_DIR / "uncategorised"
MOCKUPS_CATEGORISED_DIR = MOCKUPS_INPUT_DIR / "categorised"
MOCKUP_THUMBNAIL_DIR = MOCKUPS_INPUT_DIR / ".thumbnails"
SIGNATURES_DIR = Path(os.getenv("SIGNATURES_DIR", BASE_DIR / "inputs" / "signatures"))
GENERIC_TEXTS_DIR = Path(os.getenv("GENERIC_TEXTS_DIR", BASE_DIR / "generic_texts"))
COORDS_DIR = Path(os.getenv("COORDS_DIR", BASE_DIR / "inputs" / "Coordinates"))
GDWS_CONTENT_DIR = DATA_DIR / "gdws_content"

# --- [ 3.4: Output Directories ] ---
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", BASE_DIR / "outputs"))
COMPOSITES_DIR = OUTPUTS_DIR / "composites"
SELECTIONS_DIR = OUTPUTS_DIR / "selections"
SELLBRITE_DIR = OUTPUTS_DIR / "sellbrite"
SIGNED_DIR = OUTPUTS_DIR / "signed"
CODEX_LOGS_DIR = Path(os.getenv("CODEX_LOGS_DIR", BASE_DIR / "CODEX-LOGS"))

# Aliases
MOCKUPS_ROOT = MOCKUPS_INPUT_DIR
CATEGORISED_MOCKUPS_ROOT = MOCKUPS_CATEGORISED_DIR
COMPOSITES_ROOT = COMPOSITES_DIR
THUMB_SUBDIR = "THUMBS"
THUMBS_ROOT = FINALISED_ROOT / THUMB_SUBDIR

# =============================================================================
# 4. HELPER & REGISTRY FILES
# =============================================================================
DB_PATH = DATA_DIR / "artnarrator.sqlite3"
SKU_TRACKER = SETTINGS_DIR / "sku_tracker.json"
ANALYSIS_STATUS_FILE = LOGS_DIR / "analysis_status.json"
SESSION_REGISTRY_FILE = LOGS_DIR / "session_registry.json"
ONBOARDING_PATH = SETTINGS_DIR / "Master-Etsy-Listing-Description-Writing-Onboarding.txt"
MOCKUP_CATEGORISER_PROMPT_PATH = SETTINGS_DIR / "mockup_categoriser_prompt.txt"
OUTPUT_JSON = ART_PROCESSING_DIR / "master-artwork-paths.json"
MOCKUP_CATEGORISATION_LOG = LOGS_DIR / "mockup_categorisation.log"
PENDING_MOCKUPS_QUEUE_FILE = PROCESSED_ROOT / "pending_mockups.json"


# =============================================================================
# 5. FILENAME TEMPLATES
# =============================================================================
FILENAME_TEMPLATES = {
    "artwork": "{seo_slug}.jpg",
    "mockup": "{seo_slug}-MU-{num:02d}.jpg",
    "thumbnail": "{seo_slug}-THUMB.jpg",
    "analyse": "{seo_slug}-ANALYSE.jpg",
    "listing_json": "{seo_slug}-listing.json",
    "qc_json": "{seo_slug}.qc.json",
}

# =============================================================================
# 6. FILE TYPES, LIMITS, & IMAGE SIZES
# =============================================================================
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png").split(","))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
ANALYSE_MAX_DIM = int(os.getenv("ANALYSE_MAX_DIM", "2400"))
ANALYSE_MAX_MB = int(os.getenv("ANALYSE_MAX_MB", "5"))
THUMB_WIDTH = int(os.getenv("THUMB_WIDTH", "400"))
THUMB_HEIGHT = int(os.getenv("THUMB_HEIGHT", "400"))

# =============================================================================
# 7. APPLICATION CONSTANTS
# =============================================================================
# --- [ 7.1: Artwork & Mockup Defaults ] ---
MOCKUPS_PER_LISTING = 9
DEFAULT_MOCKUP_IMAGE = STATIC_DIR / "img" / "default-mockup.jpg"

# --- ADDED FOR THE SIGNING SCRIPT ---
ARTWORKS_INPUT_DIR = UNANALYSED_ROOT  # Pointing to the unanalysed artwork folder
SIGNATURE_SIZE_PERCENTAGE = 0.10     # Signature will be 10% of the image's long edge
SIGNATURE_MARGIN_PERCENTAGE = 0.05   # 5% margin from the edges
SIGNED_OUTPUT_DIR = SIGNED_DIR       # Alias for the script to find the correct folder

ETSY_COLOURS = {
    'Beige': (222, 202, 173), 'Black': (24, 23, 22), 'Blue': (42, 80, 166),
    'Bronze': (140, 120, 83), 'Brown': (110, 72, 42), 'Clear': (240, 240, 240),
    'Copper': (181, 101, 29), 'Gold': (236, 180, 63), 'Grey': (160, 160, 160),
    'Green': (67, 127, 66), 'Orange': (237, 129, 40), 'Pink': (229, 100, 156),
    'Purple': (113, 74, 151), 'Rainbow': (170, 92, 152), 'Red': (181, 32, 42),
    'Rose gold': (212, 150, 146), 'Silver': (170, 174, 179),
    'White': (242, 242, 243), 'Yellow': (242, 207, 46)
}

# --- [ 7.2: Security & Session Management ] ---
MAX_SESSIONS = 5
SESSION_TIMEOUT_SECONDS = 7200  # 2 hours

# --- [ 7.3: SKU Configuration ] ---
SKU_CONFIG = {
    "PREFIX": "RJC-",
    "DIGITS": 4
}

# --- [ 7.4: Sellbrite Export Defaults ] ---
SELLBRITE_DEFAULTS = {
    "QUANTITY": 25,
    "CONDITION": "New",
    "CATEGORY": "Art & Collectibles > Prints > Digital Prints",
    "WEIGHT": 0
}

# --- [ 7.5: Guided Description Writing System (GDWS) Config ] ---
GDWS_CONFIG = {
    "PARAGRAPH_HEADINGS": [
        "About the Artist – Robin Custance", "Did You Know? Aboriginal Art & the Spirit of Dot Painting",
        "What You’ll Receive", "Ideal Uses for the", "Printing Tips",
        "Top 10 Print-On-Demand Services for Wall Art & Art Prints", "Important Notes",
        "Frequently Asked Questions", "LET’S CREATE SOMETHING BEAUTIFUL TOGETHER",
        "THANK YOU – FROM MY STUDIO TO YOUR HOME", "EXPLORE MY WORK", "WHY YOU’LL LOVE THIS ARTWORK",
        "HOW TO BUY & PRINT", "Thank You & Stay Connected"
    ],
    "PINNED_START_TITLES": [
        "About the Artist – Robin Custance",
        "Did You Know? Aboriginal Art & the Spirit of Dot Painting",
        "What You’ll Receive",
        "WHY YOU’LL LOVE THIS ARTWORK",
        "HOW TO BUY & PRINT",
    ],
    "PINNED_END_TITLES": [
        "THANK YOU – FROM MY STUDIO TO YOUR HOME",
        "Thank You & Stay Connected",
    ]
}


# =============================================================================
# 8. DYNAMIC CATEGORIES (from filesystem)
# =============================================================================
def get_mockup_categories() -> list[str]:
    override = os.getenv("MOCKUP_CATEGORIES")
    if override:
        return [c.strip() for c in override.split(",") if c.strip()]
    d = MOCKUPS_CATEGORISED_DIR
    if d.exists():
        return sorted([f.name for f in d.iterdir() if f.is_dir()])
    return []

MOCKUP_CATEGORIES = get_mockup_categories()


def resolve_image_url(path: Path) -> str:
    """Convert filesystem path to a proper public URL."""
    relative_path = path.relative_to(BASE_DIR).as_posix()
    return f"{BASE_URL}/{relative_path}"

# =============================================================================
# 9. FOLDER AUTO-CREATION
# =============================================================================
_CRITICAL_FOLDERS = [
    ART_PROCESSING_DIR, UNANALYSED_ROOT, PROCESSED_ROOT, FINALISED_ROOT,
    ARTWORK_VAULT_ROOT, OUTPUTS_DIR, COMPOSITES_DIR, SELECTIONS_DIR,
    SELLBRITE_DIR, SIGNED_DIR, MOCKUPS_INPUT_DIR, MOCKUPS_STAGING_DIR,
    MOCKUPS_CATEGORISED_DIR, MOCKUP_THUMBNAIL_DIR, SIGNATURES_DIR,
    GENERIC_TEXTS_DIR, COORDS_DIR, SCRIPTS_DIR, SETTINGS_DIR, LOGS_DIR,
    CODEX_LOGS_DIR, DATA_DIR, STATIC_DIR, TEMPLATES_DIR, GDWS_CONTENT_DIR,
]
for folder in _CRITICAL_FOLDERS:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"Could not create required folder {folder}: {exc}") from exc

# =============================================================================
# 10. SCRIPT PATHS (for automation & CLI)
# =============================================================================
ANALYZE_SCRIPT_PATH = SCRIPTS_DIR / "analyze_artwork.py"
GENERATE_SCRIPT_PATH = SCRIPTS_DIR / "generate_composites.py"
MOCKUP_CATEGORISER_SCRIPT_PATH = SCRIPTS_DIR / "mockup_categoriser.py"
COORDINATE_GENERATOR_SCRIPT_PATH = SCRIPTS_DIR / "generate_coordinates.py"
COORDINATE_GENERATOR_RATIO_SCRIPT_PATH = SCRIPTS_DIR / "generate_coordinates_for_ratio.py"

# =============================================================================
# 11. URLS & ROUTE PREFIXES
# =============================================================================
# --- [ 11.1: Base URL for Serving Content ] ---
BASE_URL = f"https://{BRAND_DOMAIN}" if ENVIRONMENT == "prod" else f"http://{HOST}:{PORT}"

# --- [ 11.2: URL Paths for Serving Static-like Content via Flask ] ---
STATIC_URL_PREFIX = "static"
PROCESSED_URL_PATH = f"{STATIC_URL_PREFIX}/{PROCESSED_ROOT.relative_to(BASE_DIR).as_posix()}"
FINALISED_URL_PATH = f"{STATIC_URL_PREFIX}/{FINALISED_ROOT.relative_to(BASE_DIR).as_posix()}"
LOCKED_URL_PATH = f"{STATIC_URL_PREFIX}/{ARTWORK_VAULT_ROOT.relative_to(BASE_DIR).as_posix()}"

# --- [ 11.3: Prefixes for Other Dynamic Image Routes ] ---
UNANALYSED_IMG_URL_PREFIX = "unanalysed-img"
MOCKUP_THUMB_URL_PREFIX = "thumbs"
COMPOSITE_IMG_URL_PREFIX = "composite-img"

# =============================================================================
# 12. AUDIT & MARKDOWN FILES
# =============================================================================
QA_AUDIT_INDEX = BASE_DIR / "QA_AUDIT_INDEX.md"
SITEMAP_FILE = BASE_DIR / "SITEMAP.md"
CHANGELOG_FILE = BASE_DIR / "CHANGELOG.md"

# =============================================================================
# 14. LOGGING SETUP
# =============================================================================
# --- [ 13.1: Log File Timestamp Format ] ---
LOG_TIMESTAMP_FORMAT = "%a-%d-%b-%Y-%I-%M-%p"

# --- [ 13.2: Log File Configurations ] ---
LOG_CONFIG = {
    # Core App Lifecycle
    "APP_STARTUP": "app-lifecycle-logs",
    "DATABASE": "database-logs",
    "SECURITY": "security-logs",
    "GUNICORN": "gunicorn",
    # Artwork Workflow Actions
    "UPLOAD": "upload",
    "DELETE": "delete",
    "EDITS": "edits",
    "FINALISE": "finalise",
    "LOCK": "lock",
    # Script & Subprocess Actions
    "ANALYZE_OPENAI": "analyse-openai",
    "ANALYZE_GOOGLE": "analyse-google",
    "COMPOSITE_GEN": "composite-generation-logs",
    # API Integrations
    "SELLBRITE_API": "sellbrite-api-logs",
    # Default/Catch-all
    "DEFAULT": "general-logs",
}
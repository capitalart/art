"""Central configuration for the ART Narrator project.

This module defines all folder paths, filename templates, allowed
extensions, image sizes and other parameters used across the codebase.
Values can be overridden using environment variables of the same name.

Update paths here rather than hard-coding them elsewhere. All modules
should import settings from ``config`` so behaviour automatically adapts
when directory names or limits change. Every value can be overridden by an
environment variable of the same name which allows for per-user or
deployment specific customisation via ``.env`` files.

Critical folders are created on import. If creation fails an explicit
``RuntimeError`` is raised. Edit this file or set env vars to tweak folder
names, extensions or limits rather than updating code elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Project Root -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CONFIG_VERSION = "1.2.0"

# --- Input/Output Folders ---------------------------------------------------
ARTWORKS_INPUT_DIR = Path(
    os.getenv("ARTWORKS_INPUT_DIR", BASE_DIR / "inputs" / "artworks")
)
MOCKUPS_INPUT_DIR = Path(
    os.getenv("MOCKUPS_INPUT_DIR", BASE_DIR / "inputs" / "mockups")
)
MOCKUPS_CATEGORISED_DIR = Path(
    os.getenv("MOCKUPS_CATEGORISED_DIR", MOCKUPS_INPUT_DIR / "4x5-categorised")
)
ARTWORKS_PROCESSED_DIR = Path(
    os.getenv("ARTWORKS_PROCESSED_DIR", BASE_DIR / "outputs" / "processed")
)
ARTWORKS_FINALISED_DIR = Path(
    os.getenv("ARTWORKS_FINALISED_DIR", BASE_DIR / "outputs" / "finalised-artwork")
)
COMPOSITES_DIR = Path(os.getenv("COMPOSITES_DIR", BASE_DIR / "outputs" / "composites"))
SELECTIONS_DIR = Path(os.getenv("SELECTIONS_DIR", BASE_DIR / "outputs" / "selections"))
THUMBNAILS_DIR = Path(os.getenv("THUMBNAILS_DIR", BASE_DIR / "outputs" / "thumbnails"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", BASE_DIR / "logs"))
DEV_LOGS_DIR = Path(os.getenv("DEV_LOGS_DIR", BASE_DIR / "dev-logs"))
PARSE_FAILURE_DIR = Path(os.getenv("PARSE_FAILURE_DIR", LOGS_DIR / "parse_failures"))
OPENAI_PROMPT_LOG_DIR = Path(
    os.getenv("OPENAI_PROMPT_LOG_DIR", LOGS_DIR / "openai_prompts")
)
OPENAI_RESPONSE_LOG_DIR = Path(
    os.getenv("OPENAI_RESPONSE_LOG_DIR", LOGS_DIR / "openai_responses")
)
GIT_LOG_DIR = Path(os.getenv("GIT_LOG_DIR", BASE_DIR / "git-update-push-logs"))
SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", BASE_DIR / "scripts"))
SIGNATURES_DIR = Path(os.getenv("SIGNATURES_DIR", BASE_DIR / "inputs" / "signatures"))
GENERIC_TEXTS_DIR = Path(os.getenv("GENERIC_TEXTS_DIR", BASE_DIR / "generic_texts"))
UPLOADS_TEMP_DIR = Path(os.getenv("UPLOADS_TEMP_DIR", BASE_DIR / "uploads_temp"))
COORDS_DIR = Path(os.getenv("COORDS_DIR", BASE_DIR / "inputs" / "Coordinates"))
TMP_DIR = Path(os.getenv("TMP_DIR", BASE_DIR / "tmp" / "ai_input_images"))
SELLBRITE_OUTPUT_DIR = Path(
    os.getenv("SELLBRITE_OUTPUT_DIR", BASE_DIR / "outputs" / "sellbrite")
)
AIGW_PROMPTS_DIR = Path(
    os.getenv("AIGW_PROMPTS_DIR", BASE_DIR / "outputs" / "aigw_prompts")
)
AIGW_OPTIONS_FILE = Path(
    os.getenv("AIGW_OPTIONS_FILE", BASE_DIR / "settings" / "aigw_options.json")
)
SELLBRITE_TEMPLATE_CSV = Path(
    os.getenv("SELLBRITE_TEMPLATE_CSV", BASE_DIR / "docs" / "csv_product_template.csv")
)
SELLBRITE_DEFAULT_QUANTITY = int(os.getenv("SELLBRITE_DEFAULT_QUANTITY", "1"))

# Additional general file locations
ONBOARDING_PATH = Path(
    os.getenv(
        "ONBOARDING_PATH",
        BASE_DIR
        / "settings"
        / "Master-Etsy-Listing-Description-Writing-Onboarding.txt",
    )
)
OUTPUT_JSON = Path(
    os.getenv("OUTPUT_JSON", BASE_DIR / "outputs" / "artwork_listing_master.json")
)
OUTPUT_PROCESSED_ROOT = ARTWORKS_PROCESSED_DIR

# Paths to helper scripts used by various workflows
ANALYZE_SCRIPT_PATH = Path(
    os.getenv("ANALYZE_SCRIPT_PATH", SCRIPTS_DIR / "analyze_artwork.py")
)
GENERATE_SCRIPT_PATH = Path(
    os.getenv("GENERATE_SCRIPT_PATH", SCRIPTS_DIR / "generate_composites.py")
)

# --- Filename Templates -----------------------------------------------------
FILENAME_TEMPLATES = {
    "artwork": "{seo_slug}.jpg",
    "mockup": "{seo_slug}-MU-{num:02d}.jpg",
    "thumbnail": "{seo_slug}-THUMB.jpg",
    "analyse": "{seo_slug}-ANALYSE.jpg",
    "listing_json": "{seo_slug}-listing.json",
    "qc_json": "{seo_slug}.qc.json",
}

# --- Allowed Extensions & Sizes --------------------------------------------
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png").split(","))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "32"))
ANALYSE_MAX_DIM = int(os.getenv("ANALYSE_MAX_DIM", "2400"))
ANALYSE_MAX_MB = int(os.getenv("ANALYSE_MAX_MB", "1"))

# --- Image Dimensions -------------------------------------------------------
THUMB_WIDTH = int(os.getenv("THUMB_WIDTH", "400"))
THUMB_HEIGHT = int(os.getenv("THUMB_HEIGHT", "400"))


# --- Mockup Categories ------------------------------------------------------
def get_mockup_categories() -> list[str]:
    override = os.getenv("MOCKUP_CATEGORIES")
    if override:
        return [c.strip() for c in override.split(",") if c.strip()]
    if MOCKUPS_CATEGORISED_DIR.exists():
        return sorted(
            [
                f.name
                for f in MOCKUPS_CATEGORISED_DIR.iterdir()
                if f.is_dir() and f.name.lower() != "uncategorised"
            ]
        )
    return []


MOCKUP_CATEGORIES = get_mockup_categories()

# --- Signature Settings -----------------------------------------------------
SIGNATURE_SIZE_PERCENTAGE = float(os.getenv("SIGNATURE_SIZE_PERCENTAGE", "0.05"))
SIGNATURE_MARGIN_PERCENTAGE = float(os.getenv("SIGNATURE_MARGIN_PERCENTAGE", "0.03"))

# --- SKU Tracking -----------------------------------------------------------
SKU_TRACKER = Path(
    os.getenv("SKU_TRACKER_PATH", BASE_DIR / "settings" / "sku_tracker.json")
)

# File used by the web UI to report progress of analysis jobs
ANALYSIS_STATUS_FILE = Path(
    os.getenv("ANALYSIS_STATUS_FILE", LOGS_DIR / "analysis_status.json")
)

# Feature flags --------------------------------------------------------------
# Toggle visibility of Upgrade/Subscription links in the UI. Set the
# environment variable ``ENABLE_UPGRADE`` to ``true`` to enable.
ENABLE_UPGRADE = os.getenv("ENABLE_UPGRADE", "false").lower() == "true"

# --- API Keys ---------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- AI Model Configuration -------------------------------------------------
OPENAI_PRIMARY_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-4o")
OPENAI_FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4-turbo")
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-1.5-pro")


def get_openai_model() -> str:
    """Return the best available model with fallback."""
    primary = OPENAI_PRIMARY_MODEL
    fallback = OPENAI_FALLBACK_MODEL
    return primary if primary else fallback

# --- Additional Script Paths and Outputs -----------------------------------
PATCHES_DIR = Path(os.getenv("PATCHES_DIR", BASE_DIR / "patches"))
PATCH_INPUT = Path(os.getenv("PATCH_INPUT", BASE_DIR / "copy-git-apply.txt"))
# Output location for signed artworks generated by utilities
SIGNED_OUTPUT_DIR = Path(
    os.getenv("SIGNED_OUTPUT_DIR", BASE_DIR / "outputs" / "signed")
)
# Log file for the mockup categoriser script
MOCKUP_CATEGORISATION_LOG = Path(
    os.getenv("MOCKUP_CATEGORISATION_LOG", BASE_DIR / "mockup_categorisation_log.txt")
)

# Midjourney sorting helper defaults
MIDJOURNEY_CSV_PATH = Path(
    os.getenv("MIDJOURNEY_CSV_PATH", BASE_DIR / "inputs" / "autojourney.csv")
)
MIDJOURNEY_INPUT_DIR = Path(
    os.getenv("MIDJOURNEY_INPUT_DIR", BASE_DIR / "inputs" / "midjourney")
)
MIDJOURNEY_OUTPUT_DIR = Path(
    os.getenv("MIDJOURNEY_OUTPUT_DIR", BASE_DIR / "outputs" / "midjourney_sorted")
)
MIDJOURNEY_METADATA_CSV = Path(
    os.getenv(
        "MIDJOURNEY_METADATA_CSV",
        MIDJOURNEY_OUTPUT_DIR / "art_narrator_image_metadata.csv",
    )
)

# --- Ensure Critical Folders Exist -----------------------------------------
for folder in [
    ARTWORKS_INPUT_DIR,
    MOCKUPS_INPUT_DIR,
    ARTWORKS_PROCESSED_DIR,
    LOGS_DIR,
    DEV_LOGS_DIR,
    PARSE_FAILURE_DIR,
    OPENAI_PROMPT_LOG_DIR,
    OPENAI_RESPONSE_LOG_DIR,
    GIT_LOG_DIR,
    PATCHES_DIR,
    SIGNED_OUTPUT_DIR,
    SELLBRITE_OUTPUT_DIR,
    UPLOADS_TEMP_DIR,
    AIGW_PROMPTS_DIR,
]:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - simple safety
        raise RuntimeError(f"Could not create required folder {folder}: {exc}")

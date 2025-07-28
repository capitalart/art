# scripts/populate_gdws.py
"""
One-time script to parse the original generic text files and populate the
GDWS (Guided Description Writing System) content directory with a structured
set of JSON files.

INDEX
-----
1.  Imports
2.  Configuration & Logging
3.  Helper Functions
4.  Main Execution Logic
5.  Command-Line Interface (CLI)
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import json
import logging
import re
import sys
from pathlib import Path

# Local application imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utils.logger_utils import setup_logger

# ===========================================================================
# 2. Configuration & Logging
# ===========================================================================
logger = setup_logger(__name__, "DEFAULT")

# Get GDWS configuration from the central config file
SOURCE_TEXT_DIR = config.GENERIC_TEXTS_DIR
GDWS_CONTENT_DIR = config.GDWS_CONTENT_DIR
PARAGRAPH_HEADINGS = config.GDWS_CONFIG["PARAGRAPH_HEADINGS"]


# ===========================================================================
# 3. Helper Functions
# ===========================================================================

def slugify(text: str) -> str:
    """
    Creates a filesystem-safe name from a heading.
    Note: This version is specific to GDWS and contains hardcoded remappings.
    """
    s = text.lower()
    s = re.sub(r'[^\w\s-]', '', s).strip()
    s = re.sub(r'[-\s]+', '_', s)
    # Handle specific long names for cleaner folder names
    if "about_the_artist" in s: return "about_the_artist"
    if "did_you_know" in s: return "about_art_style"
    if "what_youll_receive" in s: return "file_details"
    return s


# ===========================================================================
# 4. Main Execution Logic
# ===========================================================================

def parse_and_create_files():
    """Reads source text files, parses them, and creates the GDWS structure."""
    if not SOURCE_TEXT_DIR.exists():
        logger.critical(f"Source directory not found at '{SOURCE_TEXT_DIR}'. Aborting.")
        print(f"❌ Error: Source directory not found at '{SOURCE_TEXT_DIR}'")
        return

    logger.info(f"Starting GDWS population from '{SOURCE_TEXT_DIR}'...")
    print(f"🚀 Starting GDWS population from '{SOURCE_TEXT_DIR}'...")
    
    GDWS_CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    source_files = list(SOURCE_TEXT_DIR.glob("*.txt"))
    if not source_files:
        logger.warning("No .txt files found in the source directory. Nothing to do.")
        print("🤷 No .txt files found in the source directory. Nothing to do.")
        return

    # Create a regex pattern to split the file content by the configured headings
    split_pattern = re.compile('(' + '|'.join(re.escape(h) for h in PARAGRAPH_HEADINGS) + ')')

    for txt_file in source_files:
        aspect_ratio = txt_file.stem
        # Handle known typo in an old filename
        if aspect_ratio.lower() == "a-series-verical":
            aspect_ratio = "A-Series-Vertical"

        aspect_dir = GDWS_CONTENT_DIR / aspect_ratio
        aspect_dir.mkdir(exist_ok=True)
        
        logger.info(f"Processing: {txt_file.name} for aspect ratio '{aspect_ratio}'...")
        print(f"\nProcessing: {txt_file.name} for aspect ratio '{aspect_ratio}'...")
        
        content = txt_file.read_text(encoding='utf-8').strip()
        parts = split_pattern.split(content)
        
        i = 1 # Start at 1 because the first element is the text before the first heading
        while i < len(parts):
            title = parts[i].strip()
            body = parts[i+1].strip() if (i+1) < len(parts) else ""
            
            folder_name = slugify(title)
            paragraph_dir = aspect_dir / folder_name
            paragraph_dir.mkdir(exist_ok=True)
            
            base_file = paragraph_dir / "base.json"
            
            data_to_save = {
                "id": "base",
                "title": title,
                "content": body,
                "instructions": (
                    f"This is the base text for the '{title}' section for the {aspect_ratio} "
                    "aspect ratio. Edit the text to refine the message for this paragraph."
                )
            }
            
            base_file.write_text(json.dumps(data_to_save, indent=4), encoding='utf-8')
            logger.info(f"  - Created base file for '{title}' in {folder_name}")
            print(f"  ✅ Created base file for '{title}'")
            i += 2

    logger.info("GDWS population script finished.")
    print(f"\n🎉 GDWS population complete! Check the '{GDWS_CONTENT_DIR}' directory.")


# ===========================================================================
# 5. Command-Line Interface (CLI)
# ===========================================================================

if __name__ == "__main__":
    parse_and_create_files()
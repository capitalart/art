# ============================== [ mockup_categoriser.py ] ==============================
# Bulk and single-file AI-based mockup categorisation script for ArtNarrator.
# --------------------------------------------------------------------------------------
# Can be run in batch mode (processes all files in staging) or single-file mode.
# Uses config variables for all paths.
# ======================================================================================

import os
import shutil
import time
import base64
import argparse
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import sys

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    OPENAI_API_KEY,
    MOCKUPS_STAGING_DIR,
    MOCKUPS_CATEGORISED_DIR,
    MOCKUP_CATEGORISATION_LOG,
)

# ============================== [ 1. CONFIG & CONSTANTS ] ==============================

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-4o")
client = OpenAI(api_key=OPENAI_API_KEY)

# We will focus on the 4x5 aspect ratio as planned
STAGING_FOLDER = MOCKUPS_STAGING_DIR / "4x5"
CATEGORISED_FOLDER = MOCKUPS_CATEGORISED_DIR / "4x5-categorised"
LOG_FILE = str(MOCKUP_CATEGORISATION_LOG)

# ============================== [ 2. HELPER FUNCTIONS ] ==============================

def detect_valid_categories():
    """Dynamically detect valid category folders."""
    if not CATEGORISED_FOLDER.exists():
        return []
    return [d.name for d in CATEGORISED_FOLDER.iterdir() if d.is_dir()]

def log_result(filename: str, category: str):
    """Appends a result to the log file."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {filename} -> {category}\n")

def move_file_to_category(file_path: Path, category: str):
    """Moves a file to the correct category subfolder."""
    dest_folder = CATEGORISED_FOLDER / category
    dest_folder.mkdir(exist_ok=True)
    shutil.move(str(file_path), dest_folder / file_path.name)

def is_image(filename: str) -> bool:
    """Checks if a filename has a common image extension."""
    return filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))

def encode_image_to_base64(file_path: str) -> str:
    """Encodes an image file to a base64 string for API submission."""
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# ============================== [ 3. OPENAI ANALYSIS ] ==============================

def analyse_mockup(file_path: str, valid_categories: list) -> str:
    """Uses OpenAI Vision to classify a mockup image into a category."""
    try:
        encoded_image = encode_image_to_base64(file_path)
        system_prompt = (
            "You are an expert AI assistant helping a professional digital artist organise mockup preview images. "
            "You will receive one image at a time, and your job is to classify it into one of the following categories:\n\n"
            f"{', '.join(valid_categories)}\n\n"
            "These images depict digital artworks displayed in styled rooms. Only respond with the *exact* category name. "
            "If unsure, choose the closest appropriate category based on furniture, lighting, layout or wall style. "
            "No explanations, just return the category string."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}]}
        ]
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=20,
            temperature=0
        )
        category = response.choices[0].message.content.strip()
        if category not in valid_categories:
            raise ValueError(f"Returned category '{category}' is not in the list of valid categories.")
        return category
    except Exception as e:
        print(f"[ERROR] {os.path.basename(file_path)}: {e}", file=sys.stderr)
        return "Uncategorised"

# ============================== [ 4. MAIN EXECUTION ] ==============================

def main():
    """Main function to parse arguments and run the categorisation."""
    parser = argparse.ArgumentParser(description="Categorize mockups using AI.")
    parser.add_argument("--file", type=str, help="Path to a single mockup file to process.")
    parser.add_argument("--no-move", action="store_true", help="Analyze and suggest a category but do not move the file.")
    args = parser.parse_args()

    print("🔍 Starting mockup categorisation...")
    STAGING_FOLDER.mkdir(parents=True, exist_ok=True)
    CATEGORISED_FOLDER.mkdir(parents=True, exist_ok=True)

    valid_categories = detect_valid_categories()
    if not valid_categories:
        print(f"⚠️ No valid category folders found in {CATEGORISED_FOLDER}. Please create them first in the Mockup Admin dashboard.")
        return

    # Determine whether to run in single-file or batch mode
    if args.file:
        images_to_process = [Path(args.file)]
        print(f"Single file mode: Processing {args.file}")
    else:
        images_to_process = [STAGING_FOLDER / f for f in os.listdir(STAGING_FOLDER) if is_image(f)]
        print(f"Batch mode: Processing {len(images_to_process)} images from {STAGING_FOLDER}")

    for image_path in images_to_process:
        if not image_path.exists():
            print(f"⚠️ File not found, skipping: {image_path}", file=sys.stderr)
            continue
            
        print(f"→ Analysing {image_path.name}...")
        category = analyse_mockup(str(image_path), valid_categories)
        
        if not args.no_move:
            move_file_to_category(image_path, category)
            log_result(image_path.name, category)
        
        # When called for a single file, print the suggested category to stdout
        if args.file:
            print(category)

        # Be a good citizen and don't hammer the API
        time.sleep(1.5)

    print("✅ Categorisation complete.")

# ============================== [ 5. ENTRY POINT ] ==============================

if __name__ == "__main__":
    main()
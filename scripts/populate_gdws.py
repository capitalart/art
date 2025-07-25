"""
One-time script to parse the generic text files and populate the GDWS content directory.
"""
import os
import re
import json
from pathlib import Path

# --- Configuration ---
# This script assumes it's in the 'scripts' directory and the project root is one level up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Reads from your existing 'generic_texts' directory
SOURCE_TEXT_DIR = PROJECT_ROOT / "generic_texts"
GDWS_CONTENT_DIR = PROJECT_ROOT / "data" / "gdws_content"

# Define the paragraph headings to look for in the text files
PARAGRAPH_HEADINGS = [
    "About the Artist – Robin Custance", "Did You Know? Aboriginal Art & the Spirit of Dot Painting",
    "What You’ll Receive", "Ideal Uses for the", "Printing Tips",
    "Top 10 Print-On-Demand Services for Wall Art & Art Prints", "Important Notes",
    "Frequently Asked Questions", "LET’S CREATE SOMETHING BEAUTIFUL TOGETHER",
    "THANK YOU – FROM MY STUDIO TO YOUR HOME", "EXPLORE MY WORK", "WHY YOU’LL LOVE THIS ARTWORK",
    "HOW TO BUY & PRINT", "Thank You & Stay Connected"
]

def slugify(text):
    """Creates a filesystem-safe name from a heading."""
    s = text.lower()
    s = re.sub(r'[^\w\s-]', '', s).strip()
    s = re.sub(r'[-\s]+', '_', s)
    # Handle specific long names
    if "about_the_artist" in s: return "about_the_artist"
    if "did_you_know" in s: return "about_art_style"
    if "what_youll_receive" in s: return "file_details"
    return s

def parse_and_create_files():
    """Reads source text files, parses them, and creates the GDWS structure."""
    if not SOURCE_TEXT_DIR.exists():
        print(f"❌ Error: Source directory not found at '{SOURCE_TEXT_DIR}'")
        return

    print(f"🚀 Starting GDWS population from '{SOURCE_TEXT_DIR}'...")
    
    GDWS_CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    source_files = list(SOURCE_TEXT_DIR.glob("*.txt"))
    if not source_files:
        print("🤷 No .txt files found in the source directory. Nothing to do.")
        return

    # Create a regex pattern to split the file content by the headings
    split_pattern = re.compile('(' + '|'.join(re.escape(h) for h in PARAGRAPH_HEADINGS) + ')')

    for txt_file in source_files:
        aspect_ratio = txt_file.stem
        # Handle potential typo in filename
        if aspect_ratio.lower() == "a-series-verical":
            aspect_ratio = "A-Series-Vertical"

        aspect_dir = GDWS_CONTENT_DIR / aspect_ratio
        aspect_dir.mkdir(exist_ok=True)
        
        print(f"\nProcessing: {txt_file.name} for aspect ratio '{aspect_ratio}'...")
        
        content = txt_file.read_text(encoding='utf-8')
        # This is the fully corrected line to remove the tags
        content = re.sub(r'\\', '', content).strip()
        
        parts = split_pattern.split(content)
        
        i = 1
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
                "instructions": f"This is the base text for the '{title}' section for the {aspect_ratio} aspect ratio. Edit the text to refine the message for this paragraph."
            }
            
            with open(base_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
                
            print(f"  ✅ Created base file for '{title}'")
            i += 2

    print(f"\n🎉 GDWS population complete! Check the '{GDWS_CONTENT_DIR}' directory.")

if __name__ == "__main__":
    parse_and_create_files()
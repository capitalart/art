# scripts/mockup_categoriser.py
"""
Categorizes a single mockup image using an AI vision model.

This script takes an image file path as input, sends it to an AI model,
and prints the suggested category name based on a predefined list.

INDEX
-----
1.  Imports
2.  Configuration & Logging
3.  Core Logic
4.  Command-Line Interface (CLI)
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import argparse
import base64
import logging
import sys
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utils.logger_utils import setup_logger

# ===========================================================================
# 2. Configuration & Logging
# ===========================================================================
load_dotenv()
logger = setup_logger(__name__, "DEFAULT")

client = OpenAI(api_key=config.OPENAI_API_KEY, project=config.OPENAI_PROJECT_ID)

# Load the system prompt from the centrally managed file
try:
    SYSTEM_PROMPT = config.MOCKUP_CATEGORISER_PROMPT_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    logger.critical(f"Critical error: Mockup categoriser prompt file not found at {config.MOCKUP_CATEGORISER_PROMPT_PATH}")
    sys.exit("Error: Prompt file not found. Please check your configuration.")


# ===========================================================================
# 3. Core Logic
# ===========================================================================

def categorise_mockup(image_path: Path) -> str:
    """
    Analyzes an image with an AI model and returns the suggested category.

    Args:
        image_path: The path to the mockup image file.

    Returns:
        The suggested category name as a string.
        
    Raises:
        Exception: If the AI call fails.
    """
    logger.info(f"Starting mockup categorization for: {image_path.name}")
    try:
        with open(image_path, "rb") as f:
            encoded_img = base64.b64encode(f.read()).decode("utf-8")

        logger.info("Sending request to OpenAI Vision API...")
        response = client.chat.completions.create(
            model=config.OPENAI_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_img}"}},
                    ],
                }
            ],
            max_tokens=50,
        )
        category = response.choices[0].message.content.strip()
        logger.info(f"AI suggested category for '{image_path.name}': '{category}'")
        return category
    except Exception as e:
        logger.error(f"Failed to categorize mockup {image_path.name}: {e}", exc_info=True)
        raise


# ===========================================================================
# 4. Command-Line Interface (CLI)
# ===========================================================================

def main():
    """Parses arguments and runs the categorization process."""
    parser = argparse.ArgumentParser(description="Suggest a category for a mockup image.")
    parser.add_argument("--file", type=Path, required=True, help="Path to the mockup image file.")
    # --no-move argument is kept for compatibility with the admin panel call, but is not used in this script.
    parser.add_argument("--no-move", action="store_true", help="Flag (unused) for compatibility.")
    args = parser.parse_args()

    try:
        suggested_category = categorise_mockup(args.file)
        # Print the result to stdout for the calling process to capture
        print(suggested_category)
    except Exception as e:
        # Print errors to stderr
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
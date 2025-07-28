# scripts/test_sellbrite_add_listing.py
"""
A command-line utility to post a test product to Sellbrite.

This script loads a sample JSON listing, authenticates with the Sellbrite API
using credentials from the config, and attempts to create a new product.
It is intended for verifying that the API integration is functional.

INDEX
-----
1.  Imports
2.  Configuration & Setup
3.  Core Functions
4.  Main Execution Logic
5.  Command-Line Interface (CLI)
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import sys
import json
import logging
import base64
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
from utils.logger_utils import setup_logger

# ===========================================================================
# 2. Configuration & Setup
# ===========================================================================
load_dotenv()
logger = setup_logger(__name__, "SELLBRITE_API")

TEST_JSON_PATH = config.DATA_DIR / "sellbrite" / "test_sellbrite_listing.json"
API_ENDPOINT = f"{config.SELLBRITE_API_BASE_URL}/products"


# ===========================================================================
# 3. Core Functions
# ===========================================================================

def get_auth_header() -> dict[str, str]:
    """
    Constructs the Basic Authentication header for the Sellbrite API.
    
    MODIFIED: This now matches the authentication method used in the main
    sellbrite_service.py for consistency.
    """
    token = config.SELLBRITE_ACCOUNT_TOKEN
    secret = config.SELLBRITE_SECRET_KEY
    if not token or not secret:
        raise ValueError("Sellbrite credentials (TOKEN, SECRET) are not set in config.")
    
    creds = f"{token}:{secret}".encode("utf-8")
    encoded_creds = base64.b64encode(creds).decode("utf-8")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_creds}"
    }


def load_test_payload(path: Path) -> dict:
    """Loads the test listing data from a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Test JSON file not found: {path}")
    logger.info(f"Loading test payload from {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def post_listing(payload: dict) -> requests.Response:
    """Sends the listing payload to the Sellbrite API."""
    headers = get_auth_header()
    logger.info(f"Sending POST request to {API_ENDPOINT} for SKU {payload.get('sku')}")
    response = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=20)
    return response


# ===========================================================================
# 4. Main Execution Logic
# ===========================================================================

def main():
    """Main function to run the Sellbrite listing test."""
    dry_run = "--dry-run" in sys.argv
    print("🚀 Sellbrite Add Listing Test Started...")
    logger.info("Sellbrite test script initiated.")

    try:
        payload = load_test_payload(TEST_JSON_PATH)
    except Exception as e:
        logger.critical(f"Failed to load test payload: {e}", exc_info=True)
        print(f"❌ Failed to load test payload: {e}")
        return

    if dry_run:
        print("🧪 DRY RUN: Would send this JSON payload to Sellbrite:")
        print(json.dumps(payload, indent=2))
        logger.info("Dry run executed. Payload displayed but not sent.")
        return

    try:
        response = post_listing(payload)
        
        if response.status_code == 201:
            print("✅ Listing successfully created in Sellbrite.")
            logger.info(f"SUCCESS: Sellbrite responded with status {response.status_code}.")
        else:
            print(f"❌ Failed with status {response.status_code}: {response.text}")
            logger.error(f"FAILURE: Sellbrite responded with status {response.status_code}: {response.text}")

        try:
            response_json = response.json()
            logger.info("--- Sellbrite API Response ---")
            logger.info(json.dumps(response_json, indent=2))
            print("📝 Full API response has been saved to the log file.")
        except json.JSONDecodeError:
            logger.info("--- Sellbrite API Response (Raw Text) ---")
            logger.info(response.text)
            
    except Exception as e:
        logger.critical(f"An unexpected error occurred during the API call: {e}", exc_info=True)
        print(f"❌ An unexpected error occurred: {e}")


# ===========================================================================
# 5. Command-Line Interface (CLI)
# ===========================================================================

if __name__ == "__main__":
    main()
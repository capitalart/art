"""
Sellbrite Add Listing Test Script
This utility posts a test product to Sellbrite using credentials from config.py and a sample JSON input.
Run this as a CLI script or from VSCode to verify the integration works.

Robbie Mode™ – Stable, Deterministic, and Logged.
"""

"""
Sellbrite Add Listing Test Script
"""

import sys
from pathlib import Path

# --- Ensure project root is in sys.path ---
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import json
import logging
import requests
from dotenv import load_dotenv
from config import (
    SELLBRITE_ACCOUNT_TOKEN,
    SELLBRITE_SECRET_KEY,
    SELLBRITE_API_BASE_URL,
    DATA_DIR,
    LOGS_DIR,
)

# -----------------------------------------------------------------------------
# 1. Setup & Constants
# -----------------------------------------------------------------------------
load_dotenv()
TEST_JSON_PATH = DATA_DIR / "sellbrite" / "test_sellbrite_listing.json"
RESPONSE_LOG_PATH = LOGS_DIR / "sellbrite_test_response.json"
API_ENDPOINT = f"{SELLBRITE_API_BASE_URL}/products"

# -----------------------------------------------------------------------------
# 2. Auth Headers
# -----------------------------------------------------------------------------
def get_auth_headers() -> dict:
    if not SELLBRITE_ACCOUNT_TOKEN or not SELLBRITE_SECRET_KEY:
        raise ValueError("Sellbrite credentials are not properly set in .env or config.py")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SELLBRITE_ACCOUNT_TOKEN}",
        "X-SB-API-KEY": SELLBRITE_SECRET_KEY,
    }

# -----------------------------------------------------------------------------
# 3. Load Test Payload
# -----------------------------------------------------------------------------
def load_test_payload(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"❌ Test JSON file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# -----------------------------------------------------------------------------
# 4. Post to Sellbrite
# -----------------------------------------------------------------------------
def post_listing(payload: dict, dry_run: bool = False) -> requests.Response | None:
    if dry_run:
        print("🧪 DRY RUN: Would send this JSON to Sellbrite:")
        print(json.dumps(payload, indent=2))
        return None

    headers = get_auth_headers()
    try:
        response = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=10)
        return response
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None

# -----------------------------------------------------------------------------
# 5. Main CLI Logic
# -----------------------------------------------------------------------------
def main():
    dry_run = "--dry-run" in sys.argv
    print("🚀 Sellbrite Listing Test Started...")

    try:
        payload = load_test_payload(TEST_JSON_PATH)
    except Exception as e:
        print(f"❌ Failed to load test payload: {e}")
        return

    response = post_listing(payload, dry_run=dry_run)

    if response is None:
        return

    if response.status_code == 201:
        print("✅ Listing successfully created in Sellbrite.")
    else:
        print(f"❌ Failed with status {response.status_code}: {response.text}")

    try:
        with open(RESPONSE_LOG_PATH, "w", encoding="utf-8") as log_file:
            json.dump(response.json(), log_file, indent=2)
            print(f"📝 Response saved to: {RESPONSE_LOG_PATH}")
    except Exception as e:
        print(f"⚠️ Could not save response JSON: {e}")

# -----------------------------------------------------------------------------
# 6. Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()

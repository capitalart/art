# tests/test_analyze_artwork.py
# ======================================================================================
# FILE: tests/test_analyze_artwork.py
# DESCRIPTION: Test /analyze API endpoint and ensure proper HTML response + cleanup
# AUTHOR: Robbie Mode™ Patch - 2025-07-31 (Final Self-Contained Version)
# ======================================================================================

import os
import shutil
import pytest
from pathlib import Path
from PIL import Image
import sys

# Add project root to path before other imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
import config
from dotenv import load_dotenv

# Load environment variables from system .env
load_dotenv(dotenv_path="/home/art/.env", override=True)

# ======================================================================================
# SECTION 1: Setup
# ======================================================================================

@pytest.fixture
def client():
    """Flask test client fixture for HTTP request simulation."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        # Log in a test user for the session
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'testuser'
        yield client

# ======================================================================================
# SECTION 2: Test Analyze Route – HTML Response
# ======================================================================================

def test_analyze_api_html_response(client):
    """
    Ensure that /analyze/<aspect>/<filename> returns valid HTML content after redirect.
    """
    # --- [ 2.0: Skip if dummy API key ] ---
    openai_key = os.getenv("OPENAI_API_KEY", "test")
    if openai_key.strip().lower() == "test" or not openai_key:
        pytest.skip("Skipping test: Requires a valid OPENAI_API_KEY")

    # --- [ 2.1: Prepare test image and folder structure ] ---
    base_filename = "cassowary-test-01"
    unique_id = "test-run"
    filename = f"{base_filename}-{unique_id}.jpg"
    aspect = "4x5"
    
    unanalysed_subfolder = config.UNANALYSED_ROOT / f"{base_filename}-{unique_id}"
    unanalysed_subfolder.mkdir(parents=True, exist_ok=True)
    destination_img_path = unanalysed_subfolder / filename

    # **FIX:** Create a dummy image file from scratch instead of relying on an external asset
    try:
        Image.new("RGB", (100, 125), "blue").save(destination_img_path)
    except Exception as e:
        pytest.fail(f"Failed to create dummy test image: {e}")

    # --- [ 2.2: POST to the CORRECT /analyze route and follow redirect ] ---
    response = client.post(f"/analyze/{aspect}/{filename}", data={'provider': 'openai'}, follow_redirects=True)

    # --- [ 2.3: Validate response is HTML and contains hidden marker for Edit Page ] ---
    assert response.status_code == 200, "❌ Expected HTTP 200 OK from /analyze redirect"
    assert b"<html" in response.data or b"<div" in response.data, "❌ Expected HTML structure"

    # --- [ 2.4: Check for hidden edit page marker for test validation ] ---
    assert b'id="edit-listing-marker"' in response.data, "❌ Edit page marker not found in HTML"

# ======================================================================================
# SECTION 3: Post-Test Cleanup
# ======================================================================================

def teardown_module(module):
    """
    Cleanup test folders and files from ALL relevant directories after the test run completes.
    """
    patterns = ["test-", "sample-", "good-", "bad-", "cassowary-test-01-test-run"]
    
    # FIX: Add both unanalysed and processed roots to the cleanup path list
    roots_to_clean = [
        Path(config.UNANALYSED_ROOT),
        Path(config.PROCESSED_ROOT)
    ]

    for root in roots_to_clean:
        if not root.exists():
            continue

        for item in root.iterdir():
            if item.is_dir() and any(item.name.startswith(p) for p in patterns):
                try:
                    shutil.rmtree(item)
                    print(f"✅ Cleaned up test folder: {item}")
                except Exception as e:
                    print(f"⚠️ Could not delete test folder {item}: {e}")
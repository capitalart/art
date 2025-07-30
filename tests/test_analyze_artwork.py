# ======================================================================================
# FILE: tests/test_analyze_artwork.py
# DESCRIPTION: Test /analyze API endpoint and ensure proper JSON response + cleanup
# AUTHOR: Robbie Mode™ Patch - 2025-07-30
# ======================================================================================

import os
import shutil
import pytest
from pathlib import Path
from app import app
import config

# ======================================================================================
# SECTION 1: Setup
# ======================================================================================

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

# ======================================================================================
# SECTION 2: Test Endpoint – Analyze JSON
# ======================================================================================

def test_analyze_api_json(client):
    """Test that /analyze returns a valid JSON response for test image, and cleanup after."""

    # --- [ 2.0: Skip if test API key is used ] ---
    openai_key = os.getenv("OPENAI_API_KEY", "test")
    if openai_key.strip().lower() == "test":
        pytest.skip("Skipping test: OPENAI_API_KEY is set to 'test'")

    # --- [ 2.1: Ensure image exists ] ---
    filename = "cassowary-generate-an-aboriginal-dot-painting-of-a-southern-cassowary-casuarius-casuarius-featuring.jpg"
    img_path = Path(config.UNANALYSED_ROOT) / filename

    if not img_path.exists():
        raise FileNotFoundError(f"Test image missing: {img_path}")

    # --- [ 2.2: POST to /analyze ] ---
    response = client.post(f"/analyze/openai/{filename}", follow_redirects=True)

    # --- [ 2.3: Assert JSON returned ] ---
    assert response.status_code == 200, "Expected HTTP 200 OK"
    assert response.is_json, "Response should be JSON"

    json_data = response.get_json()
    assert "listing" in json_data, "JSON missing 'listing' key"
    assert json_data["listing"].get("title"), "Missing title in listing"
    assert json_data["listing"].get("description"), "Missing description in listing"

# ======================================================================================
# SECTION 3: Post-Test Cleanup
# ======================================================================================

def teardown_module(module):
    """Clean up unanalysed-artwork test folders after tests run."""
    patterns = ["test-", "sample-", "good-", "bad-"]
    root = Path(config.UNANALYSED_ROOT)

    for folder in root.iterdir():
        if folder.is_dir() and any(folder.name.startswith(p) for p in patterns):
            try:
                shutil.rmtree(folder)
                print(f"✅ Removed test folder: {folder}")
            except Exception as e:
                print(f"⚠️ Could not delete {folder}: {e}")

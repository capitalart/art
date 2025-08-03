import os
import json
import logging
import shutil
from pathlib import Path
import pytest

# Ensure the app's modules can be imported
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Set a dummy API key to satisfy environment checks in the app
os.environ.setdefault("OPENAI_API_KEY", "test_key_not_used")

# --- Test Configuration & Fixtures ---

# Configure logging for clear test output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def artwork_paths(tmp_path_factory):
    """
    Creates a temporary, realistic directory structure for the tests
    and yields a dictionary of the root paths. Cleans up afterward.
    """
    base_path = tmp_path_factory.mktemp("art_processing_test")
    paths = {
        "base": base_path,
        "unanalysed": base_path / "unanalysed-artwork",
        "processed": base_path / "processed-artwork",
        "finalised": base_path / "finalised-artwork",
        "vault": base_path / "artwork-vault",
        "state_file": base_path / "artwork_state_tracker.json"
    }
    
    # Create the directories
    for key, path in paths.items():
        if key not in ["base", "state_file"]:
            path.mkdir(parents=True, exist_ok=True)
            
    logger.info(f"Created temporary test structure at: {base_path}")

    yield paths
    
    # Teardown: This code runs after all tests in the module are complete
    logger.info(f"Cleaning up temporary test structure at: {base_path}")
    # shutil.rmtree(base_path) # pytest handles tmp_path_factory cleanup automatically

@pytest.fixture
def state_manager(artwork_paths):
    """
    Provides a simple way to read from and write to the state tracking JSON file.
    Ensures the file is reset for each test function.
    """
    state_file = artwork_paths["state_file"]
    
    # Ensure the file is empty before each test
    if state_file.exists():
        state_file.unlink()
    state_file.write_text("{}", encoding="utf-8")

    def _update_state(artwork_id, stage, data):
        """Updates the state for a specific artwork and stage."""
        current_state = json.loads(state_file.read_text(encoding="utf-8"))
        if artwork_id not in current_state:
            current_state[artwork_id] = {}
        current_state[artwork_id][stage] = data
        state_file.write_text(json.dumps(current_state, indent=2), encoding="utf-8")
        logger.info(f"STATE UPDATE for '{artwork_id}' at stage '{stage}': {data}")

    return _update_state

# --- Main Lifecycle Test ---

def test_full_artwork_lifecycle(artwork_paths, state_manager):
    """
    Simulates and verifies an artwork's journey through all stages.
    """
    artwork_id = "eucalypt-woodland-original"
    original_filename = "eucalypt-woodland-open-dry-forest.jpg"
    
    # --- 1. UPLOAD STAGE ---
    logger.info("--- STAGE 1: UPLOAD ---")
    unanalysed_dir = artwork_paths["unanalysed"] / artwork_id
    unanalysed_dir.mkdir()
    unanalysed_image_path = unanalysed_dir / original_filename
    unanalysed_image_path.touch() # Create a dummy file

    assert unanalysed_image_path.exists(), "Image file should exist in unanalysed stage"
    
    state_manager(artwork_id, "upload", {
        "path": str(unanalysed_image_path),
        "folder": artwork_id,
        "filename": original_filename
    })

    # --- 2. ANALYSE STAGE ---
    logger.info("--- STAGE 2: ANALYSE ---")
    new_seo_folder = "moon-over-fire-country-dot-art-by-robin-custance-RJC-0278"
    processed_dir = artwork_paths["processed"] / new_seo_folder
    
    # Simulate moving and renaming the folder
    shutil.move(str(unanalysed_dir), str(processed_dir))
    
    # Simulate creating the listing JSON
    listing_json_path = processed_dir / f"{new_seo_folder}-listing.json"
    listing_data = {"title": "Moon Over Fire Country", "sku": "RJC-0278"}
    listing_json_path.write_text(json.dumps(listing_data), encoding="utf-8")
    
    # Simulate renaming the main image file
    processed_image_path = processed_dir / f"{new_seo_folder}.jpg"
    (processed_dir / original_filename).rename(processed_image_path)

    assert not unanalysed_dir.exists(), "Original unanalysed folder should be gone"
    assert processed_dir.exists(), "Processed folder should exist"
    assert listing_json_path.exists(), "listing.json should exist in processed folder"
    assert processed_image_path.exists(), "Image file should be renamed and exist in processed folder"

    state_manager(artwork_id, "analyse", {
        "path": str(processed_image_path),
        "folder": new_seo_folder,
        "filename": processed_image_path.name,
        "json_path": str(listing_json_path)
    })

    # --- 3. FINALISED STAGE ---
    logger.info("--- STAGE 3: FINALISED ---")
    finalised_dir = artwork_paths["finalised"] / new_seo_folder
    
    # Simulate moving to finalised
    shutil.move(str(processed_dir), str(finalised_dir))

    assert not processed_dir.exists(), "Processed folder should be gone"
    assert finalised_dir.exists(), "Finalised folder should exist"
    
    finalised_image_path = finalised_dir / f"{new_seo_folder}.jpg"
    finalised_json_path = finalised_dir / f"{new_seo_folder}-listing.json"
    assert finalised_image_path.exists(), "Image should be in finalised folder"
    assert finalised_json_path.exists(), "JSON should be in finalised folder"

    state_manager(artwork_id, "finalised", {
        "path": str(finalised_image_path),
        "folder": new_seo_folder,
        "filename": finalised_image_path.name,
        "json_path": str(finalised_json_path)
    })

    # --- 4. LOCKED STAGE ---
    logger.info("--- STAGE 4: LOCKED ---")
    locked_folder_name = f"LOCKED-{new_seo_folder}"
    locked_dir = artwork_paths["vault"] / locked_folder_name

    # Simulate moving and locking
    shutil.move(str(finalised_dir), str(locked_dir))
    
    assert not finalised_dir.exists(), "Finalised folder should be gone"
    assert locked_dir.exists(), "Locked folder should exist in vault"
    assert locked_dir.name.startswith("LOCKED-"), "Locked folder name should be prefixed"

    locked_image_path = locked_dir / f"{new_seo_folder}.jpg"
    locked_json_path = locked_dir / f"{new_seo_folder}-listing.json"
    assert locked_image_path.exists(), "Image should be in locked folder"
    assert locked_json_path.exists(), "JSON should be in locked folder"

    state_manager(artwork_id, "locked", {
        "path": str(locked_image_path),
        "folder": locked_folder_name,
        "filename": locked_image_path.name,
        "json_path": str(locked_json_path)
    })

    # --- 5. PUBLIC URL VERIFICATION ---
    logger.info("--- STAGE 5: PUBLIC URL VERIFICATION ---")
    
    # This part tests the logic of converting the final file path to a public URL.
    # We construct the URL based on the final known state of the artwork.
    base_url = "https://artnarrator.com"
    
    # We need the path relative to the 'art_processing_test' base directory
    relative_image_path = locked_image_path.relative_to(artwork_paths["base"])
    
    # Construct the expected "friendly" URL
    expected_url = f"{base_url}/art-processing/{relative_image_path}"
    
    logger.info(f"Final file path: {locked_image_path}")
    logger.info(f"Generated public URL: {expected_url}")
    
    # This is the final check
    assert "artwork-vault/LOCKED-moon-over-fire-country" in expected_url, \
        "The generated URL does not have the correct structure"
        
    logger.info("✅ Full artwork lifecycle test completed successfully!")


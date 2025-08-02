# tests/test_sku_tracker.py
import json
import os
import shutil
from pathlib import Path
import sys
from PIL import Image
from unittest import mock
import pytest

# Add project root to path to allow imports
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

# Import the necessary modules and test utilities
os.environ.setdefault("OPENAI_API_KEY", "test")
import config
from scripts import analyze_artwork as aa
from routes import utils

@pytest.fixture
def isolated_fs_sku(tmp_path, monkeypatch):
    """A fixture to create an isolated filesystem for SKU tests."""
    # Create temporary directories
    unanalysed_dir = tmp_path / "unanalysed-artwork"
    processed_dir = tmp_path / "processed-artwork"
    unanalysed_dir.mkdir()
    processed_dir.mkdir()
    
    # Create temporary registry file
    registry_file = tmp_path / "master-artwork-paths.json"
    registry_file.write_text("{}")

    # Monkeypatch config to use our temporary paths
    monkeypatch.setattr(config, "UNANALYSED_ROOT", unanalysed_dir)
    monkeypatch.setattr(config, "PROCESSED_ROOT", processed_dir)
    monkeypatch.setattr(config, "OUTPUT_JSON", registry_file)
    
    yield unanalysed_dir

class DummyChoice:
    def __init__(self, text):
        self.message = type('m', (), {'content': text})

class DummyResp:
    def __init__(self, text):
        self.choices = [DummyChoice(text)]

SAMPLE_JSON1 = json.dumps({
    "title": "First Artwork", "description": "Test description", "tags": ["tag"], "materials": ["mat"],
    "primary_colour": "Black", "secondary_colour": "Brown", "price": 18.27
})
SAMPLE_JSON2 = json.dumps({
    "title": "Second Artwork", "description": "Test description", "tags": ["tag"], "materials": ["mat"],
    "primary_colour": "Black", "secondary_colour": "Brown", "price": 18.27
})

def test_sequential_sku_assignment(tmp_path, monkeypatch, isolated_fs_sku):
    tracker = tmp_path / 'sku_tracker.json'
    tracker.write_text(json.dumps({"last_sku": 80}))
    monkeypatch.setattr(config, "SKU_TRACKER", tracker)

    # Create fresh, reliable images for the test run in the isolated directory
    img1_folder = isolated_fs_sku / "img1_subfolder"
    img2_folder = isolated_fs_sku / "img2_subfolder"
    img1_folder.mkdir()
    img2_folder.mkdir()
    
    img1 = img1_folder / 'a.jpg'
    img2 = img2_folder / 'b.jpg'
    Image.new('RGB', (10, 10), 'red').save(img1)
    Image.new('RGB', (10, 10), 'blue').save(img2)

    responses = [DummyResp(SAMPLE_JSON1), DummyResp(SAMPLE_JSON2)]
    with mock.patch.object(aa.client.chat.completions, 'create', side_effect=responses):
        entry1 = aa.analyze_single(img1)
        entry2 = aa.analyze_single(img2)

    assert entry1['sku'] == 'RJC-0081'
    assert entry2['sku'] == 'RJC-0082'
    assert json.loads(tracker.read_text())['last_sku'] == 82
    
    path1 = Path(entry1['processed_folder']) / f"{Path(entry1['processed_folder']).name}-listing.json"
    path2 = Path(entry2['processed_folder']) / f"{Path(entry2['processed_folder']).name}-listing.json"

    utils.assign_or_get_sku(path1, tracker, force=True)
    utils.assign_or_get_sku(path2, tracker, force=True)

    assert json.loads(tracker.read_text())['last_sku'] == 84

    with mock.patch.object(aa.client.chat.completions, 'create', return_value=DummyResp(SAMPLE_JSON1)):
        # Re-analyze the same file. The erroneous copy line has been removed.
        entry1b = aa.analyze_single(img1)

    assert entry1b['sku'] == 'RJC-0085'
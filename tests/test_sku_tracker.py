import json
import os
import shutil
from pathlib import Path
import sys
from PIL import Image
from unittest import mock

# Add project root to path to allow imports
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

# Import the necessary modules and test utilities
os.environ.setdefault("OPENAI_API_KEY", "test")
import config
from scripts import analyze_artwork as aa
from routes import utils


class DummyChoice:
    def __init__(self, text):
        self.message = type('m', (), {'content': text})

class DummyResp:
    def __init__(self, text):
        self.choices = [DummyChoice(text)]


SAMPLE_JSON1 = json.dumps({
    "title": "First Artwork",
    "description": "Test description",
    "tags": ["tag"],
    "materials": ["mat"],
    "primary_colour": "Black",
    "secondary_colour": "Brown"
})

SAMPLE_JSON2 = json.dumps({
    "title": "Second Artwork",
    "description": "Test description",
    "tags": ["tag"],
    "materials": ["mat"],
    "primary_colour": "Black",
    "secondary_colour": "Brown"
})


def test_sequential_sku_assignment(tmp_path, monkeypatch):
    tracker = tmp_path / 'sku_tracker.json'
    tracker.write_text(json.dumps({"last_sku": 80}))
    monkeypatch.setattr(config, "SKU_TRACKER", tracker)

    # remove any pre-existing output folders from previous runs
    for folder in ('first-artwork', 'second-artwork'):
        shutil.rmtree(config.PROCESSED_ROOT / folder, ignore_errors=True)

    img_iter = config.UNANALYSED_ROOT.rglob('*.jpg')
    img_src = next(img_iter, None)
    if img_src is None:
        config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
        img_src = config.UNANALYSED_ROOT / 'sample.jpg'
        Image.new('RGB', (10, 10), 'red').save(img_src)
    img1 = tmp_path / 'a.jpg'
    img2 = tmp_path / 'b.jpg'
    shutil.copy2(img_src, img1)
    shutil.copy2(img_src, img2)

    responses = [DummyResp(SAMPLE_JSON1), DummyResp(SAMPLE_JSON2)]
    with mock.patch.object(aa.client.chat.completions, 'create', side_effect=responses):
        entry1 = aa.analyze_single(img1)
        entry2 = aa.analyze_single(img2)

    # Analysis stage now assigns a unique SKU
    assert entry1['sku'] == 'RJC-0081'
    assert entry2['sku'] == 'RJC-0082'
    assert json.loads(tracker.read_text())['last_sku'] == 82

    # Finalising assigns sequential SKUs
    utils.assign_or_get_sku(Path(entry1['processed_folder']) / f"{entry1['seo_filename'].replace('.jpg', '-listing.json')}", tracker, force=True)
    utils.assign_or_get_sku(Path(entry2['processed_folder']) / f"{entry2['seo_filename'].replace('.jpg', '-listing.json')}", tracker, force=True)

    assert json.loads(tracker.read_text())['last_sku'] == 84

    with mock.patch.object(aa.client.chat.completions, 'create', return_value=DummyResp(SAMPLE_JSON1)):
        shutil.copy2(img_src, img1)
        entry1b = aa.analyze_single(img1)

    assert entry1b['sku'] == 'RJC-0085'
import json
import os
import shutil
from pathlib import Path
import sys
from PIL import Image
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("SKU_TRACKER_PATH", str(Path("/tmp/sku_tracker_default.json")))
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "scripts"))
from config import UNANALYSED_ROOT, PROCESSED_ROOT
from unittest import mock
import analyze_artwork as aa
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


def test_sequential_sku_assignment(tmp_path):
    tracker = tmp_path / 'sku_tracker.json'
    tracker.write_text(json.dumps({"last_sku": 80}))
    os.environ['SKU_TRACKER_PATH'] = str(tracker)
    aa.SKU_TRACKER = Path(os.environ['SKU_TRACKER_PATH'])

    # remove any pre-existing output folders from previous runs
    for folder in ('first-artwork', 'second-artwork'):
        shutil.rmtree(PROCESSED_ROOT / folder, ignore_errors=True)

    img_iter = UNANALYSED_ROOT.rglob('*.jpg')
    img_src = next(img_iter, None)
    if img_src is None:
        UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
        img_src = UNANALYSED_ROOT / 'sample.jpg'
        Image.new('RGB', (10, 10), 'red').save(img_src)
    img1 = tmp_path / 'a.jpg'
    img2 = tmp_path / 'b.jpg'
    shutil.copy2(img_src, img1)
    shutil.copy2(img_src, img2)

    responses = [DummyResp(SAMPLE_JSON1), DummyResp(SAMPLE_JSON2)]
    with mock.patch.object(aa.client.chat.completions, 'create', side_effect=responses):
        system_prompt = aa.read_onboarding_prompt()
        status = []
        entry1 = aa.analyze_single(img1, system_prompt, None, status)
        entry2 = aa.analyze_single(img2, system_prompt, None, status)

    # Analysis stage only previews the next SKU
    assert entry1['sku'] == 'RJC-0081'
    assert entry2['sku'] == 'RJC-0081'
    assert json.loads(tracker.read_text())['last_sku'] == 80

    # Finalising assigns sequential SKUs
    utils.assign_or_get_sku(Path(entry1['processed_folder']) / f"{entry1['seo_name']}-listing.json", tracker, force=True)
    utils.assign_or_get_sku(Path(entry2['processed_folder']) / f"{entry2['seo_name']}-listing.json", tracker, force=True)

    assert json.loads(tracker.read_text())['last_sku'] == 82

    with mock.patch.object(aa.client.chat.completions, 'create', return_value=DummyResp(SAMPLE_JSON1)):
        system_prompt = aa.read_onboarding_prompt()
        status = []
        shutil.copy2(img_src, img1)
        entry1b = aa.analyze_single(img1, system_prompt, None, status)

    assert entry1b['sku'] == 'RJC-0081'

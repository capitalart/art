import json
from pathlib import Path
from routes import utils


def test_assign_or_get_sku(tmp_path):
    tracker = tmp_path / 'sku.json'
    tracker.write_text(json.dumps({"last_sku": 5}))
    listing = tmp_path / 'art-listing.json'
    listing.write_text(json.dumps({"title": "Test"}))

    sku = utils.assign_or_get_sku(listing, tracker)
    assert sku == 'RJC-0006'
    assert json.loads(listing.read_text())['sku'] == sku
    assert json.loads(tracker.read_text())['last_sku'] == 6

    # Calling again should keep same SKU
    sku2 = utils.assign_or_get_sku(listing, tracker)
    assert sku2 == sku
    assert json.loads(tracker.read_text())['last_sku'] == 6


def test_assign_sku_updates_seo_filename(tmp_path):
    tracker = tmp_path / 'sku.json'
    tracker.write_text(json.dumps({"last_sku": 1}))
    listing = tmp_path / 'listing.json'
    listing.write_text(json.dumps({
        "title": "Test",
        "seo_filename": "Test-Artwork-by-Robin-Custance-RJC-0000.jpg"
    }))

    sku = utils.assign_or_get_sku(listing, tracker)
    data = json.loads(listing.read_text())
    assert sku == 'RJC-0002'
    assert data['sku'] == sku
    assert data['seo_filename'].endswith(f"{sku}.jpg")

    sku2 = utils.assign_or_get_sku(listing, tracker)
    data2 = json.loads(listing.read_text())
    assert sku2 == sku
    assert data2['seo_filename'].endswith(f"{sku}.jpg")
    assert json.loads(tracker.read_text())['last_sku'] == 2


def test_validate_all_skus(tmp_path):
    tracker = tmp_path / 'sku.json'
    tracker.write_text(json.dumps({"last_sku": 2}))

    good = [{"sku": "RJC-0001"}, {"sku": "RJC-0002"}]
    assert utils.validate_all_skus(good, tracker) == []

    dup = [{"sku": "RJC-0001"}, {"sku": "RJC-0001"}]
    assert any('Duplicate' in e for e in utils.validate_all_skus(dup, tracker))

    gap = [{"sku": "RJC-0001"}, {"sku": "RJC-0003"}]
    assert any('Gap' in e for e in utils.validate_all_skus(gap, tracker))

    missing = [{}, {"sku": "RJC-0002"}]
    assert any('invalid' in e for e in utils.validate_all_skus(missing, tracker))

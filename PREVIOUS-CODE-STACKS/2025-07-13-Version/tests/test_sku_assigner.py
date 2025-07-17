import json
from pathlib import Path

from utils.sku_assigner import get_next_sku, peek_next_sku


def test_peek_does_not_increment(tmp_path):
    tracker = tmp_path / "tracker.json"
    tracker.write_text(json.dumps({"last_sku": 2}))
    peek = peek_next_sku(tracker)
    assert peek == "RJC-0003"
    assert json.loads(tracker.read_text())['last_sku'] == 2


def test_get_next_sku_increments(tmp_path):
    tracker = tmp_path / "tracker.json"
    tracker.write_text(json.dumps({"last_sku": 10}))
    first = get_next_sku(tracker)
    second = get_next_sku(tracker)
    assert first == "RJC-0011"
    assert second == "RJC-0012"
    assert json.loads(tracker.read_text())['last_sku'] == 12


def test_cancel_does_not_consume(tmp_path):
    tracker = tmp_path / "tracker.json"
    tracker.write_text(json.dumps({"last_sku": 5}))
    preview = peek_next_sku(tracker)
    assert preview == "RJC-0006"
    # no assignment yet
    assert json.loads(tracker.read_text())['last_sku'] == 5
    final = get_next_sku(tracker)
    assert final == preview
    assert json.loads(tracker.read_text())['last_sku'] == 6

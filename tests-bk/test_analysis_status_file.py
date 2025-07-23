import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes.utils import load_json_file_safe


def test_load_json_file_safe_missing(tmp_path, caplog):
    test_file = tmp_path / 'missing.json'
    with caplog.at_level(logging.WARNING):
        data = load_json_file_safe(test_file)
    assert data == {}
    assert test_file.exists()
    assert test_file.read_text() == '{}'
    assert 'created new empty file' in caplog.text


def test_load_json_file_safe_empty(tmp_path, caplog):
    test_file = tmp_path / 'empty.json'
    test_file.write_text('   ')
    with caplog.at_level(logging.WARNING):
        data = load_json_file_safe(test_file)
    assert data == {}
    assert test_file.read_text() == '{}'
    assert 'reset to {}' in caplog.text


def test_load_json_file_safe_invalid(tmp_path, caplog):
    test_file = tmp_path / 'invalid.json'
    test_file.write_text('{bad json')
    with caplog.at_level(logging.ERROR):
        data = load_json_file_safe(test_file)
    assert data == {}
    assert test_file.read_text() == '{}'
    assert 'Invalid JSON' in caplog.text


def test_load_json_file_safe_valid(tmp_path):
    test_file = tmp_path / 'valid.json'
    content = {'a': 1}
    test_file.write_text(json.dumps(content))
    data = load_json_file_safe(test_file)
    assert data == content

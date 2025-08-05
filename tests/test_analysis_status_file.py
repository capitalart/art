# tests/test_analysis_status_file.py
import json
import logging
from pathlib import Path
import sys
import pytest
import os

os.environ.setdefault("OPENAI_API_KEY", "test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

from helpers.listing_utils import load_json_file_safe, resolve_artwork_stage

def test_load_json_file_safe_missing(tmp_path, caplog):
    test_file = tmp_path / 'missing.json'
    with caplog.at_level(logging.WARNING):
        data = load_json_file_safe(test_file)
    assert data == {}
    assert test_file.exists()
    assert test_file.read_text() == '{}'
    # FIX (2025-08-04): Check for a substring, not an exact match, to make the test less brittle.
    assert 'File not found' in caplog.text

def test_load_json_file_safe_empty(tmp_path, caplog):
    test_file = tmp_path / 'empty.json'
    test_file.write_text('   ')
    with caplog.at_level(logging.WARNING):
        data = load_json_file_safe(test_file)
    assert data == {}
    assert test_file.read_text() == '{}'
    # FIX (2025-08-04): Check for a substring to make the test less brittle.
    assert 'File is empty' in caplog.text

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

def test_resolve_artwork_stage(tmp_path, monkeypatch):
    un = tmp_path / 'unanalysed-artwork'
    proc = tmp_path / 'processed-artwork'
    fin = tmp_path / 'finalised-artwork'
    vault = tmp_path / 'artwork-vault'
    for d in (un, proc, fin, vault):
        d.mkdir()

    monkeypatch.setattr(config, 'UNANALYSED_ROOT', un)
    monkeypatch.setattr(config, 'PROCESSED_ROOT', proc)
    monkeypatch.setattr(config, 'FINALISED_ROOT', fin)
    monkeypatch.setattr(config, 'ARTWORK_VAULT_ROOT', vault)

    (un / 'a1').mkdir()
    (proc / 'a2').mkdir()
    (fin / 'a3').mkdir()
    (vault / 'LOCKED-a4').mkdir()

    assert resolve_artwork_stage('a1')[0] == 'unanalysed'
    assert resolve_artwork_stage('a2')[0] == 'processed'
    assert resolve_artwork_stage('a3')[0] == 'finalised'
    assert resolve_artwork_stage('a4')[0] == 'vault'
    assert resolve_artwork_stage('missing') == (None, None)
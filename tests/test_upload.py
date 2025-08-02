# tests/test_upload.py
import io
import json
from pathlib import Path
import os
import sys
from PIL import Image
from unittest import mock
import pytest
import shutil

os.environ.setdefault("OPENAI_API_KEY", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config
from utils import session_tracker

@pytest.fixture
def isolated_fs(tmp_path, monkeypatch):
    """A fixture to create an isolated filesystem for upload/analysis tests."""
    unanalysed_dir = tmp_path / "unanalysed-artwork"
    unanalysed_dir.mkdir()
    
    # Monkeypatch config to use our temporary directories
    monkeypatch.setattr(config, "UNANALYSED_ROOT", unanalysed_dir)
    
    # Create a dummy image for tests to use
    img_path = unanalysed_dir / 'sample.jpg'
    Image.new('RGB', (10, 10), 'red').save(img_path)
    
    yield unanalysed_dir # Provide the temp dir to the test

    # Pytest's tmp_path handles the cleanup automatically after the test yields.

def test_upload_single(isolated_fs):
    client = app.test_client()
    img_path = isolated_fs / 'sample.jpg'
    data = img_path.read_bytes()

    resp = client.post('/upload', data={'images': (io.BytesIO(data), 'test.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    # Check that a new subfolder was created inside our isolated directory
    subfolders = [d for d in isolated_fs.iterdir() if d.is_dir()]
    assert len(subfolders) == 1
    created_files = list(subfolders[0].glob("*.jpg"))
    assert len(created_files) > 0 # At least the original was saved

def test_upload_reject_corrupt(isolated_fs):
    client = app.test_client()
    bad_data = io.BytesIO(b'not-a-real-image')
    
    resp = client.post('/upload', data={'images': (bad_data, 'bad.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    # Check that the flash message indicates an error
    assert b'Image processing failed' in resp.data

def test_upload_batch(isolated_fs):
    client = app.test_client()
    img_path = isolated_fs / 'sample.jpg'
    good_data = img_path.read_bytes()
    bad_data = io.BytesIO(b'this-is-not-an-image')
    
    resp = client.post('/upload', data={'images': [
        (io.BytesIO(good_data), 'good.jpg'), 
        (bad_data, 'bad.jpg')
    ]}, content_type='multipart/form-data', follow_redirects=True)

    assert resp.status_code == 200
    assert b'Uploaded 1 file(s) successfully' in resp.data
    assert b'bad.jpg: Image processing failed' in resp.data

def test_upload_json_response(isolated_fs):
    client = app.test_client()
    for s in session_tracker.active_sessions('robbie'):
        session_tracker.remove_session('robbie', s['session_id'])
    client.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=True)
    
    img_path = isolated_fs / 'sample.jpg'
    data = img_path.read_bytes()
    
    resp = client.post('/upload',
        data={'images': (io.BytesIO(data), 'sample.jpg')},
        content_type='multipart/form-data',
        headers={'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})
        
    assert resp.status_code == 200
    json_response = resp.get_json()
    assert isinstance(json_response, list)
    assert len(json_response) == 1
    assert json_response[0]['success'] is True
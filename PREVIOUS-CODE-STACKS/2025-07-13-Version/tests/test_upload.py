import io
import json
from pathlib import Path
import os
import sys
os.environ.setdefault("OPENAI_API_KEY", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config
import scripts.analyze_artwork as aa
from unittest import mock


def dummy_openai_response(text):
    class C:
        def __init__(self, t):
            self.message = type('m', (), {'content': t})
    class R:
        def __init__(self, t):
            self.choices = [C(t)]
    return R(text)

SAMPLE_JSON = json.dumps({
    "seo_filename": "uploaded-artwork-by-robin-custance-rjc-9999.jpg",
    "title": "Test",
    "description": "desc",
    "tags": ["tag"],
    "materials": ["mat"],
    "primary_colour": "Black",
    "secondary_colour": "Brown"
})


def test_upload_single(tmp_path):
    client = app.test_client()
    client.post('/login', data={'username': os.getenv('ADMIN_USER','robbie'), 'password': os.getenv('ADMIN_PASS','secret')})
    img_path = next((config.ARTWORKS_INPUT_DIR).rglob('*.jpg'))
    data = img_path.read_bytes()
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': (io.BytesIO(data), 'test.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()
    tmp_files = list(config.UPLOADS_TEMP_DIR.glob('*.qc.json'))
    assert tmp_files, "QC file not created"


def test_upload_reject_corrupt(tmp_path):
    client = app.test_client()
    client.post('/login', data={'username': os.getenv('ADMIN_USER','robbie'), 'password': os.getenv('ADMIN_PASS','secret')})
    bad = io.BytesIO(b'notanimage')
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': (bad, 'bad.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    assert '\u274c'.encode() in resp.data or b'error' in resp.data
    m.assert_not_called()


def test_upload_batch(tmp_path):
    client = app.test_client()
    client.post('/login', data={'username': os.getenv('ADMIN_USER','robbie'), 'password': os.getenv('ADMIN_PASS','secret')})
    img_path = next((config.ARTWORKS_INPUT_DIR).rglob('*.jpg'))
    good = img_path.read_bytes()
    bad = io.BytesIO(b'bad')
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': [(io.BytesIO(good), 'good.jpg'), (bad, 'bad.jpg')]}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()
    qc_files = list(config.UPLOADS_TEMP_DIR.glob('*.qc.json'))
    assert len(qc_files) >= 1


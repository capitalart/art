import io
import json
from pathlib import Path
import os
import sys
from PIL import Image
os.environ.setdefault("OPENAI_API_KEY", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config
import scripts.analyze_artwork as aa
from unittest import mock
from utils import session_tracker


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
    img_iter = config.UNANALYSED_ROOT.rglob('*.jpg')
    img_path = next(img_iter, None)
    if img_path is None:
        config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
        img_path = config.UNANALYSED_ROOT / 'sample.jpg'
        Image.new('RGB', (10, 10), 'red').save(img_path)
    data = img_path.read_bytes()
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': (io.BytesIO(data), 'test.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()



def test_upload_reject_corrupt(tmp_path):
    client = app.test_client()
    bad = io.BytesIO(b'notanimage')
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': (bad, 'bad.jpg')}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()


def test_upload_batch(tmp_path):
    client = app.test_client()
    img_iter = config.UNANALYSED_ROOT.rglob('*.jpg')
    img_path = next(img_iter, None)
    if img_path is None:
        config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
        img_path = config.UNANALYSED_ROOT / 'sample.jpg'
        Image.new('RGB', (10, 10), 'red').save(img_path)
    good = img_path.read_bytes()
    bad = io.BytesIO(b'bad')
    with mock.patch.object(aa.client.chat.completions, 'create') as m:
        resp = client.post('/upload', data={'images': [(io.BytesIO(good), 'good.jpg'), (bad, 'bad.jpg')]}, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    m.assert_not_called()


def test_upload_json_response(tmp_path):
    client = app.test_client()
    for s in session_tracker.active_sessions('robbie'):
        session_tracker.remove_session('robbie', s['session_id'])
    client.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=True)
    config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    img = config.UNANALYSED_ROOT / 'json-sample.jpg'
    Image.new('RGB', (10, 10), 'green').save(img)
    data = img.read_bytes()
    with mock.patch.object(aa.client.chat.completions, 'create'):
        resp = client.post('/upload',
            data={'images': (io.BytesIO(data), 'sample.jpg')},
            content_type='multipart/form-data',
            headers={'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 200
    arr = resp.get_json()
    assert isinstance(arr, list) and arr[0]['success']



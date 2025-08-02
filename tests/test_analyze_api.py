# tests/test_analyze_api.py
import io
import json
from pathlib import Path
from PIL import Image
import sys
import os
import pytest
import shutil # <-- FIX: Added the missing import
from unittest import mock

os.environ.setdefault("OPENAI_API_KEY", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config
from utils import session_tracker
import routes.utils as routes_utils

# A pytest fixture to create and automatically clean up test files.
@pytest.fixture
def api_test_image(monkeypatch):
    """Creates a temporary folder and image for API tests and ensures cleanup."""
    temp_unanalysed_dir = config.UNANALYSED_ROOT / "api_test_temp"
    temp_unanalysed_dir.mkdir(parents=True, exist_ok=True)
    
    # Monkeypatch the config to ensure the app looks in our temp test folder
    monkeypatch.setattr(config, "UNANALYSED_ROOT", temp_unanalysed_dir)
    
    # Yield a function to create specific files
    def _create_file(name, content):
        path = temp_unanalysed_dir / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            Image.new("RGB", (10, 10), content).save(path)
        return path

    yield _create_file
    
    # Teardown: This code runs after each test, ensuring the folder is deleted.
    shutil.rmtree(temp_unanalysed_dir, ignore_errors=True)


def test_analyze_api_json(tmp_path, api_test_image):
    client = app.test_client()
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    client.post(
        "/login",
        data={"username": "robbie", "password": "kangaroo123"},
        follow_redirects=True,
    )
    api_test_image("dummy.jpg", "blue") # Create the test image using the fixture

    seo_folder = "dummy-artwork"
    dummy_entry = {
        "processed_folder": str(config.PROCESSED_ROOT / seo_folder),
        "seo_filename": f"{seo_folder}.jpg",
        "aspect_ratio": "square",
    }

    with mock.patch(
        "routes.artwork_routes._run_ai_analysis", return_value=dummy_entry
    ), mock.patch("routes.artwork_routes._generate_composites"):
        resp = client.post(
            "/analyze/square/dummy.jpg",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"]


def test_analyze_api_strip_bytes(tmp_path, monkeypatch, api_test_image):
    client = app.test_client()
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    client.post(
        "/login",
        data={"username": "robbie", "password": "kangaroo123"},
        follow_redirects=True,
    )
    api_test_image("byte.jpg", b"") # Create the test image using the fixture

    seo_folder = "byte-art"
    dummy_entry = {
        "processed_folder": str(config.PROCESSED_ROOT / seo_folder),
        "seo_filename": f"{seo_folder}.jpg",
        "aspect_ratio": "square",
        "blob": b"bigdata",
    }

    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(routes_utils, "LOGS_DIR", tmp_path)

    with mock.patch(
        "routes.artwork_routes._run_ai_analysis", return_value=dummy_entry
    ), mock.patch("routes.artwork_routes._generate_composites"):
        resp = client.post(
            "/analyze/square/byte.jpg",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert "blob" not in json.dumps(data)


def test_analyze_api_error_bytes(tmp_path, monkeypatch, api_test_image):
    client = app.test_client()
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    client.post(
        "/login",
        data={"username": "robbie", "password": "kangaroo123"},
        follow_redirects=True,
    )
    api_test_image("err.jpg", b"") # Create the test image using the fixture

    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(routes_utils, "LOGS_DIR", tmp_path)

    with mock.patch(
        "routes.artwork_routes._run_ai_analysis", side_effect=RuntimeError(b"oops")
    ), mock.patch("routes.artwork_routes._generate_composites"):
        resp = client.post(
            "/analyze/square/err.jpg",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )

    assert resp.status_code == 500
    text = resp.get_data(as_text=True)
    assert "oops" in text
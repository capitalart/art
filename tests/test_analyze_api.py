import io
import json
from pathlib import Path
from PIL import Image
import sys
import os

os.environ.setdefault("OPENAI_API_KEY", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config
from unittest import mock
from utils import session_tracker
import routes.utils as routes_utils


def test_analyze_api_json(tmp_path):
    client = app.test_client()
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    client.post(
        "/login",
        data={"username": "robbie", "password": "kangaroo123"},
        follow_redirects=True,
    )
    # Ensure an image exists in the unanalysed folder
    config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    img_path = config.UNANALYSED_ROOT / "dummy.jpg"
    Image.new("RGB", (10, 10), "blue").save(img_path)

    seo_folder = "dummy-artwork"

    # CORRECTED: The dummy data now perfectly mimics the real script's output
    dummy_entry = {
        "processed_folder": str(config.PROCESSED_ROOT / seo_folder),
        "seo_filename": f"{seo_folder}.jpg",
        "aspect_ratio": "square",
    }

    # REMOVED: Unnecessary mocks that are no longer used by the refactored route
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


def test_analyze_api_strip_bytes(tmp_path, monkeypatch):
    client = app.test_client()
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    client.post(
        "/login",
        data={"username": "robbie", "password": "kangaroo123"},
        follow_redirects=True,
    )
    config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    (config.UNANALYSED_ROOT / "byte.jpg").write_bytes(b"")

    seo_folder = "byte-art"

    # CORRECTED: The dummy data now perfectly mimics the real script's output
    dummy_entry = {
        "processed_folder": str(config.PROCESSED_ROOT / seo_folder),
        "seo_filename": f"{seo_folder}.jpg",
        "aspect_ratio": "square",
        "blob": b"bigdata",
    }

    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(routes_utils, "LOGS_DIR", tmp_path)

    # REMOVED: Unnecessary mocks
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


def test_analyze_api_error_bytes(tmp_path, monkeypatch):
    client = app.test_client()
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    client.post(
        "/login",
        data={"username": "robbie", "password": "kangaroo123"},
        follow_redirects=True,
    )
    config.UNANALYSED_ROOT.mkdir(parents=True, exist_ok=True)
    (config.UNANALYSED_ROOT / "err.jpg").write_bytes(b"")

    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(routes_utils, "LOGS_DIR", tmp_path)

    # This test is fine as is, but we'll remove the unused mock for consistency
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
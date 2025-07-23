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
    processed_dir = tmp_path
    listing_path = processed_dir / f"{seo_folder}-listing.json"
    listing_path.write_text(json.dumps({"title": "t"}))

    dummy_entry = {
        "seo_name": seo_folder,
        "processed_folder": str(processed_dir),
    }

    with mock.patch(
        "routes.artwork_routes._run_ai_analysis", return_value=dummy_entry
    ), mock.patch("routes.artwork_routes._generate_composites"), mock.patch(
        "routes.artwork_routes.utils.find_aspect_filename_from_seo_folder",
        return_value=("square", f"{seo_folder}.jpg"),
    ):
        resp = client.post(
            "/analyze-openai/dummy.jpg",
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
    img_path = config.UNANALYSED_ROOT / "byte.jpg"
    Image.new("RGB", (10, 10), "blue").save(img_path)

    seo_folder = "byte-art"
    processed_dir = tmp_path
    (processed_dir / f"{seo_folder}-listing.json").write_text("{}")

    dummy_entry = {
        "seo_name": seo_folder,
        "processed_folder": str(processed_dir),
        "blob": b"bigdata",
    }

    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(routes_utils, "LOGS_DIR", tmp_path)

    with mock.patch(
        "routes.artwork_routes._run_ai_analysis", return_value=dummy_entry
    ), mock.patch("routes.artwork_routes._generate_composites"), mock.patch(
        "routes.artwork_routes.utils.find_aspect_filename_from_seo_folder",
        return_value=("square", f"{seo_folder}.jpg"),
    ):
        resp = client.post(
            "/analyze-openai/byte.jpg",
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
    img_path = config.UNANALYSED_ROOT / "err.jpg"
    Image.new("RGB", (10, 10), "blue").save(img_path)

    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(routes_utils, "LOGS_DIR", tmp_path)

    with mock.patch(
        "routes.artwork_routes._run_ai_analysis", side_effect=RuntimeError(b"oops")
    ), mock.patch("routes.artwork_routes._generate_composites"), mock.patch(
        "routes.artwork_routes.utils.find_aspect_filename_from_seo_folder",
        return_value=("square", "err.jpg"),
    ):
        resp = client.post(
            "/analyze-openai/err.jpg",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )

    assert resp.status_code == 500
    text = resp.get_data(as_text=True)
    assert "oops" not in text
    assert "b'" not in text

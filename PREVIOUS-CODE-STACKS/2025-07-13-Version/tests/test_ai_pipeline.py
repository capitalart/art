import json
import os
from pathlib import Path
from unittest import mock

import importlib
import sys

root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "scripts"))


def setup_env(tmp_path):
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ["LOGS_DIR"] = str(tmp_path / "logs")
    os.environ["PARSE_FAILURE_DIR"] = str(tmp_path / "pf")
    os.environ["OPENAI_PROMPT_LOG_DIR"] = str(tmp_path / "prompts")
    os.environ["OPENAI_RESPONSE_LOG_DIR"] = str(tmp_path / "responses")
    if "config" in sys.modules:
        importlib.reload(sys.modules["config"])
    if "scripts.analyze_artwork" in sys.modules:
        importlib.reload(sys.modules["scripts.analyze_artwork"])
    return importlib.import_module("scripts.analyze_artwork")


def dummy_resp(text):
    class C:
        def __init__(self, t):
            self.message = type("m", (), {"content": t})

    class R:
        def __init__(self, t):
            self.choices = [C(t)]

    return R(text)


SAMPLE_JSON = json.dumps(
    {
        "seo_filename": "test-artwork-by-robin-custance-rjc-9999.jpg",
        "title": "Test",
        "description": "desc" * 100,
        "tags": ["tag"],
        "materials": ["mat"],
        "primary_colour": "Black",
        "secondary_colour": "Brown",
        "price": 18.27,
        "sku": "RJC-9999",
    }
)


def test_markdown_wrapped_json(tmp_path):
    aa = setup_env(tmp_path)
    img = next((aa.ARTWORKS_DIR).rglob("*.jpg"))
    wrapped = "```json\n" + SAMPLE_JSON + "\n```"
    with mock.patch.object(aa.client.chat.completions, "create", return_value=dummy_resp(wrapped)):
        listing, raw, p_log, r_log, err = aa.generate_ai_listing(
            "prompt", img, "1x1", "RJC-9999"
        )
    assert listing and not err
    assert p_log.exists() and r_log.exists()


def test_retry_then_success(tmp_path):
    aa = setup_env(tmp_path)
    img = next((aa.ARTWORKS_DIR).rglob("*.jpg"))
    responses = [dummy_resp("not json"), dummy_resp(SAMPLE_JSON)]
    with mock.patch.object(aa.client.chat.completions, "create", side_effect=responses) as m:
        listing, raw, p_log, r_log, err = aa.generate_ai_listing(
            "prompt", img, "1x1", "RJC-9999"
        )
    assert listing and not err
    assert m.call_count == 2
    assert len(list((tmp_path / "responses").glob("*.txt"))) == 2


def test_failure_logged(tmp_path):
    aa = setup_env(tmp_path)
    img = next((aa.ARTWORKS_DIR).rglob("*.jpg"))
    with mock.patch.object(aa.client.chat.completions, "create", return_value=dummy_resp("bad")):
        listing, raw, p_log, r_log, err = aa.generate_ai_listing(
            "prompt", img, "1x1", "RJC-9999"
        )
    assert listing is None
    pf = list((tmp_path / "pf").glob("*.txt"))
    assert pf

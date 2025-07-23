from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from utils.logger_utils import log_action


def test_log_action_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    log_action("upload", "test.jpg", "alice", "uploaded test.jpg")
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H")
    log_file = tmp_path / "upload" / f"{stamp}.log"
    assert log_file.exists()
    text = log_file.read_text()
    assert "user: alice" in text
    assert "action: upload" in text
    assert "file: test.jpg" in text
    assert "status: success" in text


def test_log_action_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    log_action("upload", "bad.jpg", None, "failed", status="fail", error="oops")
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H")
    log_file = tmp_path / "upload" / f"{stamp}.log"
    lines = log_file.read_text().strip().splitlines()
    assert any("status: fail" in l for l in lines)
    assert any("error: oops" in l for l in lines)

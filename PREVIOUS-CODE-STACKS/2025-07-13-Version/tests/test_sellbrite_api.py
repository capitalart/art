import base64
import importlib
import os
import pytest

from utils.sellbrite_api import SellbriteAPI


def test_auth_header(monkeypatch):
    monkeypatch.setenv("SELLBRITE_TOKEN", "abc")
    monkeypatch.setenv("SELLBRITE_SECRET", "def")
    importlib.reload(importlib.import_module("utils.sellbrite_api"))
    api = SellbriteAPI()
    expected = base64.b64encode(b"abc:def").decode("utf-8")
    assert api._auth_header()["Authorization"] == f"Basic {expected}"


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("SELLBRITE_TOKEN", raising=False)
    monkeypatch.delenv("SELLBRITE_SECRET", raising=False)
    importlib.reload(importlib.import_module("utils.sellbrite_api"))
    with pytest.raises(RuntimeError):
        SellbriteAPI()

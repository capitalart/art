"""Sellbrite API helper class for product management."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv


class SellbriteAPI:
    """Wrapper around Sellbrite REST API."""

    def __init__(self, api_base: str | None = None) -> None:
        load_dotenv()
        self.token = os.getenv("SELLBRITE_TOKEN")
        self.secret = os.getenv("SELLBRITE_SECRET")
        if not self.token or not self.secret:
            raise RuntimeError("Sellbrite credentials not configured")
        self.api_base = api_base or os.getenv(
            "SELLBRITE_API_BASE", "https://api.sellbrite.com/v1"
        )
        self.session = requests.Session()
        self.session.headers.update(self._auth_header())
        self.logger = logging.getLogger(self.__class__.__name__)

    def _auth_header(self) -> Dict[str, str]:
        creds = f"{self.token}:{self.secret}".encode("utf-8")
        encoded = base64.b64encode(creds).decode("utf-8")
        return {"Authorization": f"Basic {encoded}"}

    def test_connection(self) -> bool:
        """Return True if credentials allow listing products."""
        url = f"{self.api_base}/products"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return True
            self.logger.error(
                "Sellbrite connection failed: %s %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as exc:  # pragma: no cover - network
            self.logger.error("Sellbrite request error: %s", exc)
            return False

    def create_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST a new product to Sellbrite and return the API response."""
        url = f"{self.api_base}/products"
        resp = self.session.post(url, json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def upload_image(self, product_id: str, image: Path) -> Dict[str, Any]:
        """Upload an image file for an existing product."""
        url = f"{self.api_base}/products/{product_id}/images"
        with open(image, "rb") as f:
            files = {"file": (image.name, f, "image/jpeg")}
            resp = self.session.post(url, files=files, timeout=10)
        resp.raise_for_status()
        return resp.json()

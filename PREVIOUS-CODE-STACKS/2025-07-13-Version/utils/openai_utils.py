"""Utility helpers for selecting the best available OpenAI model."""

from __future__ import annotations

import os
from openai import OpenAI
from config import (
    OPENAI_PRIMARY_MODEL,
    OPENAI_FALLBACK_MODEL,
    get_openai_model as config_get_openai_model,
)

# Use existing API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

_openai_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Return a cached OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def check_model_availability(model_name: str) -> bool:
    """Return True if the model can be retrieved via the API."""
    if not OPENAI_API_KEY:
        return False
    client = _get_client()
    try:
        client.models.retrieve(model_name)
        return True
    except Exception:
        return False


def get_openai_model() -> str:
    """Return the first available model from the configured fallback chain."""
    primary = OPENAI_PRIMARY_MODEL
    fallback = OPENAI_FALLBACK_MODEL

    chain = [primary]
    if fallback and fallback != primary:
        chain.append(fallback)
    if "gpt-4-turbo" not in chain:
        chain.append("gpt-4-turbo")

    for model in chain:
        if check_model_availability(model):
            return model
    # Final fallback if all checks fail
    return config_get_openai_model()

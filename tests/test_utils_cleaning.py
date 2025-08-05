# tests/test_utils_cleaning.py
import pytest
from routes import utils
# FIX (2025-08-05): Import validate_listing_fields from its new, correct location.
from routes.edit_listing_routes import validate_listing_fields
import config


def test_clean_terms():
    cleaned, changed = utils.clean_terms(["te-st", "b@d"])
    assert cleaned == ["test", "bd"]
    assert changed


def test_read_generic_text():
    txt = utils.read_generic_text("4x5")
    assert txt.strip() != ""


def test_validate_generic_error_message():
    generic = utils.read_generic_text("4x5")
    data = {
        "title": "t",
        "description": "short description",
        "tags": ["tag"],
        "materials": ["mat"],
        "primary_colour": "Black",
        "secondary_colour": "Brown",
        "seo_filename": "Test-Artwork-by-Robin-Custance-RJC-0001.jpg",
        "price": "17.88",
        "sku": "RJC-0001",
        "images": [str(config.FINALISED_ROOT / 'test' / 'test.jpg')],
    }
    errors = validate_listing_fields(data, generic)
    joined = " ".join(errors)
    assert "correct generic context block" in joined


def test_validate_generic_present_with_whitespace():
    generic = utils.read_generic_text("4x5")
    base = "word " * 400
    desc = base + "\n\n" + generic + "\n   extra words after"
    data = {
        "title": "t",
        "description": desc,
        "tags": ["tag"],
        "materials": ["mat"],
        "primary_colour": "Black",
        "secondary_colour": "Brown",
        "seo_filename": "Test-Artwork-by-Robin-Custance-RJC-0001.jpg",
        "price": "18.27",
        "sku": "RJC-0001",
        "images": [str(config.FINALISED_ROOT / 'test' / 'test.jpg')],
    }
    errors = validate_listing_fields(data, generic)
    assert "correct generic context block" not in " ".join(errors)
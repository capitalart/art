# routes/sellbrite_export.py
from __future__ import annotations
"""
Utilities for exporting listings to Sellbrite.

This module contains the helper function for generating a JSON payload
formatted specifically for the Sellbrite Listings API.

INDEX
-----
1.  Imports
2.  JSON Generation Function
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from typing import Any, Dict
import config


# ===========================================================================
# 2. JSON Generation Function
# ===========================================================================
def generate_sellbrite_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a dictionary formatted for the Sellbrite Listings API.

    This function takes an artwork's listing data, constructs absolute image
    URLs using the configured BASE_URL, and maps the fields to what the
    Sellbrite API expects, including a default quantity.

    Args:
        data: A dictionary containing the artwork listing information.

    Returns:
        A dictionary formatted for the Sellbrite API.
    """
    # Construct the public base URL for images from config
    base_url = config.BASE_URL
    
    relative_image_paths = data.get("images", [])
    
    # Convert relative paths from the project root to full, public URLs
    absolute_image_urls = [f"{base_url}/{path}" for path in relative_image_paths]

    sb = {
        "sku": data.get("sku"),
        "name": data.get("title"),
        "description": data.get("description"),
        "price": data.get("price"),
        "quantity": config.SELLBRITE_DEFAULTS["QUANTITY"],
        "tags": data.get("tags", []),
        "materials": data.get("materials", []),
        "primary_colour": data.get("primary_colour"),
        "secondary_colour": data.get("secondary_colour"),
        "seo_filename": data.get("seo_filename"),
        "images": absolute_image_urls,
    }
    # Clean out any empty or None fields before sending to the API
    return {k: v for k, v in sb.items() if v not in (None, "", [])}
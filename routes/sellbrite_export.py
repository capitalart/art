"""Utilities for exporting listings to Sellbrite.

Field mapping between our artwork JSON and Sellbrite's Listings API:

| JSON field       | Sellbrite field |
|------------------|-----------------|
| title            | name            |
| description      | description     |
| tags             | tags            |
| materials        | materials       |
| primary_colour   | primary_colour  |
| secondary_colour | secondary_colour|
| seo_filename     | seo_filename    |
| sku              | sku             |
| price            | price           |
| images           | images          |
"""

# routes/sellbrite_export.py
"""
Utilities for exporting listings to Sellbrite.
"""

from __future__ import annotations
from typing import Any, Dict
import config


def generate_sellbrite_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dictionary formatted for the Sellbrite Listings API with absolute image URLs."""
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
        "quantity": 25, # <-- MODIFIED: Added default quantity
        "tags": data.get("tags", []),
        "materials": data.get("materials", []),
        "primary_colour": data.get("primary_colour"),
        "secondary_colour": data.get("secondary_colour"),
        "seo_filename": data.get("seo_filename"),
        "images": absolute_image_urls,
    }
    # Clean out any empty fields before sending
    return {k: v for k, v in sb.items() if v not in (None, "", [])}
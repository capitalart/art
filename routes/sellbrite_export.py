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

from __future__ import annotations

from typing import Any, Dict
import config


def generate_sellbrite_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dictionary formatted for the Sellbrite Listings API with absolute image URLs."""
    # Construct the base URL for public images from config [cite: 753]
    base_url = f"https://{config.BRAND_DOMAIN}"
    
    # Get relative image paths from the listing data
    relative_image_paths = data.get("images", [])
    
    # Convert relative paths to full, public URLs
    # The static URL path is the relative path prefixed with '/static/'
    absolute_image_urls = [f"{base_url}/static/{path}" for path in relative_image_paths]

    sb = {
        "sku": data.get("sku"),
        "name": data.get("title"),
        "description": data.get("description"),
        "price": data.get("price"),
        "tags": data.get("tags", []),
        "materials": data.get("materials", []),
        "primary_colour": data.get("primary_colour"),
        "secondary_colour": data.get("secondary_colour"),
        "seo_filename": data.get("seo_filename"),
        "images": absolute_image_urls,  # Use the new absolute URLs
    }
    return {k: v for k, v in sb.items() if v not in (None, "", [])}
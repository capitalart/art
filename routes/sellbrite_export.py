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


def generate_sellbrite_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dictionary formatted for the Sellbrite Listings API."""
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
        "images": data.get("images", []),
    }
    return {k: v for k, v in sb.items() if v not in (None, "", [])}

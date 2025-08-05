# app_utils.py
"""
Application-level utility functions, especially those needed by templates.

This module contains helpers that require access to the Flask application
context (like `url_for`) and are made available globally to all Jinja
templates via a context processor in `app.py`.
"""
from __future__ import annotations
import logging
from flask import url_for
import config

logger = logging.getLogger(__name__)

def get_artwork_image_url(artwork_status: str, filename: str) -> str:
    """
    Generates a fail-safe public URL for an artwork image based on its status.

    Args:
        artwork_status: The status of the artwork (e.g., 'processed', 'finalised', 'locked').
        filename: The relative path of the file from its stage root (e.g., 'folder/image.jpg').

    Returns:
        A correct, publicly accessible URL string.
    """
    endpoint = ''
    if artwork_status == 'locked':
        endpoint = 'artwork.locked_image'
    elif artwork_status == 'finalised':
        endpoint = 'artwork.finalised_image'
    else: # Default to 'processed'
        endpoint = 'artwork.processed_image'
    
    try:
        # Mockup thumbnails have their own special route because they are in a sub-folder
        if config.THUMB_SUBDIR in filename and "-MU-" in filename:
            endpoint = 'artwork.serve_mockup_thumb'
            return url_for(endpoint, filepath=filename)

        return url_for(endpoint, filename=filename)
    except Exception as e:
        logger.error(f"Could not generate URL for endpoint '{endpoint}' with filename '{filename}': {e}")
        return "#" # Return a dead link on error
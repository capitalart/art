# routes/test_routes.py
"""
Flask routes for rendering experimental or test templates.

This blueprint is used for development and testing purposes, allowing new
UI components or page layouts to be viewed in isolation before being
integrated into the main application.

INDEX
-----
1.  Imports
2.  Blueprint Setup
3.  Test Routes
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
from flask import Blueprint, render_template

# ===========================================================================
# 2. Blueprint Setup
# ===========================================================================
test_bp = Blueprint('test_bp', __name__)


# ===========================================================================
# 3. Test Routes
# ===========================================================================

@test_bp.route('/overlay-test')
def overlay_test():
    """Renders a test page for the main overlay menu design."""
    return render_template('codex-library/Overlay-Menu-Design-Template/main-design-template.html')


@test_bp.route('/test/edit-listing')
def edit_listing_test():
    """Renders an overlay test version of the edit listing template."""
    return render_template('edit_listing_overlay_test.html')


@test_bp.route('/test/artworks')
def artworks_test():
    """Renders an overlay test version of the artworks template."""
    return render_template('artworks_overlay_test.html')
from flask import Blueprint, render_template

# Blueprint for overlay migration testing
test_bp = Blueprint('test_bp', __name__)

@test_bp.route('/overlay-test')
def overlay_test():
    return render_template('codex-library/Overlay-Menu-Design-Template/main-design-template.html')


# Route to view edit listing overlay test template
@test_bp.route('/test/edit-listing')
def edit_listing_test():
    """Render overlay version of edit listing template."""
    return render_template('edit_listing_overlay_test.html')


# Route to view artworks overlay test template
@test_bp.route('/test/artworks')
def artworks_test():
    """Render overlay version of artworks template."""
    return render_template('artworks_overlay_test.html')

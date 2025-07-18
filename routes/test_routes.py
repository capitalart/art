from flask import Blueprint, render_template

test_bp = Blueprint('test_bp', __name__)

@test_bp.route('/overlay-test')
def overlay_test():
    return render_template('codex-library/Overlay-Menu-Design-Template/main-design-template.html')

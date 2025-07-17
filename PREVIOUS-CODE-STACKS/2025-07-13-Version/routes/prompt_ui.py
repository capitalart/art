"""UI route for manual prompt generation."""

from flask import Blueprint, render_template
from routes import utils

bp = Blueprint('prompt_ui', __name__)

@bp.route('/prompt-generator')
def prompt_generator():
    """Render the simple prompt generator UI."""
    return render_template('prompt_generator.html', menu=utils.get_menu())

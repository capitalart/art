
"""API endpoints for retrieving AI prompt option values."""

from __future__ import annotations

import json
from pathlib import Path
from flask import Blueprint, jsonify, abort

OPTIONS_DIR = Path('config/ai_prompt_options')

bp = Blueprint('prompt_options', __name__, url_prefix='/api')

@bp.route('/prompt-options/<category>')
def get_prompt_options(category: str):
    """Return JSON list of prompt options for the given category."""
    file = OPTIONS_DIR / f'{category}.json'
    if file.is_file():
        with open(file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
        return jsonify(data)
    return jsonify([])


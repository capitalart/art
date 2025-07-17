"""Admin interface for the Guided Description Writing System (GDWS)."""

from flask import Blueprint, render_template, request, jsonify
import json
import os
import random
import re
from pathlib import Path
import shutil
from datetime import datetime

from config import BASE_DIR
from routes.utils import get_menu
from utils.ai_services import call_ai_to_rewrite  # We will create this module next

GDWS_CONTENT_PATH = BASE_DIR / "gdws_content"

bp = Blueprint("gdws_admin", __name__, url_prefix="/admin/gdws")

def slugify(text):
    """A simple function to create a filesystem-safe name."""
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)


def get_paragraph_folders(aspect: str) -> list[str]:
    """Return paragraph type folders for an aspect ratio."""
    aspect_path = GDWS_CONTENT_PATH / aspect
    if not aspect_path.exists():
        return []
    return [p.name for p in aspect_path.iterdir() if p.is_dir()]


@bp.route("/")
def editor():
    """Renders the main GDWS editor page."""
    return render_template("dws_editor.html", menu=get_menu())


@bp.route("/base-editor")
def base_editor():
    """Simple page to edit base paragraph text."""
    return render_template("gdws_base_editor.html", menu=get_menu())


@bp.route("/template/<aspect_ratio>")
def get_template_data(aspect_ratio):
    """
    Fetches a set of paragraphs for a given aspect ratio template.
    This simulates the final assembly process for preview in the editor.
    """
    # Note: In this new model, aspect ratio might just define which paragraph
    # types to load, or it might load a base template that you can edit.
    # For now, we'll load one random variation from each folder.

    all_blocks = []
    paragraph_folders = get_paragraph_folders(aspect_ratio)

    aspect_path = GDWS_CONTENT_PATH / aspect_ratio
    for folder_name in paragraph_folders:
        folder_path = aspect_path / folder_name
        variations = list(folder_path.glob("*.json"))
        if variations:
            random_variation_path = random.choice(variations)
            with open(random_variation_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data.setdefault('deletable', True)
            data.setdefault('pinned', False)
            all_blocks.append(data)

    # You can add logic here for pinned blocks etc.
    # This is a simplified example.
    return jsonify({"templateId": aspect_ratio, "blocks": all_blocks})


@bp.route("/regenerate-paragraph", methods=['POST'])
def regenerate_paragraph():
    """Handles AI regeneration for a single paragraph."""
    data = request.json
    prompt = (
        f"Instruction: \"{data.get('instructions', '')}\"\n"
        f"Base Text to refer to: \"{data.get('base_text', '')}\"\n"
        f"Current Text to rewrite: \"{data.get('current_text', '')}\""
    )

    new_text = call_ai_to_rewrite(
        prompt,
        provider=data.get('ai_provider', 'openai')
    )

    return jsonify({"new_content": new_text})


@bp.route("/save-paragraph", methods=['POST'])
def save_paragraph():
    """Saves a single paragraph variation to a JSON file."""
    data = request.json
    title = data.get('title')
    content = data.get('content')

    # The folder name is derived from the title
    folder_name = slugify(title)
    folder_path = GDWS_CONTENT_PATH / folder_name
    folder_path.mkdir(exist_ok=True)

    # Create a unique filename for this variation
    variation_id = data.get('id', f"var_{int(datetime.now().timestamp())}")
    file_path = folder_path / f"{variation_id}.json"

    save_data = {
        "id": variation_id,
        "title": title,
        "content": content,
        "version": "1.0",
        "last_updated": datetime.now().isoformat()
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=4)

    return jsonify({"status": "success", "message": f"Saved {file_path}", "new_id": variation_id})


@bp.route("/rename-paragraph-type", methods=['POST'])
def rename_paragraph_type():
    """Renames a paragraph folder when a title is changed."""
    data = request.json
    old_title = data.get('old_title')
    new_title = data.get('new_title')

    old_folder_name = slugify(old_title)
    new_folder_name = slugify(new_title)

    old_path = GDWS_CONTENT_PATH / old_folder_name
    new_path = GDWS_CONTENT_PATH / new_folder_name

    if not old_path.exists():
        return jsonify({"status": "error", "message": "Original folder not found."}), 404

    if new_path.exists():
        return jsonify({"status": "error", "message": "A paragraph type with that name already exists."}), 400

    shutil.move(str(old_path), str(new_path))

    return jsonify({"status": "success", "message": f"Renamed folder to {new_folder_name}"})


@bp.route("/save-base-paragraph", methods=['POST'])
def save_base_paragraph():
    """Save edits to the base text and instructions."""
    data = request.json
    file_path = Path(data.get('file'))
    if not file_path.is_file():
        return jsonify({"status": "error", "message": "File not found"}), 404
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    except Exception:
        existing = {}
    existing.update({
        "base_text": data.get('base_text', existing.get('base_text', '')),
        "base_instructions": data.get('base_instructions', existing.get('base_instructions', '')),
    })
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2)
    return jsonify({"status": "success"})


@bp.route('/email-templates')
def email_templates():
    """Placeholder page for email templates."""
    return render_template('templates_components/email_templates.html', menu=get_menu())


@bp.route('/listing-templates')
def listing_templates():
    """Placeholder page for listing templates."""
    return render_template('templates_components/listing_templates.html', menu=get_menu())

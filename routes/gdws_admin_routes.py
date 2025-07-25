"""Admin interface for the Guided Description Writing System (GDWS)."""

from flask import Blueprint, render_template, request, jsonify
import json
import random
import re
from pathlib import Path
import shutil
from datetime import datetime

from config import GDWS_CONTENT_DIR
from routes.utils import get_menu
from utils.ai_services import call_ai_to_rewrite, call_ai_to_generate_title

GDWS_CONTENT_PATH = GDWS_CONTENT_DIR

bp = Blueprint("gdws_admin", __name__, url_prefix="/admin/gdws")

# Define which paragraph titles are pinned to the start or end
PINNED_START_TITLES = [
    "About the Artist – Robin Custance",
    "Did You Know? Aboriginal Art & the Spirit of Dot Painting",
    "What You’ll Receive",
    "WHY YOU’LL LOVE THIS ARTWORK",
    "HOW TO BUY & PRINT",
]
PINNED_END_TITLES = [
    "THANK YOU – FROM MY STUDIO TO YOUR HOME",
    "Thank You & Stay Connected",
]

def slugify(text):
    """A simple function to create a filesystem-safe name."""
    s = text.lower()
    s = re.sub(r'[^\w\s-]', '', s).strip()
    s = re.sub(r'[-\s]+', '_', s)
    if "about_the_artist" in s: return "about_the_artist"
    if "did_you_know" in s: return "about_art_style"
    if "what_youll_receive" in s: return "file_details"
    return s

def get_aspect_ratios() -> list[str]:
    """Return a list of available aspect ratio folders."""
    if not GDWS_CONTENT_PATH.exists(): return []
    return sorted([p.name for p in GDWS_CONTENT_PATH.iterdir() if p.is_dir()])

@bp.route("/")
def editor():
    """Renders the main GDWS editor page with available aspect ratios."""
    return render_template(
        "dws_editor.html",
        menu=get_menu(),
        aspect_ratios=get_aspect_ratios(),
        PINNED_START_TITLES=PINNED_START_TITLES,
        PINNED_END_TITLES=PINNED_END_TITLES,
    )

@bp.route("/template/<aspect_ratio>")
def get_template_data(aspect_ratio):
    """Fetches and sorts paragraphs based on saved order and pinned status."""
    aspect_path = GDWS_CONTENT_PATH / aspect_ratio
    if not aspect_path.exists():
        return jsonify({"error": "Aspect ratio not found"}), 404

    all_blocks = {}
    for folder_path in [p for p in aspect_path.iterdir() if p.is_dir()]:
        base_file = folder_path / "base.json"
        if base_file.exists():
            try:
                with open(base_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_blocks[data['title']] = data
            except Exception as e:
                print(f"Error loading {base_file}: {e}")

    start_blocks = [all_blocks.pop(title) for title in PINNED_START_TITLES if title in all_blocks]
    end_blocks = [all_blocks.pop(title) for title in PINNED_END_TITLES if title in all_blocks]
    middle_blocks_dict = all_blocks

    order_file = aspect_path / "order.json"
    sorted_middle_blocks = []
    if order_file.exists():
        with open(order_file, 'r', encoding='utf-8') as f:
            order = json.load(f)
        for title in order:
            if title in middle_blocks_dict:
                sorted_middle_blocks.append(middle_blocks_dict.pop(title))
    
    sorted_middle_blocks.extend(middle_blocks_dict.values())

    return jsonify({"blocks": start_blocks + sorted_middle_blocks + end_blocks})

@bp.route("/save-order", methods=['POST'])
def save_order():
    """Saves the new order of the middle paragraphs."""
    data = request.json
    aspect_ratio = data.get('aspect_ratio')
    order = data.get('order')

    if not aspect_ratio or order is None:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    order_file = GDWS_CONTENT_PATH / aspect_ratio / "order.json"
    with open(order_file, 'w', encoding='utf-8') as f:
        json.dump(order, f, indent=2)
    
    return jsonify({"status": "success", "message": "Order saved."})

@bp.route("/regenerate-title", methods=['POST'])
def regenerate_title():
    """Handles AI regeneration for a paragraph title."""
    data = request.json
    content = data.get('content', '')
    new_title = call_ai_to_generate_title(content)
    return jsonify({"new_title": new_title})

@bp.route("/regenerate-paragraph", methods=['POST'])
def regenerate_paragraph():
    """Handles AI regeneration for a single paragraph."""
    data = request.json
    prompt = (
        f"Instruction: \"{data.get('instructions', '')}\"\n\n"
        f"Rewrite the following text based on the instruction. Respond only with the rewritten text.\n\n"
        f"TEXT TO REWRITE:\n\"{data.get('current_text', '')}\""
    )
    new_text = call_ai_to_rewrite(prompt)
    return jsonify({"new_content": new_text})

@bp.route("/save-paragraph-version", methods=['POST'])
def save_paragraph_version():
    """Saves a new paragraph variation, not overwriting the base."""
    data = request.json
    aspect_ratio = data.get('aspect_ratio')
    title = data.get('title')
    content = data.get('content')
    
    if not all([aspect_ratio, title, content]):
        return jsonify({"status": "error", "message": "Missing data."}), 400

    folder_name = slugify(title)
    folder_path = GDWS_CONTENT_PATH / aspect_ratio / folder_name
    folder_path.mkdir(exist_ok=True)

    variation_id = f"var_{int(datetime.now().timestamp() * 1000)}"
    file_path = folder_path / f"{variation_id}.json"

    save_data = {
        "id": variation_id,
        "title": title,
        "content": content,
        "instructions": data.get('instructions', ''),
        "version": "1.1", # Signifies it's a variation
        "last_updated": datetime.now().isoformat()
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=4)

    return jsonify({"status": "success", "message": f"Saved new variation {file_path}", "new_id": variation_id})

@bp.route("/save-base-paragraph", methods=['POST'])
def save_base_paragraph():
    """Saves edits to a base.json file, handling potential renames."""
    data = request.json
    aspect_ratio = data.get('aspect_ratio')
    original_title = data.get('original_title')
    new_title = data.get('new_title')
    
    if not all([aspect_ratio, original_title, new_title]):
        return jsonify({"status": "error", "message": "Missing data."}), 400

    original_slug = slugify(original_title)
    new_slug = slugify(new_title)
    
    original_folder = GDWS_CONTENT_PATH / aspect_ratio / original_slug
    target_folder = GDWS_CONTENT_PATH / aspect_ratio / new_slug
    
    if original_slug != new_slug:
        if target_folder.exists():
            return jsonify({"status": "error", "message": "A paragraph with that name already exists."}), 400
        if not original_folder.exists():
            return jsonify({"status": "error", "message": "Original paragraph folder not found."}), 404
        original_folder.rename(target_folder)

    file_path = target_folder / "base.json"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    except Exception:
        existing_data = {"id": "base"}

    existing_data['title'] = new_title
    existing_data['content'] = data.get('content', existing_data.get('content', ''))
    existing_data['instructions'] = data.get('instructions', existing_data.get('instructions', ''))
    existing_data['last_updated'] = datetime.now().isoformat()
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=4)
        
    return jsonify({"status": "success", "message": f"Updated {file_path}", "new_slug": new_slug})
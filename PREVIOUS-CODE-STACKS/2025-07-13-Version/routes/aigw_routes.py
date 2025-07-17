"""Routes for the AI Image Generator Whisperer (AIGW) tool."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash

import config
from routes import utils

# --- SECTION: Blueprint setup ---

bp = Blueprint("aigw", __name__, url_prefix="/aigw")

OPTIONS_FILE = config.AIGW_OPTIONS_FILE
PROMPTS_DIR = config.AIGW_PROMPTS_DIR
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

# --- SECTION: Helper functions ---

def _load_options() -> dict:
    """Return selector options from JSON or defaults."""
    if OPTIONS_FILE.exists():
        try:
            with open(OPTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "genre": [
            "Abstract",
            "Landscape",
            "Portrait",
            "Still Life",
            "Wildlife",
            "Cityscape",
            "Fantasy",
            "Surrealism",
            "Conceptual",
            "Minimalism",
        ],
        "style": [
            "Impressionism",
            "Expressionism",
            "Pop Art",
            "Realism",
            "Cubism",
            "Fauvism",
            "Art Nouveau",
            "Modernism",
            "Traditional Aboriginal Dot Art",
            "Street Art",
        ],
        "technique": [
            "Brushwork",
            "Stippling",
            "Impasto",
            "Sgraffito",
            "Crosshatching",
            "Glazing",
            "Splattering",
            "Digital Blending",
            "Spray Painting",
            "Collage",
        ],
        "medium": [
            "Oil Paint",
            "Acrylic",
            "Watercolour",
            "Ink",
            "Digital (Tablet/Procreate)",
            "Pastel",
            "Charcoal",
            "Mixed Media",
            "Gouache",
            "Spray Paint",
        ],
        "colour_palette": [
            "Earth Tones",
            "Pastels",
            "Monochrome",
            "Vibrant Rainbow",
            "Cool Blues/Greens",
            "Warm Reds/Yellows",
            "Muted Neutrals",
            "Black & White",
            "High Contrast",
            "Outback Ochres",
        ],
        "texture": [
            "Smooth",
            "Rough",
            "Matte",
            "Glossy",
            "Thick Impasto",
            "Fine Detail",
            "Weathered",
            "Layered",
            "Textured Paper/Canvas",
            "Iridescent",
        ],
        "lighting": [
            "Golden Hour",
            "Backlit",
            "Soft Ambient",
            "Dramatic Shadows",
            "Spotlit",
            "Neon Glow",
            "Overcast",
            "Studio",
            "Candlelit",
            "Moody Rim",
        ],
        "mood": [
            "Nostalgic",
            "Adventurous",
            "Mysterious",
            "Whimsical",
            "Serene",
            "Energetic",
            "Melancholic",
            "Triumphant",
            "Romantic",
            "Contemplative",
        ],
        "perspective": [
            "Bird's Eye",
            "Worm's Eye",
            "Eye-Level",
            "Dutch Angle",
            "Isometric",
            "Macro",
            "Wide Shot",
            "Close Up",
            "Tilt Shift",
            "Panoramic",
        ],
        "era": [
            "Contemporary",
            "Retro 80s",
            "Classical",
            "Future",
            "Renaissance",
            "Victorian",
            "Postmodern",
            "Ancient",
            "Roaring 20s",
            "Space Age",
        ],
        "format": [
            "4x5",
            "1x1",
            "16x9",
            "3x4",
            "4x3",
            "5x7",
            "7x5",
            "A-Series-Vertical",
            "A-Series-Horizontal",
            "Panoramic",
        ],
        "focal_point": [
            "Foreground",
            "Background",
            "Centered",
            "Off-center",
            "Left Third",
            "Right Third",
            "Symmetrical",
            "Rule of Thirds",
            "Golden Ratio",
            "Diagonal",
        ],
    }


def _save_prompt(data: dict) -> None:
    """Save prompt data to a JSON file."""
    file_path = PROMPTS_DIR / f"{data['id']}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# --- SECTION: Main editor route ---

@bp.route("/", methods=["GET", "POST"], endpoint="editor")
def editor():
    """Render the prompt builder and handle saves."""
    options = _load_options()
    if request.method == "POST":
        data = {k: request.form.get(k, "") for k in options.keys()}
        data["prompt"] = request.form.get("prompt", "")
        data["id"] = uuid.uuid4().hex
        _save_prompt(data)
        flash("Prompt saved", "success")
        return redirect(url_for("aigw.editor"))
    return render_template(
        "aigw.html", menu=utils.get_menu(), options=options
    )


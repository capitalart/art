"""Blueprint for AI Image Prompt Whisperer."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, session
from openai import OpenAI

bp = Blueprint("whisperer", __name__, url_prefix="/prompt-whisperer")

DATA_DIR = Path("descriptions")
PROMPT_SAVE_DIR = Path("prompts")
CATEGORY_FILE = Path("static/data/art_categories.json")

client = OpenAI()

SENTIMENTS = [
    "Joyful",
    "Melancholic",
    "Mystical",
    "Peaceful",
    "Dynamic",
    "Playful",
    "Majestic",
    "Uplifting",
    "Ethereal",
    "Dramatic",
]


def load_categories() -> list[str]:
    """Load list of art categories from disk."""
    try:
        with open(CATEGORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@bp.route("/")
def index() -> str:
    """Render the main Prompt Whisperer page."""
    last_prompt = session.get("last_prompt", "")
    cats = load_categories()
    return render_template(
        "prompt_whisperer.html",
        prompt=last_prompt,
        categories=cats,
        sentiments=SENTIMENTS,
    )


@bp.post("/generate")
def generate() -> "json":
    """Generate a new prompt using OpenAI."""
    data = request.get_json() or {}
    instructions = data.get("instructions", "")
    word_count = int(data.get("word_count", 40))
    category = data.get("category", "")
    randomness = int(data.get("randomness", 40))
    sentiment = data.get("sentiment", "Mystical")

    try:
        with open(DATA_DIR / "artworks.json", "r", encoding="utf-8") as f:
            trending = json.load(f)
    except Exception:
        trending = []
    trending_desc = "; ".join(a.get("description", "") for a in trending[:3])

    sys_msg = (
        "You are an AI prompt whisperer helping artists craft unique image prompts."
    )
    user_msg = (
        f"Create a {word_count}-word prompt in a {sentiment.lower()} tone. "
        f"Category suggestion: {category}. "
        f"Trending inspirations: {trending_desc}. "
        f"{instructions}"
    )
    temp = max(0.0, min(1.0, randomness / 100))
    try:
        resp = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            max_tokens=word_count * 2,
            temperature=temp,
        )
        prompt = resp.choices[0].message.content.strip()
    except Exception as exc:  # pragma: no cover - network failure
        prompt = f"Error generating prompt: {exc}"

    session["last_prompt"] = prompt
    return jsonify({"prompt": prompt, "category": category})


@bp.post("/save")
def save_prompt() -> "json":
    """Persist a generated prompt for later reference."""
    data = request.get_json() or {}
    prompt = data.get("prompt", "")
    category = data.get("category", "Uncategorised")
    info = {
        "prompt": prompt,
        "instructions": data.get("instructions", ""),
        "word_count": int(data.get("word_count", 0)),
        "randomness": int(data.get("randomness", 0)),
        "sentiment": data.get("sentiment", ""),
        "timestamp": datetime.utcnow().isoformat(),
    }
    dest = PROMPT_SAVE_DIR / category
    dest.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    with open(dest / f"{ts}.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    return jsonify({"saved": True})

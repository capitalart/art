"""Mockup upload and categorisation UI."""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import uuid
import datetime
from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    abort,
    session,
    send_from_directory,
    flash,
)
from openai import OpenAI
from utils.openai_utils import get_openai_model

import config
from . import utils

bp = Blueprint("mockups", __name__, url_prefix="/mockups")

client = OpenAI(api_key=config.OPENAI_API_KEY)


def _encode_image(path: Path) -> str:
    """Return base64 string for an image file."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _analyse_mockup(image_path: Path, categories: list[str]) -> tuple[str, str]:
    """Return (category, description) from OpenAI."""
    system_prompt = (
        "You help organise mockup preview images for digital artwork. "
        "Classify the image into one of these categories:\n"
        f"{', '.join(categories)}\n"
        "Return only the category name."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{_encode_image(image_path)}"},
                }
            ],
        },
    ]
    try:
        resp = client.chat.completions.create(model=get_openai_model(), messages=messages, max_tokens=20, temperature=0)
        cat = resp.choices[0].message.content.strip()
        if cat not in categories:
            cat = "Uncategorised"
    except Exception:
        cat = "Uncategorised"

    desc_prompt = (
        "Describe the mockup style, mood and room context in one short professional sentence."
    )
    try:
        dresp = client.chat.completions.create(
            model=get_openai_model(),
            messages=[{"role": "system", "content": desc_prompt}, {"role": "user", "content": {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_encode_image(image_path)}"}}}],
            max_tokens=60,
            temperature=0.3,
        )
        desc = dresp.choices[0].message.content.strip()
    except Exception:
        desc = ""
    return cat, desc


def _run_coords(image_path: Path, output_path: Path) -> None:
    """Generate perspective coordinates for a mockup image."""
    script = config.SCRIPTS_DIR / "generate_mockup_coords.py"
    subprocess.run(["python", str(script), str(image_path), str(output_path)], check=True)


@bp.route("/")
def index():
    """List available aspect ratios for mockup images."""
    aspects = utils.get_aspect_ratios()
    return render_template("mockups/index.html", aspects=aspects, menu=utils.get_menu())


@bp.route("/upload", methods=["GET", "POST"])
def upload():
    """Upload new mockup images and categorise via AI."""
    if session.get("role") != "admin":
        abort(403)
    aspects = utils.get_aspect_ratios()
    if request.method == "POST":
        aspect = request.form.get("aspect")
        files = request.files.getlist("images")
        dest_uncat = config.MOCKUPS_INPUT_DIR / aspect / "uncategorised"
        dest_uncat.mkdir(parents=True, exist_ok=True)
        cat_base = config.MOCKUPS_INPUT_DIR / f"{aspect}-categorised"
        results = []
        for f in files:
            filename = f.filename or f"upload-{uuid.uuid4().hex}.png"
            temp_path = dest_uncat / filename
            f.save(temp_path)
            categories = utils.get_categories_for_aspect(aspect)
            if not categories:
                categories = ["Uncategorised"]
            ai_cat, desc = _analyse_mockup(temp_path, categories)
            dest_dir = cat_base / ai_cat
            dest_dir.mkdir(parents=True, exist_ok=True)
            final_path = dest_dir / filename
            shutil.move(temp_path, final_path)
            coords_file = dest_dir / f"{final_path.stem}.coords.json"
            _run_coords(final_path, coords_file)
            meta = {
                "filename": final_path.name,
                "aspect": aspect,
                "category": ai_cat,
                "ai_category": ai_cat,
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "original": filename,
                "description": desc,
                "coords": coords_file.name,
            }
            with open(dest_dir / f"{final_path.stem}.json", "w", encoding="utf-8") as mf:
                json.dump(meta, mf, indent=2)
            utils.log_mockup_action("upload", session.get("user", "?"), f"{aspect}/{ai_cat}/{filename}")
            results.append(meta)
        flash(f"Uploaded {len(results)} mockup(s)", "success")
        return redirect(url_for("mockups.gallery", aspect=aspect))
    return render_template("mockups/upload.html", aspects=aspects, menu=utils.get_menu())


@bp.route("/gallery/<aspect>")
def gallery(aspect):
    """Show categories for a given aspect ratio."""
    cats = utils.get_categories_for_aspect(aspect)
    items = []
    base = config.MOCKUPS_INPUT_DIR / f"{aspect}-categorised"
    for c in cats:
        count = len(list((base / c).glob("*.png")))
        items.append({"name": c, "count": count})
    return render_template("mockups/gallery.html", aspect=aspect, categories=items, menu=utils.get_menu())


@bp.route("/gallery/<aspect>/<category>")
def category_gallery(aspect, category):
    """Display all mockups inside a category."""
    folder = config.MOCKUPS_INPUT_DIR / f"{aspect}-categorised" / category
    images = sorted(p.name for p in folder.glob("*.png"))
    return render_template("mockups/category_gallery.html", aspect=aspect, category=category, images=images, menu=utils.get_menu())


@bp.route("/img/<aspect>/<category>/<filename>")
def image(aspect, category, filename):
    """Serve a raw mockup image file."""
    folder = config.MOCKUPS_INPUT_DIR / f"{aspect}-categorised" / category
    return send_from_directory(folder, filename)


@bp.route("/detail/<aspect>/<category>/<filename>", methods=["GET", "POST"])
def detail(aspect: str, category: str, filename: str):
    """View and edit metadata for a specific mockup."""
    folder = config.MOCKUPS_INPUT_DIR / f"{aspect}-categorised" / category
    meta_path = folder / f"{Path(filename).stem}.json"
    if not meta_path.exists():
        abort(404)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            os.remove(folder / filename)
            os.remove(meta_path)
            coords = folder / meta.get("coords", "")
            if coords.exists():
                coords.unlink()
            utils.log_mockup_action("delete", session.get("user", "?"), f"{aspect}/{category}/{filename}")
            flash("Deleted", "success")
            return redirect(url_for("mockups.category_gallery", aspect=aspect, category=category))
        meta["category"] = request.form.get("category", meta.get("category"))
        meta["description"] = request.form.get("description", meta.get("description"))
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        utils.log_mockup_action("edit", session.get("user", "?"), f"{aspect}/{category}/{filename}")
        flash("Saved", "success")
    categories = utils.get_categories_for_aspect(aspect)
    return render_template("mockups/detail.html", meta=meta, categories=categories, menu=utils.get_menu())



@bp.route('/review')
def review():
    """Placeholder page for reviewing mockups."""
    return render_template('mockups/review.html', menu=utils.get_menu())


@bp.route('/categories')
def categories():
    """Placeholder page for mockup categories."""
    return render_template('mockups/categories.html', menu=utils.get_menu())

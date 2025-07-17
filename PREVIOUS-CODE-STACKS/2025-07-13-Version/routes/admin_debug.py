
"""Debug and administration endpoints used during development.

These routes expose helper pages for inspecting AI parse output, viewing
application status and peeking at SKU sequencing. They are not secured
and should only be enabled in development environments.
"""

from __future__ import annotations

import datetime
import json

from flask import Blueprint, request, render_template, Response

import config
from routes import utils
from utils.sku_assigner import peek_next_sku
from scripts.analyze_artwork import parse_text_fallback

bp = Blueprint("admin", __name__, url_prefix="/admin")
# TODO: Protect admin debug routes with authentication/authorization


@bp.route("/debug/parse-ai", methods=["GET", "POST"])
def parse_ai():
    """Manually parse AI output or saved failures for debugging.

    This route allows pasting raw JSON or selecting a previously failed parse
    file. It attempts to load JSON and falls back to the older text parser on
    failure.
    """
    raw = ""
    parsed = None
    error = ""
    file_name = request.args.get("file")
    if file_name:
        path = config.PARSE_FAILURE_DIR / file_name
        if path.exists():
            raw = path.read_text(encoding="utf-8")
    if request.method == "POST":
        raw = request.form.get("raw", "")
        try:
            parsed = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            try:
                parsed = parse_text_fallback(raw)
                error = f"Input was not valid JSON: {exc}"
            except Exception as inner:  # noqa: BLE001
                error = f"Parse failed: {inner}"
                config.PARSE_FAILURE_DIR.mkdir(parents=True, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                fail_file = config.PARSE_FAILURE_DIR / f"parse_fail_{ts}.txt"
                fail_file.write_text(raw, encoding="utf-8")
    return render_template(
        "debug_parse_ai.html",
        raw=raw,
        parsed=parsed,
        error=error,
        menu=utils.get_menu(),
    )


@bp.route("/debug/next-sku")
def preview_next_sku_admin():
    """Return the next SKU value without reserving it."""
    return Response(peek_next_sku(config.SKU_TRACKER), mimetype="text/plain")


@bp.route("/debug/status")
def debug_status():
    """Display simple environment diagnostic information."""
    info = {
        "openai_key": bool(config.OPENAI_API_KEY),
        "processed_dir": config.ARTWORKS_PROCESSED_DIR.exists(),
        "finalised_dir": config.ARTWORKS_FINALISED_DIR.exists(),
        "parse_failures": sorted(
            p.name for p in config.PARSE_FAILURE_DIR.glob("*.txt")
        ),
    }
    return render_template("debug_status.html", info=info, menu=utils.get_menu())

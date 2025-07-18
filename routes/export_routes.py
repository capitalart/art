from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path
from typing import List, Dict

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, abort

import config
from . import utils
from scripts import sellbrite_csv_export as sb

bp = Blueprint("exports", __name__, url_prefix="/exports")


def _collect_listings(locked_only: bool) -> List[Dict]:
    listings = []
    for base in (config.ARTWORKS_FINALISED_DIR, config.LOCKED_VAULT_DIR):
        if not base.exists():
            continue
        for listing in base.rglob("*-listing.json"):
            try:
                utils.assign_or_get_sku(listing, config.SKU_TRACKER)
                with open(listing, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if locked_only and not data.get("locked"):
                continue
            listings.append(data)
    return listings


def _export_csv(listings: List[Dict], locked_only: bool) -> tuple[Path, Path, List[str]]:
    config.SELLBRITE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    kind = "locked" if locked_only else "all"
    csv_path = config.SELLBRITE_OUTPUT_DIR / f"sellbrite_{stamp}_{kind}.csv"
    log_path = config.SELLBRITE_OUTPUT_DIR / f"sellbrite_{stamp}_{kind}.log"

    header = sb.read_template_header(config.SELLBRITE_TEMPLATE_CSV)

    errors = utils.validate_all_skus(listings, config.SKU_TRACKER)
    if errors:
        raise ValueError("; ".join(errors))

    warnings: List[str] = []
    def row_iter():
        for data in listings:
            missing = [k for k in ("title", "description", "sku", "price") if not data.get(k)]
            if len((data.get("description") or "").split()) < 400:
                missing.append("description<400w")
            if not data.get("images"):
                missing.append("images")
            if missing:
                warnings.append(f"{data.get('seo_filename', 'unknown')}: {', '.join(missing)}")
            yield data

    sb.export_to_csv(row_iter(), header, csv_path)
    with open(log_path, "w", encoding="utf-8") as log:
        if warnings:
            log.write("\n".join(warnings))
        else:
            log.write("No warnings")
    return csv_path, log_path, warnings


@bp.route("/sellbrite")
def sellbrite_exports():
    items = []
    for csv_file in sorted(config.SELLBRITE_OUTPUT_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True):
        log_file = csv_file.with_suffix(".log")
        export_type = "Locked" if "locked" in csv_file.stem else "All"
        items.append({
            "name": csv_file.name,
            "mtime": datetime.datetime.fromtimestamp(csv_file.stat().st_mtime),
            "type": export_type,
            "log": log_file.name if log_file.exists() else None,
        })
    return render_template("sellbrite_exports.html", exports=items, menu=utils.get_menu())


@bp.route("/sellbrite/run", methods=["GET", "POST"])
def run_sellbrite_export():
    locked = request.args.get("locked") in {"1", "true", "yes"}
    try:
        listings = _collect_listings(locked)
        csv_path, log_path, warns = _export_csv(listings, locked)
        flash(f"Export created: {csv_path.name}", "success")
        if warns:
            flash(f"{len(warns)} warning(s) generated", "warning")
    except Exception as exc:  # noqa: BLE001
        flash(f"Export failed: {exc}", "danger")
    return redirect(url_for("exports.sellbrite_exports"))


@bp.route("/sellbrite/download/<path:csv_filename>")
def download_sellbrite(csv_filename: str):
    return send_from_directory(config.SELLBRITE_OUTPUT_DIR, csv_filename, as_attachment=True)


@bp.route("/sellbrite/preview/<path:csv_filename>")
def preview_sellbrite_csv(csv_filename: str):
    path = config.SELLBRITE_OUTPUT_DIR / csv_filename
    if not path.exists():
        abort(404)
    rows = []
    header: List[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for i, row in enumerate(reader):
            if i >= 20:
                break
            rows.append(row)
    return render_template(
        "sellbrite_csv_preview.html",
        csv_filename=csv_filename,
        header=header,
        rows=rows,
        menu=utils.get_menu(),
    )


@bp.route("/sellbrite/log/<path:log_filename>")
def view_sellbrite_log(log_filename: str):
    path = config.SELLBRITE_OUTPUT_DIR / log_filename
    if not path.exists():
        abort(404)
    text = path.read_text(encoding="utf-8")
    return render_template(
        "sellbrite_log.html",
        log_filename=log_filename,
        log_text=text,
        menu=utils.get_menu(),
    )

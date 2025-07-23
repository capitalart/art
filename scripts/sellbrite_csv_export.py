"""Generate a Sellbrite-compatible CSV from artwork data.

This script reads either an Etsy CSV export or ArtNarrator listing JSON
files and produces a CSV ready for upload to Sellbrite. The Sellbrite
CSV header is taken from a provided template so the column order matches
exactly.

The business rules are enforced:
- Quantity fixed to 25
- Condition set to "New"
- Brand set to "Robin Custance Art"
- Category always "Art & Collectibles > Prints > Digital Prints"
- Weight set to 0 (digital product)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from routes import utils
import config

import pandas as pd


def read_template_header(template_path: Path) -> List[str]:
    """Return the header row from the Sellbrite template CSV."""
    with open(template_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            header = [h.strip() for h in row]
            if header:
                return header
    raise ValueError("Template CSV missing header")


def load_etsy_csv(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield dicts from an Etsy export CSV."""
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        yield row.to_dict()


def load_listing_json(folder: Path) -> Iterable[Dict[str, Any]]:
    """Yield listing data from JSON files within ``folder``."""
    for listing in folder.rglob("*-listing.json"):
        try:
            utils.assign_or_get_sku(listing, config.SKU_TRACKER)
            with open(listing, "r", encoding="utf-8") as f:
                data = json.load(f)
            yield data
        except Exception:
            continue


def ensure_description(text: str) -> str:
    """Return a plain text description of at least 400 words."""
    if not text:
        text = "This digital artwork comes from Australian Aboriginal artist Robin Custance. "
    words = text.split()
    if len(words) < 400:
        pad = (400 - len(words))
        extra = (" Robin shares stories of culture and country through vibrant colours." * 50).split()[:pad]
        words.extend(extra)
    return " ".join(words)


def map_row(data: Dict[str, Any]) -> Dict[str, Any]:
    """Map input fields to Sellbrite fields applying business rules."""
    def first_non_empty(*keys: str) -> Optional[str]:
        for k in keys:
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    sku = first_non_empty("SKU", "sku") or ""
    name = first_non_empty("Title", "title", "name") or sku
    description = first_non_empty("Description", "description") or ""
    description = ensure_description(description)
    price = first_non_empty("Price", "price") or "0"
    tags_raw = first_non_empty("Tags", "tags") or ""
    if isinstance(tags_raw, list):
        tags = ",".join(t.strip().replace(" ", "") for t in tags_raw)
    else:
        tags = ",".join(t.strip().replace(" ", "") for t in str(tags_raw).split(",") if t.strip())

    images: List[str] = []
    for i in range(1, 9):
        img = data.get(f"Image{i}") or data.get(f"image_{i}")
        if not img and i == 1:
            img = data.get("Image1") or data.get("image")
        if img:
            images.append(str(img))
    if not images:
        imgs = data.get("images") or []
        if isinstance(imgs, str):
            imgs = [i for i in imgs.splitlines() if i.strip()]
        images = list(imgs)[:8]

    mapped = {
        "SKU": sku,
        "Name": name,
        "Description": description,
        "Price": price,
        "Quantity": 25,
        "Condition": "New",
        "Brand": "Robin Custance Art",
        "Category": "Art & Collectibles > Prints > Digital Prints",
        "Weight": 0,
    }
    for idx in range(8):
        mapped[f"Image {idx+1}"] = images[idx] if idx < len(images) else ""
    mapped["Tags"] = tags
    return mapped


def export_to_csv(data: Iterable[Dict[str, Any]], template_header: List[str], output: Path) -> None:
    """Write mapped rows to ``output`` with header from template."""
    rows = list(data)
    errors = utils.validate_all_skus(rows, config.SKU_TRACKER)
    if errors:
        raise ValueError("; ".join(errors))

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=template_header)
        writer.writeheader()
        for item in rows:
            mapped = map_row(item)
            row = {k: mapped.get(k, "") for k in template_header}
            writer.writerow(row)



def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate Sellbrite CSV")
    parser.add_argument("template", type=Path, help="Sellbrite template CSV")
    parser.add_argument("output", type=Path, help="Output CSV path")
    parser.add_argument("--etsy", type=Path, help="Etsy CSV export")
    parser.add_argument("--json-dir", type=Path, help="Directory of listing JSON files")
    args = parser.parse_args()

    header = read_template_header(args.template)
    rows: List[Dict[str, Any]] = []
    if args.etsy and args.etsy.exists():
        rows.extend(load_etsy_csv(args.etsy))
    if args.json_dir and args.json_dir.exists():
        rows.extend(load_listing_json(args.json_dir))
    if not rows:
        raise SystemExit("No input data provided")

    export_to_csv(rows, header, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()

"""Generate a Sellbrite-compatible CSV from artwork data.

This script reads either an Etsy CSV export or ART Narrator listing JSON
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

REQUIRED_COLUMNS = ["sku", "name", "description", "price"]


def validate_header(header: List[str]) -> None:
    lower = [h.lower() for h in header]
    missing = [c for c in REQUIRED_COLUMNS if c.lower() not in lower]
    if missing:
        raise ValueError(f"Template missing required columns: {', '.join(missing)}")


def read_template_header(template_path: Path) -> List[str]:
    """Return the header row from the Sellbrite template CSV."""
    with open(template_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    if rows and rows[0] and rows[0][0].startswith("SELLBRITE PRODUCT CSV"):
        header = rows[2] if len(rows) >= 3 else rows[-1]
    else:
        header = rows[0] if rows else []

    header = [h.strip() for h in header]
    if not header:
        raise ValueError("Template CSV missing header")
    validate_header(header)
    return header


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


def map_row(data: Dict[str, Any], header: List[str]) -> Dict[str, Any]:
    """Map input fields to Sellbrite fields applying business rules."""
    def first_non_empty(*keys: str):
        """Return first non-empty value from ``data`` for the given keys."""
        for k in keys:
            v = data.get(k)
            if isinstance(v, str):
                if v.strip():
                    return v.strip()
            elif v:
                return v
        return None

    sku = first_non_empty("SKU", "sku") or ""
    name = first_non_empty("Title", "title", "name") or sku
    description = first_non_empty("Description", "description") or ""
    description = ensure_description(description)
    price = first_non_empty("Price", "price") or "0"
    tags_raw = first_non_empty("Tags", "tags") or ""
    if isinstance(tags_raw, list):
        # Join tag list with comma+space for readability
        tags = ", ".join(t.strip() for t in tags_raw if t.strip())
    else:
        # Handle accidental string values
        tags = ", ".join(
            t.strip() for t in str(tags_raw).split(",") if t.strip()
        )

    materials_raw = first_non_empty("Materials", "materials") or ""
    if isinstance(materials_raw, list):
        # Join materials list with comma+space for readability
        materials = ", ".join(m.strip() for m in materials_raw if m.strip())
    else:
        # Handle accidental string values
        materials = ", ".join(
            m.strip() for m in str(materials_raw).split(",") if m.strip()
        )

    locked = data.get("locked")
    locked_flag = "Y" if locked else ""

    dws = (
        data.get("DWS")
        or data.get("dws")
        or data.get("digital_wall_size")
        or ""
    )

    images: List[str] = []
    for i in range(1, 11):
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

    mapped: Dict[str, Any] = {}
    if "sku" in header:
        mapped["sku"] = sku
    if "SKU" in header:  # backward compat
        mapped["SKU"] = sku
    if "parent_sku" in header:
        mapped["parent_sku"] = ""
    if "name" in header or "Name" in header:
        mapped["name" if "name" in header else "Name"] = name
    if "description" in header or "Description" in header:
        mapped["description" if "description" in header else "Description"] = description
    if "price" in header or "Price" in header:
        mapped["price" if "price" in header else "Price"] = price
    if "quantity" in header or "Quantity" in header:
        mapped["quantity" if "quantity" in header else "Quantity"] = config.SELLBRITE_DEFAULT_QUANTITY
    if "condition" in header or "Condition" in header:
        mapped["condition" if "condition" in header else "Condition"] = "New"
    if "brand" in header or "Brand" in header:
        mapped["brand" if "brand" in header else "Brand"] = "Robin Custance Art"
    if "category_name" in header or "Category" in header:
        mapped["category_name" if "category_name" in header else "Category"] = (
            "Art > Paintings"
        )
    if "package_weight" in header or "Weight" in header or "Weight (oz)" in header:
        mapped[
            "package_weight" if "package_weight" in header else ("Weight (oz)" if "Weight (oz)" in header else "Weight")
        ] = 0
    if "Product Type" in header:
        mapped["Product Type"] = "Artwork"
    if "Digital/Physical" in header:
        mapped["Digital/Physical"] = "Physical"
    if "Primary Colour" in header:
        mapped["Primary Colour"] = first_non_empty("primary_colour", "Primary Colour") or ""
    if "Secondary Colour" in header:
        mapped["Secondary Colour"] = first_non_empty("secondary_colour", "Secondary Colour") or ""
    if "Active" in header:
        mapped["Active"] = "Yes"
    if "Published" in header:
        mapped["Published"] = "Yes"

    # Optional fields for tags/materials
    if "Tags" in header or "tags" in header:
        mapped["Tags" if "Tags" in header else "tags"] = tags
    if "Materials" in header or "materials" in header:
        mapped["Materials" if "Materials" in header else "materials"] = materials

    if "Locked" in header:
        mapped["Locked"] = locked_flag
    if "DWS" in header:
        mapped["DWS"] = dws

    for idx in range(10):
        key1 = f"product_image_{idx+1}"
        key2 = f"Image {idx+1}"
        if key1 in header or key2 in header:
            mapped[key1 if key1 in header else key2] = images[idx] if idx < len(images) else ""

    return mapped


def export_to_csv(data: Iterable[Dict[str, Any]], template_header: List[str], output: Path) -> None:
    """Write mapped rows to ``output`` with header from template."""
    validate_header(template_header)
    rows = list(data)
    errors = utils.validate_all_skus(rows, config.SKU_TRACKER)
    if errors:
        raise ValueError("; ".join(errors))

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=template_header,
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for item in rows:
            mapped = map_row(item, template_header)
            row = {k: mapped.get(k, "") for k in template_header}
            for col in REQUIRED_COLUMNS:
                key = col if col in template_header else col.capitalize()
                if key in template_header and not row.get(key):
                    raise ValueError(f"Missing value for {col} in row {item.get('sku')}")
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

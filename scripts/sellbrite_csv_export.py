# scripts/sellbrite_csv_export.py
"""
Generate a Sellbrite-compatible CSV from artwork data.

This script reads ArtNarrator listing JSON files and produces a CSV
ready for upload to Sellbrite, using a template for the header.

INDEX
-----
1.  Imports
2.  Data Loading Functions
3.  Data Mapping & Validation
4.  Main Export Function
5.  Command-Line Interface (CLI)
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

# Local application imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from routes import utils
import config
import pandas as pd

logger = logging.getLogger(__name__)

# ===========================================================================
# 2. Data Loading Functions
# ===========================================================================

def read_template_header(template_path: Path) -> List[str]:
    """Return the header row from the Sellbrite template CSV."""
    with open(template_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            header = [h.strip() for h in row]
            if header:
                return header
    raise ValueError("Template CSV is missing a header row.")


def load_listing_json(folder: Path) -> Iterable[Dict[str, Any]]:
    """Yield listing data from all *-listing.json files within a folder."""
    for listing_path in folder.rglob("*-listing.json"):
        try:
            utils.assign_or_get_sku(listing_path, config.SKU_TRACKER)
            with open(listing_path, "r", encoding="utf-8") as f:
                yield json.load(f)
        except Exception as e:
            logger.warning(f"Could not load or process listing JSON {listing_path.name}: {e}")
            continue


# ===========================================================================
# 3. Data Mapping & Validation
# ===========================================================================

def ensure_description(text: str) -> str:
    """
    Ensures a description exists and meets a minimum word count by padding it
    if necessary. This is a workaround for marketplace requirements.
    """
    if not text:
        text = "This digital artwork comes from Australian Aboriginal artist Robin Custance. "
    words = text.split()
    if len(words) < 400:
        pad_count = 400 - len(words)
        padding_text = (" Robin shares stories of culture and country through vibrant colours." * 50).split()
        words.extend(padding_text[:pad_count])
    return " ".join(words)


def map_row(data: Dict[str, Any]) -> Dict[str, Any]:
    """Maps input data from a listing JSON to the Sellbrite CSV format."""
    sku = data.get("sku") or ""
    name = data.get("title") or sku
    description = ensure_description(data.get("description", ""))
    price = data.get("price") or "0"
    
    tags_raw = data.get("tags", [])
    tags = ",".join(t.strip().replace(" ", "") for t in tags_raw)

    images_raw = data.get("images", [])
    images = list(images_raw)[:8] # Get up to 8 images

    # Use default values from config for consistency
    mapped = {
        "SKU": sku,
        "Name": name,
        "Description": description,
        "Price": price,
        "Quantity": config.SELLBRITE_DEFAULTS["QUANTITY"],
        "Condition": config.SELLBRITE_DEFAULTS["CONDITION"],
        "Brand": f"{config.BRAND_AUTHOR} Art",
        "Category": config.SELLBRITE_DEFAULTS["CATEGORY"],
        "Weight": config.SELLBRITE_DEFAULTS["WEIGHT"],
        "Tags": tags,
    }

    # Map images to Image 1, Image 2, etc. columns
    for idx in range(8):
        mapped[f"Image {idx+1}"] = images[idx] if idx < len(images) else ""
        
    return mapped


# ===========================================================================
# 4. Main Export Function
# ===========================================================================

def export_to_csv(data: Iterable[Dict[str, Any]], template_header: List[str], output: Path) -> None:
    """
    Writes mapped rows to a CSV file with a specific header.
    """
    rows = list(data)
    if not rows:
        logger.warning("No data provided to export_to_csv. Aborting export.")
        return

    errors = utils.validate_all_skus(rows, config.SKU_TRACKER)
    if errors:
        error_str = "; ".join(errors)
        logger.error(f"SKU validation failed: {error_str}")
        raise ValueError(error_str)

    logger.info(f"Starting CSV export for {len(rows)} items to {output}...")
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=template_header)
        writer.writeheader()
        for item in rows:
            mapped = map_row(item)
            # Ensure only columns from the header are written
            row_to_write = {k: mapped.get(k, "") for k in template_header}
            writer.writerow(row_to_write)
    logger.info("CSV export completed successfully.")


# ===========================================================================
# 5. Command-Line Interface (CLI)
# ===========================================================================

def main() -> None:
    """Main function to run the script from the command line."""
    parser = argparse.ArgumentParser(description="Generate a Sellbrite-compatible CSV from listing data.")
    parser.add_argument("template", type=Path, help="Path to the Sellbrite template CSV file.")
    parser.add_argument("output", type=Path, help="Path for the output CSV file.")
    parser.add_argument("--json-dir", type=Path, help="Directory of ArtNarrator listing JSON files.", required=True)
    args = parser.parse_args()

    if not args.json_dir.exists():
        logger.critical(f"Input JSON directory not found: {args.json_dir}")
        raise SystemExit(1)

    try:
        header = read_template_header(args.template)
        listing_data = list(load_listing_json(args.json_dir))
        
        if not listing_data:
            print(f"No valid *-listing.json files found in {args.json_dir}.")
            return
            
        export_to_csv(listing_data, header, args.output)
        print(f"✅ Wrote {len(listing_data)} rows to {args.output}")
    except Exception as e:
        logger.error(f"Failed to generate Sellbrite CSV: {e}", exc_info=True)
        print(f"❌ An error occurred. Check logs for details. Error: {e}")


if __name__ == "__main__":
    main()
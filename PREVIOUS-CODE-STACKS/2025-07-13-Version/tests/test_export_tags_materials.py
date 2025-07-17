import csv
import os
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import scripts.sellbrite_csv_export as sb
import config


def test_export_tags_materials(tmp_path):
    template = tmp_path / "template.csv"
    header = [
        "SKU",
        "Name",
        "Description",
        "Price",
        "Quantity",
        "Condition",
        "Brand",
        "Category",
        "Weight",
        "Image 1",
        "Tags",
        "Materials",
        "Locked",
        "DWS",
    ]
    template.write_text(",".join(header))

    orig_template = os.environ.get("SELLBRITE_TEMPLATE_CSV")
    orig_tracker = os.environ.get("SKU_TRACKER_PATH")
    os.environ["SELLBRITE_TEMPLATE_CSV"] = str(template)
    os.environ["SKU_TRACKER_PATH"] = str(tmp_path / "tracker.json")
    Path(os.environ["SKU_TRACKER_PATH"]).write_text('{"last_sku": 1}')

    importlib.reload(config)
    importlib.reload(sb)

    listing = {
        "sku": "RJC-0001",
        "title": "Test",
        "description": "desc" * 50,
        "price": "10",
        "tags": ["a", "b", "c"],
        "materials": ["x", "y"],
        "images": ["img1.jpg"],
    }

    out_csv = tmp_path / "out.csv"
    sb.export_to_csv([listing], header, out_csv)

    rows = list(csv.DictReader(out_csv.open()))
    assert rows[0]["Tags"] == "a, b, c"
    assert rows[0]["Materials"] == "x, y"

    if orig_template is not None:
        os.environ["SELLBRITE_TEMPLATE_CSV"] = orig_template
    else:
        os.environ.pop("SELLBRITE_TEMPLATE_CSV", None)
    if orig_tracker is not None:
        os.environ["SKU_TRACKER_PATH"] = orig_tracker
    else:
        os.environ.pop("SKU_TRACKER_PATH", None)

    importlib.reload(config)
    importlib.reload(sb)

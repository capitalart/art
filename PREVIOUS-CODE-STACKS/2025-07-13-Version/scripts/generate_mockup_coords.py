import json
import sys
from pathlib import Path
from PIL import Image


def generate_coords(image_path: Path) -> dict:
    """Return basic corner coordinates covering the full image."""
    with Image.open(image_path) as img:
        width, height = img.size
    corners = [
        {"x": 0, "y": 0},
        {"x": width, "y": 0},
        {"x": width, "y": height},
        {"x": 0, "y": height},
    ]
    return {"corners": corners, "width": width, "height": height}


def main(argv: list[str]) -> None:
    if len(argv) != 3:
        print("Usage: generate_mockup_coords.py <image_path> <output_json>")
        raise SystemExit(1)
    img_path = Path(argv[1])
    out_path = Path(argv[2])
    coords = generate_coords(img_path)
    out_path.write_text(json.dumps(coords, indent=2))
    print(f"Coords saved to {out_path}")


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv)

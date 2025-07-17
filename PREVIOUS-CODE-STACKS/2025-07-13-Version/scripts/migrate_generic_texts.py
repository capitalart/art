import json
from pathlib import Path

from config import BASE_DIR

GENERIC_DIR = BASE_DIR / "generic_texts"
GDWS_DIR = BASE_DIR / "gdws_content"

DEFAULT_INSTRUCTIONS = "Rewrite this paragraph to be concise and engaging."


def migrate():
    for txt_file in GENERIC_DIR.glob("*.txt"):
        aspect = txt_file.stem
        aspect_dir = GDWS_DIR / aspect
        aspect_dir.mkdir(parents=True, exist_ok=True)

        text = txt_file.read_text(encoding="utf-8")
        blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
        for i, block in enumerate(blocks, 1):
            para_dir = aspect_dir / f"paragraph_{i:02d}"
            para_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "id": f"{para_dir.name}_{i:02d}",
                "title": para_dir.name.replace("_", " ").title(),
                "base_text": block,
                "base_instructions": DEFAULT_INSTRUCTIONS,
                "current_text": block,
            }
            out_file = para_dir / "variation_01.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        print(f"Migrated {txt_file.name} -> {aspect_dir}")


if __name__ == "__main__":
    migrate()

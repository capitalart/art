# === [ ART Narrator: SKU Assigner ] ====================================
# File: utils/sku_assigner.py  (or wherever fits your project layout)

import json
from pathlib import Path
import threading

SKU_PREFIX = "RJC-"
SKU_DIGITS = 4  # e.g., 0122 for 122

_LOCK = threading.Lock()  # for thread/process safety

def get_next_sku(tracker_path: Path) -> str:
    """Safely increment and return the next sequential SKU."""
    print("[SKU DEBUG] Using tracker file:", tracker_path)
    with _LOCK:
        # 1. Load or create tracker file
        if tracker_path.exists():
            with open(tracker_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_sku = int(data.get("last_sku", 0))
        else:
            last_sku = 0

        # 2. Increment
        next_sku_num = last_sku + 1
        next_sku_str = f"{SKU_PREFIX}{next_sku_num:0{SKU_DIGITS}d}"

        # 3. Write back to tracker
        data = {"last_sku": next_sku_num}
        with open(tracker_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return next_sku_str

def peek_next_sku(tracker_path: Path) -> str:
    """Return what the next SKU would be without incrementing."""
    print("[SKU DEBUG] Peeking tracker file:", tracker_path)
    if tracker_path.exists():
        with open(tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            last_sku = int(data.get("last_sku", 0))
    else:
        last_sku = 0

    next_sku_num = last_sku + 1
    next_sku_str = f"{SKU_PREFIX}{next_sku_num:0{SKU_DIGITS}d}"
    return next_sku_str


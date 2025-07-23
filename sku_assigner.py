import json
import re
from pathlib import Path
import fcntl

def scan_for_max_sku(listings_root: Path) -> int:
    """Scan all listing JSONs for highest RJC-xxxx SKU, return max as int."""
    max_sku = 0
    sku_re = re.compile(r"RJC-(\d{4})")
    for listing_file in listings_root.glob("**/*-listing.json"):
        try:
            with open(listing_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            sku = data.get("sku")
            if sku:
                m = sku_re.match(sku)
                if m:
                    num = int(m.group(1))
                    if num > max_sku:
                        max_sku = num
        except Exception:
            continue
    return max_sku

def get_next_sku(tracker_path: Path, listings_root: Path) -> str:
    """
    Get the next available SKU as RJC-xxxx, using tracker file for speed,
    but scanning all listings to prevent duplicates or recover from corruption.
    """
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    # File-lock for safety on concurrent runs (only on UNIX systems)
    try:
        with open(tracker_path, "a+", encoding="utf-8") as tf:
            tf.seek(0)
            try:
                fcntl.flock(tf, fcntl.LOCK_EX)
            except Exception:
                pass  # Flock not available on all OS, ignore if fails

            try:
                tracker = json.load(tf)
                last_sku = int(tracker.get("last_sku", 0))
            except Exception:
                last_sku = 0

            # Always double-check by scanning actual files
            max_in_files = scan_for_max_sku(listings_root)
            next_sku = max(last_sku, max_in_files) + 1

            # Update tracker file
            tf.seek(0)
            tf.truncate()
            json.dump({"last_sku": next_sku}, tf, indent=2)
            tf.flush()

            try:
                fcntl.flock(tf, fcntl.LOCK_UN)
            except Exception:
                pass
    except Exception as e:
        print(f"Error during file operation: {e}")

    return f"RJC-{next_sku:04d}"

def peek_next_sku(tracker_path: Path, listings_root: Path) -> str:
    """Peek what the next SKU would be (not incremented)."""
    try:
        with open(tracker_path, "r", encoding="utf-8") as tf:
            tracker = json.load(tf)
            last_sku = int(tracker.get("last_sku", 0))
    except Exception:
        last_sku = 0
    max_in_files = scan_for_max_sku(listings_root)
    next_sku = max(last_sku, max_in_files) + 1
    return f"RJC-{next_sku:04d}"

# utils/sku_assigner.py
"""
Thread-safe utility for generating and tracking sequential SKUs.

This module reads from and writes to a central SKU tracker JSON file,
ensuring that each artwork receives a unique, sequential SKU.

INDEX
-----
1.  Imports
2.  Configuration & Constants
3.  SKU Management Functions
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import json
import logging
from pathlib import Path
import threading

import config

# ===========================================================================
# 2. Configuration & Constants
# ===========================================================================
SKU_PREFIX = config.SKU_CONFIG["PREFIX"]
SKU_DIGITS = config.SKU_CONFIG["DIGITS"]

_LOCK = threading.Lock()  # for thread/process safety
logger = logging.getLogger(__name__)


# ===========================================================================
# 3. SKU Management Functions
# ===========================================================================

def get_next_sku(tracker_path: Path) -> str:
    """
    Safely increments and returns the next sequential SKU.

    This function reads the last used SKU number from the tracker file,
    increments it, writes the new value back to the file, and returns
    the newly formatted SKU string. It is thread-safe.

    Args:
        tracker_path: The Path object pointing to the SKU tracker JSON file.

    Returns:
        The next sequential SKU as a string (e.g., "RJC-0001").
    """
    with _LOCK:
        try:
            if tracker_path.exists():
                with open(tracker_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    last_sku = int(data.get("last_sku", 0))
            else:
                last_sku = 0
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Could not read SKU tracker at {tracker_path}. Starting from 0. Error: {e}")
            last_sku = 0

        next_sku_num = last_sku + 1
        next_sku_str = f"{SKU_PREFIX}{next_sku_num:0{SKU_DIGITS}d}"

        try:
            tracker_path.write_text(json.dumps({"last_sku": next_sku_num}, indent=2), encoding="utf-8")
            logger.info(f"Assigned new SKU: {next_sku_str}. Tracker file updated.")
        except IOError as e:
            logger.error(f"Could not write to SKU tracker at {tracker_path}: {e}")

        return next_sku_str


def peek_next_sku(tracker_path: Path) -> str:
    """
    Returns what the next SKU would be without incrementing the tracker.

    This is useful for displaying the next available SKU in a UI without
    consuming it. It is thread-safe.

    Args:
        tracker_path: The Path object pointing to the SKU tracker JSON file.

    Returns:
        The next potential SKU as a string.
    """
    with _LOCK:
        try:
            if tracker_path.exists():
                with open(tracker_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    last_sku = int(data.get("last_sku", 0))
            else:
                last_sku = 0
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read SKU tracker at {tracker_path} for peeking. Assuming 0. Error: {e}")
            last_sku = 0

    next_sku_num = last_sku + 1
    return f"{SKU_PREFIX}{next_sku_num:0{SKU_DIGITS}d}"
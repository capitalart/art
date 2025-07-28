#!/usr/bin/env python3
# ==============================================================================
# SCRIPT: run_coordinate_generator.py
#
# PURPOSE:
#   This script orchestrates the interactive generation of coordinate data.
#   It iterates through all categorized mockup aspect ratio folders and calls
#   the `generate_coordinates_for_ratio.py` worker script for each one.
#
# INDEX
# -----
# 1.  Imports
# 2.  Configuration & Logging
# 3.  Main Execution Logic
# 4.  Command-Line Interface (CLI)
# ==============================================================================

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import logging
import subprocess
import sys
from pathlib import Path

# Local application imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from utils.logger_utils import setup_logger

# ===========================================================================
# 2. Configuration & Logging
# ===========================================================================
logger = setup_logger(__name__, "DEFAULT")


# ===========================================================================
# 3. Main Execution Logic
# ===========================================================================

def run_coordinate_generation_for_all_ratios():
    """
    Finds all aspect ratio folders and runs the interactive coordinate
    generator script for each one.
    """
    logger.info("Starting coordinate generation orchestrator script...")
    
    worker_script = config.COORDINATE_GENERATOR_RATIO_SCRIPT_PATH
    if not worker_script.is_file():
        logger.critical(f"Worker script not found at '{worker_script}'. Aborting.")
        return

    mockups_base_dir = config.MOCKUPS_CATEGORISED_DIR
    if not mockups_base_dir.is_dir():
        logger.critical(f"Mockups directory not found at '{mockups_base_dir}'. Aborting.")
        return

    aspect_ratio_folders = [d for d in mockups_base_dir.iterdir() if d.is_dir()]
    
    for aspect_path in aspect_ratio_folders:
        logger.info(f"--- Processing aspect ratio: {aspect_path.name} ---")
        try:
            command = [
                sys.executable,
                str(worker_script),
                "--aspect_ratio_path", str(aspect_path)
            ]
            logger.info(f"Executing command: {' '.join(command)}")
            subprocess.run(command, check=True)
            logger.info(f"Successfully processed aspect ratio: {aspect_path.name}")
        except Exception as e:
            logger.error(f"An error occurred while processing {aspect_path.name}: {e}", exc_info=True)
        
    logger.info("🏁 Finished processing all aspect ratios.")


# ===========================================================================
# 4. Command-Line Interface (CLI)
# ===========================================================================

if __name__ == "__main__":
    run_coordinate_generation_for_all_ratios()
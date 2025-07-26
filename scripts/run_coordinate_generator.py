#!/usr/bin/env python3
# ==============================================================================
# File: run_coordinate_generator.py (ArtNarrator Coordinate Generation Orchestrator)
# Purpose: This script orchestrates the generation of coordinate data for all
#          categorised mockup aspect ratios by calling the worker script.
# ==============================================================================
import subprocess
import pathlib
import logging
import sys

# Ensure project root is on sys.path for config import
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
COORDINATE_GENERATOR_SCRIPT = SCRIPT_DIR / "generate_coordinates_for_ratio.py"
MOCKUPS_INPUT_BASE_DIR = config.MOCKUPS_CATEGORISED_DIR

def run_coordinate_generation_for_all_ratios():
    logger.info(f"Starting coordinate generation using base directory: {MOCKUPS_INPUT_BASE_DIR}")
    if not COORDINATE_GENERATOR_SCRIPT.is_file():
        logger.critical(f"🔴 CRITICAL ERROR: Worker script not found at '{COORDINATE_GENERATOR_SCRIPT}'.")
        return

    if not MOCKUPS_INPUT_BASE_DIR.is_dir():
        logger.critical(f"🔴 CRITICAL ERROR: Mockups directory not found: '{MOCKUPS_INPUT_BASE_DIR}'.")
        return

    # Dynamically find aspect ratio folders
    aspect_ratio_folders = [d.name for d in MOCKUPS_INPUT_BASE_DIR.iterdir() if d.is_dir()]
    
    for ratio_folder_name in aspect_ratio_folders:
        aspect_ratio_path = MOCKUPS_INPUT_BASE_DIR / ratio_folder_name
        logger.info(f"Processing aspect ratio: {ratio_folder_name}")
        try:
            command = [
                sys.executable,
                str(COORDINATE_GENERATOR_SCRIPT),
                "--aspect_ratio_path", str(aspect_ratio_path)
            ]
            logger.info(f"Executing: {' '.join(command)}")
            subprocess.run(command, check=True)
            logger.info(f"✅ Successfully processed aspect ratio: {ratio_folder_name}")
        except Exception as e:
            logger.error(f"🔴 An unexpected error occurred while processing {ratio_folder_name}: {e}", exc_info=True)
        logger.info("-" * 50)
    logger.info("🏁 Finished processing all aspect ratios.")

if __name__ == "__main__":
    run_coordinate_generation_for_all_ratios()
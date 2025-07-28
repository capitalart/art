# utils/logger_utils.py
"""
Utility for structured and centralized application logging.

This module provides the `setup_logger` function, which is the primary
method for creating dedicated, timestamped log files for different parts
of the application based on the central LOG_CONFIG.

INDEX
-----
1.  Imports
2.  Data Sanitization Helpers
3.  Core Logging Setup
4.  Legacy Audit Logger
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import logging
from pathlib import Path
from datetime import datetime
from typing import Any
import config


# ===========================================================================
# 2. Data Sanitization Helpers
# ===========================================================================

def strip_binary(obj: Any) -> Any:
    """Recursively removes bytes/bytearray objects from a data structure."""
    if isinstance(obj, dict):
        return {k: strip_binary(v) for k, v in obj.items() if not isinstance(v, (bytes, bytearray))}
    if isinstance(obj, list):
        return [strip_binary(v) for v in obj if not isinstance(v, (bytes, bytearray))]
    if isinstance(obj, (bytes, bytearray)):
        return f"<stripped {len(obj)} bytes>"
    return obj


def sanitize_blob_data(obj: Any) -> Any:
    """Recursively summarizes binary or long base64 strings for safe logging."""
    if isinstance(obj, dict):
        return {k: sanitize_blob_data(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_blob_data(v) for v in obj]
    if isinstance(obj, (bytes, bytearray)):
        return f"<stripped {len(obj)} bytes>"
    if isinstance(obj, str) and len(obj) > 300 and "base64" in obj:
        return f"<base64 data stripped, length={len(obj)}>"
    return obj


# ===========================================================================
# 3. Core Logging Setup
# ===========================================================================

def setup_logger(logger_name: str, log_key: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configures and returns a logger with a timestamped file handler.

    Uses LOG_CONFIG from config.py to determine the subfolder and filename format.

    Args:
        logger_name: The name of the logger (e.g., __name__).
        log_key: The key from config.LOG_CONFIG (e.g., "ANALYZE_OPENAI").
        level: The logging level (e.g., logging.INFO).

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Prevent duplicate handlers if logger is already configured
    if logger.hasHandlers():
        return logger

    # Get folder and filename details from config
    log_folder_name = config.LOG_CONFIG.get(log_key, config.LOG_CONFIG["DEFAULT"])
    log_dir = config.LOGS_DIR / log_folder_name
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime(config.LOG_TIMESTAMP_FORMAT).upper()
    log_filename = f"{timestamp}-{log_key}.log"
    log_filepath = log_dir / log_filename
    
    # Create and configure file handler
    handler = logging.FileHandler(log_filepath, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


# ===========================================================================
# 4. Legacy Audit Logger
# ===========================================================================

def log_action(
    action: str,
    filename: str,
    user: str | None,
    details: str,
    *,
    status: str = "success",
    error: str | None = None,
) -> None:
    """
    Appends a formatted line to an action-specific audit log.
    Note: This creates hourly log files for high-frequency actions.
    """
    log_folder_name = config.LOG_CONFIG.get(action.upper(), action)
    log_dir = config.LOGS_DIR / log_folder_name
    log_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H") # Hourly log file
    log_file = log_dir / f"{stamp}.log"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    user_id = user or "unknown"
    parts = [
        timestamp,
        f"user: {user_id}",
        f"action: {action}",
        f"file: {filename}",
        f"status: {status}",
        f"detail: {details}",
    ]
    if error:
        parts.append(f"error: {error}")
        
    line = " | ".join(parts) + "\n"
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        # Fallback to main logger if file write fails
        fallback_logger = logging.getLogger(__name__)
        fallback_logger.error(f"Failed to write to action log {log_file}: {e}")
        fallback_logger.error(f"Log line was: {line}")
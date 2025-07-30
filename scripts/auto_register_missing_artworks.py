#!/usr/bin/env python3
"""
Auto-Register Missing Artworks Script
=====================================
Scans the unanalysed-artwork directory, detects any JPEG images not
already registered in the SQLite database, and inserts them into the
`artworks` table.

INDEX
-----
1. Imports & Setup
2. Core Registration Logic
3. Command-Line Interface
"""

# ============================================================================
# 1. Imports & Setup
# ============================================================================
import os
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    from config import settings  # type: ignore
except ImportError:  # Fallback for older config versions
    import config as settings

UNANALYSED_DIR = Path(settings.UNANALYSED_ROOT)
TARGET_EXTS = [".jpg", ".jpeg"]
DB_PATH = Path(settings.DB_PATH)


# ============================================================================
# 2. Core Registration Logic
# ============================================================================

def register_missing_artworks() -> None:
    """Scan folder and insert any unseen artworks into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    skipped = 0

    for file in UNANALYSED_DIR.rglob("*"):
        if file.suffix.lower() not in TARGET_EXTS:
            continue
        if "-thumb" in file.name or "-analyse" in file.name:
            continue

        filename = file.name
        folder = str(file.parent)
        filepath = str(file)

        cursor.execute(
            "SELECT id FROM artworks WHERE original_filename = ?",
            (filename,),
        )
        exists = cursor.fetchone()

        if exists:
            print(f"✅ Exists: {filename}")
            skipped += 1
            continue

        now = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO artworks (
                original_filename,
                original_file_storage_path,
                artwork_base_folder_path,
                status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (filename, filepath, folder, "uploaded_pending_qc", now, now),
        )
        print(f"➕ Inserted: {filename}")
        inserted += 1

    conn.commit()
    conn.close()
    print(f"\n🎉 Done. {inserted} new records added, {skipped} already existed.")


# ============================================================================
# 3. Command-Line Interface
# ============================================================================

if __name__ == "__main__":
    register_missing_artworks()

def register_missing_artworks_internal():
    """Callable version for FastAPI integration."""
    register_missing_artworks()
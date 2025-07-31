# tools/audit/analysis_path_tracker.py
"""
🧠 Analysis Path Tracker – Robbie Mode™ (Forensic Edition)
Scans the project for ALL path, file, and link references used across
the artwork analysis pipeline. Designed to help identify breakages and 
hardcoded patterns in analysis, listing generation, and file workflows.

Author: Codex Assistant + Robin Custance (2025-07-30)
"""

import re
from pathlib import Path
from datetime import datetime

# =============================================================================
# 1. CONFIGURATION
# =============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "logs" / "audit"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
OUTPUT_MD = OUTPUT_DIR / f"analysis_path_tracker_{timestamp}.md"

# --- Exclude folders (based on .gitignore) ---
EXCLUDED_FOLDERS = {
    ".vscode", ".vscode-server", ".idea", ".cache", "__pycache__",
    "venv", ".venv", "env", "ENV", "dist", "build", "instance",
    "backups", "reports", "outputs", "inputs", ".git", "logs"
}

EXCLUDED_EXTENSIONS = {
    ".log", ".bak", ".tmp", ".sqlite3", ".db", ".zip", ".tar.gz"
}

INCLUDED_EXTENSIONS = {".py", ".html", ".jinja", ".jinja2", ".json"}

PATH_PATTERN = re.compile(r"([\"'])(\/[^\"']+|[^\"']*\/[^\"']+)([\"'])")

# =============================================================================
# 2. FILE SCANNING
# =============================================================================
scanned_files = []
for file_path in PROJECT_ROOT.rglob("*"):
    if not file_path.is_file():
        continue
    if file_path.suffix.lower() not in INCLUDED_EXTENSIONS:
        continue
    if any(part in EXCLUDED_FOLDERS for part in file_path.parts):
        continue
    if file_path.suffix.lower() in EXCLUDED_EXTENSIONS:
        continue
    scanned_files.append(file_path)

# =============================================================================
# 3. TRACKING RESULTS
# =============================================================================
path_report = {}

for file in scanned_files:
    try:
        content = file.read_text(encoding="utf-8", errors="ignore")
        matches = PATH_PATTERN.findall(content)
        if matches:
            found_paths = sorted(set(match[1] for match in matches))
            path_report[str(file.relative_to(PROJECT_ROOT))] = found_paths
    except Exception as e:
        path_report[str(file.relative_to(PROJECT_ROOT))] = [f"⚠️ Error reading file: {e}"]

# =============================================================================
# 4. WRITE MARKDOWN REPORT
# =============================================================================
with open(OUTPUT_MD, "w", encoding="utf-8") as md:
    md.write("# 📁 ANALYSIS PATH TRACKER – FORENSIC REPORT\n")
    md.write(f"**Generated:** {datetime.now().isoformat()}\n")
    md.write(f"**Scanned From:** `{PROJECT_ROOT}`\n")
    md.write("**Exclusions:** `.gitignore`, temp/system folders, cache, venv, logs\n\n")

    if not path_report:
        md.write("✅ No paths found in scanned files.\n")
    else:
        for file, paths in sorted(path_report.items()):
            md.write(f"\n---\n## 📄 `{file}`\n")
            for path in paths:
                md.write(f"- `{path}`\n")

print(f"✅ Analysis Path Tracker report saved to: {OUTPUT_MD}")

#!/usr/bin/env python3
"""
📂 Path & Filename Validator (Robbie Mode™)
Full audit of ALL path references used in .py/.html/.json files.

✅ Lists ALL referenced paths (not just invalid)
🚫 Flags issues: bad prefixes/suffixes, illegal chars, hardcoded paths
🧾 Markdown report grouped by source file

Author: Codex Assistant + Robin Custance
Date: 2025-07-30
"""

import re
import fnmatch
from pathlib import Path
from datetime import datetime

# =============================================================================
# 1. CONFIGURATION
# =============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "logs" / "audit"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
OUTPUT_MD = OUTPUT_DIR / f"path_naming_validation_{timestamp}.md"

# =============================================================================
# 2. VALIDATION RULES
# =============================================================================
BAD_PREFIXES = ["digital-"]
BAD_SUFFIXES = ["-download"]
BAD_EXTENSIONS = [".tmp", ".bak", ".swp"]
BAD_FILENAME_CHARS = re.compile(r"[^\w\.-]")  # Allow letters, numbers, underscores, dashes, dots
PATH_REGEX = re.compile(r"([\"'])(\/[^\"']+)([\"'])")  # Match "/something/..."

# FOLDERS TO EXCLUDE (based on gitignore and project conventions)
EXCLUDE_PATTERNS = [
    ".git", ".vscode", ".vscode-server", ".idea", "__pycache__",
    "env", "venv", ".venv", "backups", "reports", "outputs",
    "logs", "dist", "build", "node_modules", ".cache", "inputs",
    "art-processing/*", "*.log", "*.zip", "*.tar.gz", "*.sqlite3", "*.db",
    "*.json", ".DS_Store", "Thumbs.db"
]

def is_excluded(path: Path) -> bool:
    rel = str(path.relative_to(PROJECT_ROOT))
    return any(fnmatch.fnmatch(rel, pat) for pat in EXCLUDE_PATTERNS)

# =============================================================================
# 3. COLLECT FILES TO SCAN
# =============================================================================
target_files = [
    f for f in PROJECT_ROOT.rglob("*")
    if f.suffix in [".py", ".html", ".json"]
    and f.is_file()
    and not is_excluded(f)
]

# =============================================================================
# 4. PATH EXTRACTION + VALIDATION
# =============================================================================
all_findings = {}

for file in target_files:
    try:
        content = file.read_text(encoding="utf-8", errors="ignore")
        matches = PATH_REGEX.findall(content)
        if not matches:
            continue

        path_records = []
        for match in matches:
            raw_path = match[1].strip()
            filename = Path(raw_path).name
            issues = []

            # Check bad prefix/suffix
            if any(filename.startswith(p) for p in BAD_PREFIXES):
                issues.append("🚫 Prefix: digital-")
            if any(filename.endswith(s) for s in BAD_SUFFIXES):
                issues.append("🚫 Suffix: -download")
            if any(ext in filename for ext in BAD_EXTENSIONS):
                issues.append(f"🚫 Extension: {ext}")
            if " " in filename or BAD_FILENAME_CHARS.search(filename):
                issues.append("⚠️ Illegal characters/spaces")

            # Check hardcoded root
            if raw_path.startswith("/home/") or raw_path.startswith("/Users/"):
                issues.append("❌ Hardcoded absolute path")

            # Store path with annotations
            label = f"`{raw_path}`"
            if issues:
                label += " → " + ", ".join(issues)
            path_records.append(label)

        if path_records:
            all_findings[str(file.relative_to(PROJECT_ROOT))] = sorted(set(path_records))

    except Exception as e:
        all_findings[str(file.relative_to(PROJECT_ROOT))] = [f"⚠️ Skipped file (read error): {e}"]

# =============================================================================
# 5. WRITE MARKDOWN REPORT
# =============================================================================
with open(OUTPUT_MD, "w", encoding="utf-8") as out:
    out.write("# 📂 Path & Filename Validation Report (FULL)\n")
    out.write(f"**Generated:** {datetime.now().isoformat()}\n")
    out.write(f"**Project Root:** `{PROJECT_ROOT}`\n\n")

    if not all_findings:
        out.write("✅ No paths or references found.\n")
    else:
        for file, paths in sorted(all_findings.items()):
            out.write(f"\n---\n## `{file}`\n")
            for p in paths:
                out.write(f"- {p}\n")

print(f"✅ Validation report saved to: {OUTPUT_MD}")

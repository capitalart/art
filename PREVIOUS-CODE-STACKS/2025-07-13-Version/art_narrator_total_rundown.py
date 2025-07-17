#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ===========================================
# 🔥 ART Narrator Total Nuclear Snapshot v2.2
# 🚀 Ultimate Dev Toolkit by Robbie Mode™
# All errors & output logged to DEV_LOGS_DIR/snapshot-YYYY-MM-DD-HHMMSS.log
#
# USAGE EXAMPLES:
#   python3 art_narrator_total_rundown.py
#   python3 art_narrator_total_rundown.py --no-zip
#   python3 art_narrator_total_rundown.py --skip-git --skip-env
# ===========================================

import os
import sys
import datetime
import subprocess
import zipfile
import py_compile
from pathlib import Path
from typing import Generator
import argparse
import traceback

from config import DEV_LOGS_DIR

# -------------------------------------------
# Config
ALLOWED_EXTENSIONS = {".py", ".sh", ".jsx", ".txt", ".html", ".js", ".css"}
EXCLUDED_EXTENSIONS = {".json"}
EXCLUDED_FOLDERS = {
    "venv", ".venv", "__MACOSX", ".git", ".vscode", "reports",
    "backups", "node_modules", ".idea", "__pycache__"
}
EXCLUDED_FILES = {".DS_Store"}
LOGS_DIR = DEV_LOGS_DIR
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOGS_DIR / f"snapshot-{datetime.datetime.now():%Y-%m-%d-%H%M%S}.log"


def log(msg):
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as logf:
        logf.write(f"{datetime.datetime.now():[%Y-%m-%d %H:%M:%S]} {msg}\n")


def log_error(msg):
    print(f"\033[91m{msg}\033[0m")  # Red in terminal
    with open(LOG_PATH, "a", encoding="utf-8") as logf:
        logf.write(f"{datetime.datetime.now():[%Y-%m-%d %H:%M:%S]} ERROR: {msg}\n")


# -------------------------------------------
def get_timestamp() -> str:
    return datetime.datetime.now().strftime("REPORTS-%d-%b-%Y-%I-%M%p").upper()


def create_reports_folder() -> Path:
    timestamp = get_timestamp()
    folder_path = Path("reports") / timestamp
    folder_path.mkdir(parents=True, exist_ok=True)
    log(f"📁 Created report folder: {folder_path}")
    return folder_path


def get_included_files() -> Generator[Path, None, None]:
    for path in Path(".").rglob("*"):
        if (
            path.is_file()
            and path.suffix in ALLOWED_EXTENSIONS
            and path.suffix not in EXCLUDED_EXTENSIONS
            and path.name not in EXCLUDED_FILES
            and not any(str(part).lower() in EXCLUDED_FOLDERS for part in path.parts)
        ):
            try:
                path.stat()
                yield path
            except Exception:
                continue


def gather_code_snapshot(folder: Path) -> Path:
    md_path = folder / f"report_code_snapshot_{folder.name.lower()}.md"
    with open(md_path, "w", encoding="utf-8") as md_file:
        md_file.write(f"# 🧠 ART Narrator Code Snapshot — {folder.name}\n\n")
        for file in get_included_files():
            rel_path = file.relative_to(Path("."))
            log(f"📄 Including file: {rel_path}")
            md_file.write(f"\n---\n## 📄 {rel_path}\n\n```{file.suffix[1:] if file.suffix else ''}\n")
            try:
                with open(file, "r", encoding="utf-8") as f:
                    md_file.write(f.read())
            except Exception as e:
                md_file.write(f"[ERROR READING FILE: {e}]")
            md_file.write("\n```\n")
    log(f"✅ Code snapshot saved to: {md_path}")
    return md_path


def generate_file_summary(folder: Path) -> None:
    summary_path = folder / "file_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# 📊 File Summary\n\n")
        f.write("| File | Size (KB) | Last Modified |\n")
        f.write("|------|------------|----------------|\n")
        for file in get_included_files():
            try:
                size_kb = round(file.stat().st_size / 1024, 1)
                mtime = datetime.datetime.fromtimestamp(file.stat().st_mtime)
                rel = file.relative_to(Path("."))
                f.write(f"| `{rel}` | {size_kb} KB | {mtime:%Y-%m-%d %H:%M} |\n")
            except Exception:
                continue
    log(f"📋 File summary written to: {summary_path}")


def validate_python_files() -> None:
    log("\n🧪 Validating Python syntax...")
    for file in get_included_files():
        if file.suffix == ".py":
            try:
                py_compile.compile(file, doraise=True)
                log(f"✅ {file}")
            except py_compile.PyCompileError as e:
                log_error(f"❌ {file} → {e.msg}")


def log_git_status(folder: Path) -> None:
    git_path = folder / "git_snapshot.txt"
    try:
        with open(git_path, "w", encoding="utf-8") as f:
            f.write("🔧 Git Status:\n")
            subprocess.run(["git", "status"], stdout=f, stderr=subprocess.STDOUT, check=False)
            f.write("\n🔁 Last Commit:\n")
            subprocess.run(["git", "log", "-1"], stdout=f, stderr=subprocess.STDOUT, check=False)
            f.write("\n🧾 Diff Summary:\n")
            subprocess.run(["git", "diff", "--stat"], stdout=f, stderr=subprocess.STDOUT, check=False)
        log(f"📘 Git snapshot written to: {git_path}")
    except Exception as e:
        log_error(f"Could not write git snapshot: {e}")


def log_environment_details(folder: Path) -> None:
    env_path = folder / "env_metadata.txt"
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("🐍 Python Version:\n")
            subprocess.run(["python3", "--version"], stdout=f, stderr=subprocess.STDOUT, check=False)
            f.write("\n🖥️ Platform Info:\n")
            if sys.platform != "win32":
                subprocess.run(["uname", "-a"], stdout=f, stderr=subprocess.STDOUT, check=False)
            f.write("\n📦 Installed Packages:\n")
            subprocess.run(["pip", "freeze"], stdout=f, stderr=subprocess.STDOUT, check=False)
        log(f"📚 Environment metadata saved to: {env_path}")
    except Exception as e:
        log_error(f"Failed environment details: {e}")


def show_dependency_issues() -> None:
    log("\n🔍 Running pip check...")
    try:
        subprocess.run(["pip", "check"])
        log("\n📦 Outdated packages:")
        subprocess.run(["pip", "list", "--outdated"])
    except Exception as e:
        log_error(f"pip not found or check failed: {e}")


def zip_report_folder(folder: Path) -> Path:
    zip_path = folder.with_suffix(".zip")
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in folder.rglob("*"):
                zipf.write(file, file.relative_to(folder.parent))
        log(f"📦 Report zipped to: {zip_path}")
        return zip_path
    except Exception as e:
        log_error(f"Zipping report failed: {e}")
        return zip_path


def parse_args():
    parser = argparse.ArgumentParser(description="ART Narrator Dev Snapshot Generator")
    parser.add_argument("--no-zip", action="store_true", help="Skip ZIP archive creation")
    parser.add_argument("--skip-env", action="store_true", help="Skip environment metadata logging")
    parser.add_argument("--skip-validate", action="store_true", help="Skip Python syntax validation")
    parser.add_argument("--skip-git", action="store_true", help="Skip Git snapshot logging")
    parser.add_argument("--skip-pip-check", action="store_true", help="Skip pip dependency checks")
    return parser.parse_args()


def main():
    args = parse_args()
    log("🎨 Generating ART Narrator Total Nuclear Snapshot (v2.2)...")
    try:
        report_folder = create_reports_folder()
        try:
            gather_code_snapshot(report_folder)
        except Exception:
            log_error(f"Code snapshot failed: {traceback.format_exc()}")
        try:
            generate_file_summary(report_folder)
        except Exception:
            log_error(f"File summary failed: {traceback.format_exc()}")
        if not args.skip_validate:
            try:
                validate_python_files()
            except Exception:
                log_error(f"Python validation failed: {traceback.format_exc()}")
        if not args.skip_env:
            try:
                log_environment_details(report_folder)
            except Exception:
                log_error(f"Env details failed: {traceback.format_exc()}")
        if not args.skip_git:
            try:
                log_git_status(report_folder)
            except Exception:
                log_error(f"Git snapshot failed: {traceback.format_exc()}")
        if not args.skip_pip_check:
            try:
                show_dependency_issues()
            except Exception:
                log_error(f"Pip checks failed: {traceback.format_exc()}")
        if not args.no_zip:
            try:
                zip_report_folder(report_folder)
            except Exception:
                log_error(f"Zip step failed: {traceback.format_exc()}")
        log("✅ Snapshot complete. All systems green, Robbie! 💚")
    except Exception:
        log_error(f"Top-level script failure: {traceback.format_exc()}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
System Codex Audit Runner
=========================
This script uses OpenAI GPT-4 Turbo to audit your system codebase.
It generates architecture summaries, flags fragile code, and highlights risks.

STRUCTURE
---------
1. Imports & Setup
2. File Loader with .gitignore Filtering
3. Codex Analysis Logic (Summary + Risk)
4. Main CLI Runner
"""

# ============================================================================
# 1. IMPORTS & SETUP
# ============================================================================
import os
import json
import argparse
from pathlib import Path
import pathspec  # For .gitignore-style exclusions

try:
    from openai import OpenAI
    client = OpenAI()
except Exception as e:
    client = None
    print(f"[ERROR] Failed to initialise OpenAI SDK: {e}")


# ============================================================================
# 2. FILE LOADER WITH .GITIGNORE FILTERING
# ============================================================================
def load_all_code_files(root: Path, exclude_patterns=None) -> dict:
    """
    Recursively loads all Python files under the project root, skipping files
    matched by .gitignore or manually provided exclude patterns.
    """
    code_map = {}
    exclude_patterns = exclude_patterns or []

    # Read .gitignore lines if available
    gitignore_path = root / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            exclude_patterns += f.read().splitlines()

    # Compile the exclusion spec
    spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_patterns)

    # Traverse project directory
    for path in root.rglob("*.py"):
        rel_path = path.relative_to(root)
        if spec.match_file(str(rel_path)):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                code_map[str(rel_path)] = f.read()
        except Exception as e:
            print(f"[WARN] Skipped unreadable file {path}: {e}")

    return code_map


# ============================================================================
# 3. GPT-4 SYSTEM ANALYSIS LOGIC
# ============================================================================
def run_codex_analysis(code_map: dict, summarise_risks: bool = False) -> dict:
    """
    Calls GPT-4 Turbo to generate a summary of the system architecture and,
    optionally, identify fragile or risky areas of code.
    """
    if not client:
        raise RuntimeError("❌ OpenAI SDK not available or failed to initialize.")

    source_blob = json.dumps(code_map)[:12000]  # Truncate to max 12k chars
    messages = [
        {"role": "system", "content": "You are a senior systems architect and audit assistant."},
        {"role": "user", "content": f"Please analyse the following source code and summarise the system structure:\n{source_blob}"}
    ]

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages,
        temperature=0.2,
    )
    summary = response.choices[0].message.content.strip()

    risks = ""
    if summarise_risks:
        risk_messages = [
            {"role": "system", "content": "You are a software auditor. Identify fragile, risky, or inconsistent parts of this codebase."},
            {"role": "user", "content": f"Please identify risk-prone areas in this codebase:\n{source_blob}"}
        ]
        risk_response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=risk_messages,
            temperature=0.1,
        )
        risks = risk_response.choices[0].message.content.strip()

    return {"summary": summary, "risks": risks}


# ============================================================================
# 4. MAIN CLI EXECUTION
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Run a Codex audit on your Python project.")
    parser.add_argument("--summarise-risks", action="store_true", help="Include risky code detection in the report.")
    args = parser.parse_args()

    root_dir = Path(os.getenv("PROJECT_ROOT", Path.cwd()))
    print(f"[INFO] Scanning source files in: {root_dir}")

    contents = load_all_code_files(root_dir)
    print(f"[INFO] Loaded {len(contents)} Python files for audit.")

    result = run_codex_analysis(contents, summarise_risks=args.summarise_risks)

    # === Print Result ===
    print("\n📋 Codex System Summary:\n")
    print(result["summary"])
    if args.summarise_risks:
        print("\n⚠️  Risk & Fragile Code Areas:\n")
        print(result["risks"])

    # === Save Markdown Report ===
    audit_dir = Path("logs/audit/")
    audit_dir.mkdir(parents=True, exist_ok=True)
    output_path = audit_dir / "codex-system-summary.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 🧠 Codex System Summary\n\n")
        f.write(result["summary"])
        if args.summarise_risks:
            f.write("\n\n## ⚠️ Risks and Fragile Areas\n\n")
            f.write(result["risks"])

    print(f"\n✅ Summary saved to: {output_path.resolve()}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
System Codex Audit Runner
=========================
This script uses OpenAI GPT-4 Turbo to audit your system codebase.
It provides architecture summaries, highlights fragile code, and flags risks.

INDEX
-----
1. Imports & Setup
2. Main Audit Functions
3. Command-Line Execution
"""

# ============================================================================
# 1. Imports & Setup
# ============================================================================
import os
import json
import argparse
from pathlib import Path
import pathspec  # Used for .gitignore matching

try:
    from openai import OpenAI
    client = OpenAI()
except Exception:
    client = None


# ============================================================================
# 2. Main Audit Functions
# ============================================================================

def load_all_code_files(root: Path, exclude_patterns=None) -> dict:
    """
    Scans and loads all source files under the project root,
    excluding paths matched by .gitignore or custom patterns.
    """
    code_map = {}
    exclude_patterns = exclude_patterns or []

    # Use .gitignore if present
    gitignore_path = root / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            exclude_patterns += f.read().splitlines()

    spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_patterns)

    for path in root.rglob("*.py"):
        rel_path = path.relative_to(root)
        if spec.match_file(str(rel_path)):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                code_map[str(rel_path)] = f.read()
        except Exception as e:
            print(f"⚠️ Could not read {path}: {e}")
    return code_map


def run_codex_analysis(code_map: dict, summarise_risks: bool = False) -> dict:
    """
    Sends project source code to GPT-4 Turbo to generate:
    - Architectural summary
    - Risk identification (optional)
    """
    if not client:
        raise RuntimeError("❌ OpenAI SDK not available or failed to initialize.")

    # Build message for Codex summary
    messages = [
        {"role": "system", "content": "Summarise the architecture and workflows."},
        {"role": "user", "content": json.dumps(code_map)[:12000]},
    ]
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages,
        temperature=0.2,
    )
    summary = response.choices[0].message.content  # type: ignore

    risks = ""
    if summarise_risks:
        risk_messages = [
            {"role": "system", "content": "Identify risks or fragile code."},
            {"role": "user", "content": json.dumps(code_map)[:12000]},
        ]
        risk_response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=risk_messages,
            temperature=0.1,
        )
        risks = risk_response.choices[0].message.content  # type: ignore

    return {"summary": summary, "risks": risks}


# ============================================================================
# 3. Command-Line Execution
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="System Codex Audit Runner")
    parser.add_argument(
        "--summarise-risks",
        action="store_true",
        help="Also generate risk/failure-prone code identification",
    )
    args = parser.parse_args()

    root_dir = Path(os.getenv("PROJECT_ROOT", Path.cwd()))
    print(f"[INFO] Scanning source files in: {root_dir}")

    contents = load_all_code_files(root_dir)
    print(f"[INFO] {len(contents)} files loaded for audit.")

    result = run_codex_analysis(contents, args.summarise_risks)

    # Output results to stdout and optional file
    print("\n📋 Codex System Summary:\n")
    print(result["summary"])
    if args.summarise_risks:
        print("\n⚠️  Risk & Fragile Code Areas:\n")
        print(result["risks"])

    # Save results to file
    audit_dir = Path("logs/audit/")
    audit_dir.mkdir(parents=True, exist_ok=True)
    summary_path = audit_dir / "codex-system-summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Codex System Summary\n\n")
        f.write(result["summary"])
        if args.summarise_risks:
            f.write("\n\n# Risks and Fragile Areas\n\n")
            f.write(result["risks"])
    print(f"\n✅ Summary saved to {summary_path}")


if __name__ == "__main__":
    main()

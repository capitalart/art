"""tools/audit/system_codex_audit_runner.py
Whole App Introspector that optionally feeds the codebase into OpenAI Codex.

INDEX
-----
1. Imports
2. File Gathering Helpers
3. Codex Interaction
4. Markdown Writers
5. CLI Entry Point
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import pathspec

try:
    import openai
except Exception:  # pragma: no cover - optional dependency
    openai = None

# ===========================================================================
# 2. File Gathering Helpers
# ===========================================================================

IGNORE_DIRS = {".git", "venv", ".venv", "env", "node_modules", "__pycache__"}


def load_gitignore(root: Path) -> pathspec.PathSpec:
    gitignore_file = root / ".gitignore"
    if gitignore_file.exists():
        patterns = gitignore_file.read_text().splitlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    return pathspec.PathSpec.from_lines("gitwildmatch", [])


def gather_python_files(root: Path, spec: pathspec.PathSpec) -> List[Path]:
    files: List[Path] = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in IGNORE_DIRS for part in relative.parts):
            continue
        if spec.match_file(str(relative)):
            continue
        files.append(path)
    return files


def collect_contents(files: List[Path], root: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for f in files:
        data[str(f.relative_to(root))] = f.read_text(encoding="utf-8")
    return data

# ===========================================================================
# 3. Codex Interaction
# ===========================================================================

def run_codex_analysis(code_map: Dict[str, str], summarise_risks: bool) -> Dict[str, str]:
    if openai is None:
        raise RuntimeError("openai package not available")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a senior Python architect. Summarise the project architecture, workflows, and key modules."
            ),
        },
        {"role": "user", "content": json.dumps(code_map)[:12000]},
    ]
    response = openai.ChatCompletion.create(model="gpt-4-turbo", messages=messages)
    summary = response.choices[0].message.content  # type: ignore[index]

    risks = ""
    if summarise_risks:
        risk_messages = [
            {"role": "system", "content": "Identify risks or fragile code."},
            {"role": "user", "content": json.dumps(code_map)[:12000]},
        ]
        risk_response = openai.ChatCompletion.create(model="gpt-4-turbo", messages=risk_messages)
        risks = risk_response.choices[0].message.content  # type: ignore[index]

    return {"summary": summary, "risks": risks}

# ===========================================================================
# 4. Markdown Writers
# ===========================================================================

def write_outputs(result: Dict[str, str], output_dir: Path, summarise_risks: bool) -> None:
    (output_dir / "system_codex_summary.md").write_text(result.get("summary", ""), encoding="utf-8")
    if summarise_risks and result.get("risks"):
        (output_dir / "system_codex_risks.md").write_text(result["risks"], encoding="utf-8")

# ===========================================================================
# 5. CLI Entry Point
# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Whole App Introspector")
    parser.add_argument("--openai", action="store_true", help="Send code to OpenAI for analysis")
    parser.add_argument("--summarise-risks", action="store_true", help="Generate risk analysis")
    parser.add_argument("--dry-run", action="store_true", help="Do not call OpenAI (default)")
    args = parser.parse_args()

    root = Path.cwd()
    spec = load_gitignore(root)
    files = gather_python_files(root, spec)
    contents = collect_contents(files, root)

    output_dir = root / "audit-output"
    output_dir.mkdir(exist_ok=True)

    if args.openai and not args.dry_run:
        result = run_codex_analysis(contents, args.summarise_risks)
    else:
        result = {"summary": "(dry run)" , "risks": ""}

    write_outputs(result, output_dir, args.summarise_risks)


if __name__ == "__main__":  # pragma: no cover
    main()

"""tools/audit/file_import_scanner.py
Recursive Codebase Import Analyzer.

INDEX
-----
1. Imports
2. Helper Classes
3. Core Logic
4. CLI Entry Point
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set

import pathspec

# ===========================================================================
# 2. Helper Classes
# ===========================================================================

class DependencyVisitor(ast.NodeVisitor):
    """AST visitor that collects import and file dependency information."""

    def __init__(self) -> None:
        self.imports: List[str] = []
        self.from_imports: List[str] = []
        self.import_aliases: Set[str] = set()
        self.used_names: Set[str] = set()
        self.file_paths: Set[str] = set()
        self.env_keys: Set[str] = set()

    # -------------------------------------
    # Import collection
    # -------------------------------------
    def visit_Import(self, node: ast.Import) -> Any:  # noqa: D401 - simple visitor
        for alias in node.names:
            self.imports.append(alias.name)
            self.import_aliases.add(alias.asname or alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:  # noqa: D401
        module = node.module or ""
        for alias in node.names:
            full = f"{module}.{alias.name}" if module else alias.name
            self.from_imports.append(full)
            self.import_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    # -------------------------------------
    # Function calls for files/env vars
    # -------------------------------------
    def visit_Call(self, node: ast.Call) -> Any:  # noqa: D401
        func_name = self._get_full_name(node.func)
        if func_name in {"open", "Path", "pathlib.Path"}:
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                self.file_paths.add(node.args[0].value)
        if func_name in {"os.getenv", "os.environ.get"}:
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                self.env_keys.add(node.args[0].value)
        self.generic_visit(node)

    # -------------------------------------
    # Attribute access for settings keys
    # -------------------------------------
    def visit_Attribute(self, node: ast.Attribute) -> Any:  # noqa: D401
        if isinstance(node.value, ast.Name) and node.value.id == "settings":
            self.env_keys.add(node.attr)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> Any:  # noqa: D401
        self.used_names.add(node.id)
        self.generic_visit(node)

    # Helper to get dotted function name
    @staticmethod
    def _get_full_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return DependencyVisitor._get_full_name(node.value) + "." + node.attr
        return ""

# ===========================================================================
# 3. Core Logic
# ===========================================================================

IGNORE_DIRS = {".git", "venv", ".venv", "env", "node_modules", "__pycache__"}


def load_gitignore(root: Path) -> pathspec.PathSpec:
    """Load .gitignore patterns using pathspec."""
    gitignore_file = root / ".gitignore"
    if gitignore_file.exists():
        patterns = gitignore_file.read_text().splitlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    return pathspec.PathSpec.from_lines("gitwildmatch", [])


def discover_python_files(root: Path, include_tests: bool, spec: pathspec.PathSpec) -> List[Path]:
    """Recursively collect Python files respecting .gitignore and flags."""
    py_files: List[Path] = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in IGNORE_DIRS for part in relative.parts):
            continue
        if spec.match_file(str(relative)):
            continue
        if not include_tests and "tests" in relative.parts:
            continue
        py_files.append(path)
    return py_files


def analyze_file(path: Path) -> Dict[str, Any]:
    """Parse a Python file and return dependency info."""
    visitor = DependencyVisitor()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return {"imports": [], "from_imports": [], "files": [], "env": [], "unused": []}
    visitor.visit(tree)
    unused = sorted(alias for alias in visitor.import_aliases if alias not in visitor.used_names)
    return {
        "imports": sorted(set(visitor.imports)),
        "from_imports": sorted(set(visitor.from_imports)),
        "files": sorted(visitor.file_paths),
        "env": sorted(visitor.env_keys),
        "unused": unused,
    }


def build_summary(root: Path, results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Generate global summary from per-file results."""
    imported_modules: Set[str] = set()
    missing_files: Set[str] = set()
    unused_imports: Dict[str, List[str]] = {}

    for info in results.values():
        imported_modules.update(info["imports"])
        imported_modules.update(info["from_imports"])
        for file_ref in info["files"]:
            if not (root / file_ref).exists():
                missing_files.add(file_ref)
        if info["unused"]:
            unused_imports.setdefault("unused", []).extend(info["unused"])

    summary = {
        "total_files": len(results),
        "unique_imports": sorted(imported_modules),
        "missing_files": sorted(missing_files),
        "unused_imports": sorted(set(unused_imports.get("unused", []))),
    }
    return summary



def write_markdown_per_file(results: Dict[str, Dict[str, Any]], outfile: Path) -> None:
    """Write a markdown report listing dependencies per file."""
    lines = ["# File Import Report", ""]
    for file, info in sorted(results.items()):
        lines.append(f"## {file}")
        lines.append("- Imports: " + ", ".join(info["imports"]))
        lines.append("- From Imports: " + ", ".join(info["from_imports"]))
        lines.append("- Files: " + ", ".join(info["files"]))
        lines.append("- Env Keys: " + ", ".join(info["env"]))
        if info["unused"]:
            lines.append("- Unused Imports: " + ", ".join(info["unused"]))
        lines.append("")
    outfile.write_text("\n".join(lines), encoding="utf-8")


def write_summary(summary: Dict[str, Any], outfile: Path) -> None:
    """Write global summary markdown."""
    lines = ["# Import Dependency Summary", ""]
    lines.append(f"Total Python files scanned: {summary['total_files']}")
    lines.append("")
    lines.append("## Unique Imports")
    for mod in summary["unique_imports"]:
        lines.append(f"- {mod}")
    lines.append("")
    if summary["missing_files"]:
        lines.append("## Missing Files")
        for f in summary["missing_files"]:
            lines.append(f"- {f}")
        lines.append("")
    if summary["unused_imports"]:
        lines.append("## Unused Imports")
        for imp in summary["unused_imports"]:
            lines.append(f"- {imp}")
        lines.append("")
    outfile.write_text("\n".join(lines), encoding="utf-8")

# ===========================================================================
# 4. CLI Entry Point
# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Recursive Codebase Import Analyzer")
    parser.add_argument("--include-tests", action="store_true", help="Include test files in scan")
    parser.add_argument("--save-json", action="store_true", help="Save dependencies.json as well")
    args = parser.parse_args()

    root = Path.cwd()
    spec = load_gitignore(root)
    py_files = discover_python_files(root, args.include_tests, spec)

    results: Dict[str, Dict[str, Any]] = {}
    for file in py_files:
        rel = str(file.relative_to(root))
        results[rel] = analyze_file(file)

    summary = build_summary(root, results)

    output_dir = root / "audit-output"
    output_dir.mkdir(exist_ok=True)
    write_markdown_per_file(results, output_dir / "file-imports-per-file.md")
    write_summary(summary, output_dir / "import-dependency-summary.md")

    if args.save_json:
        (output_dir / "dependencies.json").write_text(json.dumps({"files": results, "summary": summary}, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()

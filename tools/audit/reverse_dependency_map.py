"""tools/audit/reverse_dependency_map.py
Global Usage Tracer to map definitions and their usage across the project.

INDEX
-----
1. Imports
2. AST Visitors
3. Analysis Helpers
4. Markdown Writers
5. CLI Entry Point
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pathspec

# ===========================================================================
# 2. AST Visitors
# ===========================================================================

class DefinitionVisitor(ast.NodeVisitor):
    """Collects definitions and call sites within a file."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.definitions: Dict[str, Tuple[int, str]] = {}
        self.calls: Dict[str, List[int]] = {}
        self.routes: List[Tuple[str, str, int]] = []  # path, function, line

    # -------------------------------------
    # Definitions
    # -------------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: D401
        self.definitions[node.name] = (node.lineno, self.filename)
        self._check_route(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:  # noqa: D401
        self.definitions[node.name] = (node.lineno, self.filename)
        self.generic_visit(node)

    # -------------------------------------
    # Calls
    # -------------------------------------
    def visit_Call(self, node: ast.Call) -> Any:  # noqa: D401
        name = self._get_name(node.func)
        if name:
            self.calls.setdefault(name, []).append(node.lineno)
        self.generic_visit(node)

    # -------------------------------------
    # Helpers
    # -------------------------------------
    @staticmethod
    def _get_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def _check_route(self, node: ast.FunctionDef) -> None:
        for deco in node.decorator_list:
            name = self._get_name(deco.func if isinstance(deco, ast.Call) else deco)
            if name in {"route", "get", "post", "put", "delete"}:
                if isinstance(deco, ast.Call) and deco.args:
                    arg = deco.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        self.routes.append((arg.value, node.name, node.lineno))

# ===========================================================================
# 3. Analysis Helpers
# ===========================================================================

IGNORE_DIRS = {".git", "venv", ".venv", "env", "node_modules", "__pycache__"}


def load_gitignore(root: Path) -> pathspec.PathSpec:
    gitignore_file = root / ".gitignore"
    if gitignore_file.exists():
        patterns = gitignore_file.read_text().splitlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    return pathspec.PathSpec.from_lines("gitwildmatch", [])


def discover_python_files(root: Path, include_tests: bool, spec: pathspec.PathSpec) -> List[Path]:
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


def analyze_files(files: List[Path], root: Path) -> Tuple[Dict[str, Dict[str, Any]], List[Tuple[str, str, int]]]:
    definitions: Dict[str, Dict[str, Any]] = {}
    usage: Dict[str, Set[str]] = {}
    route_map: List[Tuple[str, str, int]] = []

    for path in files:
        visitor = DefinitionVisitor(str(path.relative_to(root)))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        visitor.visit(tree)

        for name, (line, file) in visitor.definitions.items():
            definitions[name] = {"file": file, "line": line}

        for name, calls in visitor.calls.items():
            usage.setdefault(name, set()).add(visitor.filename)

        route_map.extend([(r, f, l) for r, f, l in visitor.routes])

    for name in usage:
        usage[name] = sorted(usage[name])

    # Cross-reference definitions with usage
    for name, info in definitions.items():
        info["used_in"] = usage.get(name, [])

    return definitions, route_map


def write_reverse_map(defs: Dict[str, Dict[str, Any]], routes: List[Tuple[str, str, int]], outfile: Path, route_only: bool, dead_code: bool) -> None:
    lines = ["# Reverse Dependency Map", ""]
    if not route_only:
        for name, info in sorted(defs.items()):
            lines.append(f"## {name}")
            lines.append(f"Defined in: {info['file']}:{info['line']}")
            if info["used_in"]:
                lines.append("Used in:")
                for loc in info["used_in"]:
                    lines.append(f"- {loc}")
            elif dead_code:
                lines.append("- UNUSED")
            lines.append("")

    lines.append("## Route Map")
    for route, func, line in routes:
        lines.append(f"- {route} -> {func} ({line})")
    outfile.write_text("\n".join(lines), encoding="utf-8")


# ===========================================================================
# 4. Markdown Writers (JSON optional)
# ===========================================================================

def save_json(defs: Dict[str, Dict[str, Any]], routes: List[Tuple[str, str, int]], output_dir: Path) -> None:
    data = {"definitions": defs, "routes": routes}
    (output_dir / "reverse-dependencies.json").write_text(json.dumps(data, indent=2))

# ===========================================================================
# 5. CLI Entry Point
# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Global Usage Tracer")
    parser.add_argument("--include-tests", action="store_true", help="Include test files")
    parser.add_argument("--route-only", action="store_true", help="Output only route mappings")
    parser.add_argument("--dead-code", action="store_true", help="Mark unused functions")
    parser.add_argument("--save-json", action="store_true", help="Save reverse-dependencies.json")
    args = parser.parse_args()

    root = Path.cwd()
    spec = load_gitignore(root)
    py_files = discover_python_files(root, args.include_tests, spec)

    definitions, route_map = analyze_files(py_files, root)

    output_dir = root / "audit-output"
    output_dir.mkdir(exist_ok=True)
    write_reverse_map(definitions, route_map, output_dir / "reverse-dependency-map.md", args.route_only, args.dead_code)

    if args.save_json:
        save_json(definitions, route_map, output_dir)


if __name__ == "__main__":  # pragma: no cover
    main()

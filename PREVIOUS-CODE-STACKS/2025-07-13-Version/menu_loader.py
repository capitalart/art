"""Dynamic mega menu loader for ART Narrator.

This module scans the Jinja ``templates`` folder for HTML
files and attempts to map each template to a Flask route by
parsing the ``routes`` modules. The resulting nested data
structure is used to render the mega menu overlay.

A lightweight approach is used so the server can import this
module without loading the route modules (which may require
external APIs). It only reads the Python files as text.

To customise labels or sections, edit this file or provide
a ``menu.json`` in the project root with a structure like::

    {
        "Section Name": [
            {"label": "Home", "url": "/"}
        ]
    }

When present, the JSON data will override the auto generated
menu.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
ROUTES_DIR = BASE_DIR / "routes"
MENU_CONFIG = BASE_DIR / "menu.json"


def _discover_routes() -> Dict[str, str]:
    """Return mapping of template path to Flask route."""
    mapping: Dict[str, str] = {}
    route_pattern = re.compile(r"@bp\.route\(['\"]([^'\"]+)['\"]")
    prefix_pattern = re.compile(r"Blueprint\([^)]*url_prefix=['\"]([^'\"]+)['\"]")
    template_pattern = re.compile(r"render_template\(['\"]([^'\"]+)['\"]")

    for py_file in ROUTES_DIR.glob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        prefix_match = prefix_pattern.search(text)
        prefix = prefix_match.group(1) if prefix_match else ""
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            t_match = template_pattern.search(line)
            if not t_match:
                continue
            template = t_match.group(1)
            route = None
            for j in range(idx, -1, -1):
                r_match = route_pattern.search(lines[j])
                if r_match:
                    route = r_match.group(1)
                    break
            if route and "<" not in route:
                mapping[template] = prefix + route
    return mapping


def _scan_templates(route_map: Dict[str, str]) -> Dict[str, List[Dict[str, str]]]:
    """Return nested menu data discovered from templates."""
    menu: Dict[str, List[Dict[str, str]]] = {}
    for html in TEMPLATES_DIR.rglob("*.html"):
        parts = set(html.parts)
        if {"components", "templates_components"} & parts:
            continue
        if html.name in {"topnav.html", "main.html"}:
            continue
        if html.stem.startswith("_"):
            continue
        rel = html.relative_to(TEMPLATES_DIR)
        section = "General" if rel.parent == Path(".") else rel.parent.name.replace("_", " ").title()
        label = rel.stem.replace("_", " ").title()
        url = route_map.get(str(rel))
        if not url:
            continue
        menu.setdefault(section, []).append({"label": label, "url": url})

    # Sort sections and items for stable output
    for items in menu.values():
        items.sort(key=lambda x: x["label"])
    return dict(sorted(menu.items()))


def load_menu() -> Dict[str, List[Dict[str, str]]]:
    """Load menu data either from ``menu.json`` or by scanning files."""
    if MENU_CONFIG.exists():
        try:
            with open(MENU_CONFIG, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass

    routes = _discover_routes()
    return _scan_templates(routes)


# Generate on import
MENU_DATA = load_menu()

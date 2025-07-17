import re
from html.parser import HTMLParser
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
os.environ['ADMIN_USER'] = 'robbie'
os.environ['ADMIN_PASS'] = 'secret'
os.environ.setdefault('OPENAI_API_KEY', 'test')
os.environ['LOGS_DIR'] = 'logs'
registry = Path('logs/session_registry.json')
if registry.exists():
    registry.unlink()
import importlib
if 'config' in sys.modules:
    importlib.reload(sys.modules['config'])
import app as app_module
importlib.reload(app_module)
app = app_module.app


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href":
                    self.links.append(v)


def collect_template_endpoints():
    pattern = re.compile(r"url_for\(['\"]([^'\"]+)['\"]")
    endpoints = set()
    for path in Path("templates").rglob("*.html"):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        endpoints.update(pattern.findall(content))
    return endpoints


def test_template_endpoints_valid():
    registered = {r.endpoint for r in app.url_map.iter_rules()}
    templated = collect_template_endpoints()
    missing = [
        e for e in templated if e not in registered and not e.startswith("static")
    ]
    assert not missing, f"Unknown endpoints referenced: {missing}"


def test_routes_and_navigation():
    client = app.test_client()
    client.post('/login', data={'username': 'robbie', 'password': 'secret'}, follow_redirects=True)
    to_visit = ["/"]
    visited = set()
    while to_visit:
        url = to_visit.pop()
        if url in visited:
            continue
        resp = client.get(url)
        if url == '/logout':
            assert resp.status_code == 302
            client.post('/login', data={'username': 'robbie', 'password': 'secret'}, follow_redirects=True)
            continue
        assert resp.status_code in (200, 302), f"Failed loading {url}"
        visited.add(url)
        parser = LinkParser()
        parser.feed(resp.get_data(as_text=True))
        for link in parser.links:
            if link.startswith("http") or link.startswith("mailto:"):
                continue
            if link.startswith("/static") or "//" in link[1:]:
                continue
            if link == "#" or link.startswith("#"):
                continue
            link = link.split("?")[0]
            if link not in visited:
                to_visit.append(link)

    # Additional admin debug endpoints
    resp = client.get("/admin/debug/parse-ai")
    assert resp.status_code == 200
    resp = client.get("/admin/debug/next-sku")
    assert resp.status_code == 200
    resp = client.get("/admin/debug/git-log")
    assert resp.status_code == 200

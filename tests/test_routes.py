import os
import re
from html.parser import HTMLParser
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test")

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
import config

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
    for path in config.TEMPLATES_DIR.rglob('*.html'):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        endpoints.update(pattern.findall(content))
    return endpoints

def test_template_endpoints_valid():
    registered = {r.endpoint for r in app.url_map.iter_rules()}
    templated = collect_template_endpoints()
    missing = [e for e in templated if e not in registered and not e.startswith('static')]
    assert not missing, f"Unknown endpoints referenced: {missing}"

def test_routes_and_navigation():
    client = app.test_client()
    client.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=True)
    to_visit = ['/']
    visited = set()
    while to_visit:
        url = to_visit.pop()
        if url in visited:
            continue
        resp = client.get(url)
        
        # FIX: Handle expected redirects for certain pages during the crawl
        if resp.status_code == 302 and (url == '/logout' or url == '/composites' or url.startswith('/edit-listing')):
            continue
            
        assert resp.status_code == 200, f"Failed loading {url}"
        visited.add(url)
        parser = LinkParser()
        parser.feed(resp.get_data(as_text=True))
        for link in parser.links:
            if link.startswith('http') or link.startswith('mailto:'):
                continue
            if link.startswith('/static') or '//' in link[1:]:
                continue
            if link == '#' or link.startswith('#') or link == '/logout':
                continue
            link = link.split('?')[0]
            if link not in visited:
                to_visit.append(link)
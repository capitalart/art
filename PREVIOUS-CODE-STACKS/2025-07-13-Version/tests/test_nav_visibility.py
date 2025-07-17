import os
from pathlib import Path
import importlib

os.environ['ADMIN_USER'] = 'robbie'
os.environ['ADMIN_PASS'] = 'secret'
os.environ.setdefault('OPENAI_API_KEY', 'test')
os.environ['LOGS_DIR'] = 'logs'
os.environ['ENABLE_UPGRADE'] = 'true'
registry = Path('logs/session_registry.json')
if registry.exists():
    registry.unlink()

import app as app_module
importlib.reload(app_module)
app = app_module.app

from login_bypass import enable, disable

def extract_nav(html: str) -> str:
    start = html.find('<nav')
    end = html.find('</nav>')
    return html[start:end]

def test_guest_nav_visibility():
    client = app.test_client()
    enable(2)
    resp = client.get('/')
    disable()
    assert resp.status_code == 200
    nav = extract_nav(resp.get_data(as_text=True))
    assert 'Login' in nav
    assert 'Account' not in nav
    assert 'Admin' not in nav
    assert 'Dashboard' not in nav
    assert 'Upgrade' not in nav

def test_admin_nav_visibility():
    client = app.test_client()
    client.post('/login', data={'username': 'robbie', 'password': 'secret'}, follow_redirects=True)
    resp = client.get('/')
    assert resp.status_code == 200
    nav = extract_nav(resp.get_data(as_text=True))
    assert 'Account' in nav
    assert 'Dashboard' in nav
    assert 'User Management' in nav
    assert 'Settings' in nav
    assert 'Prompt Options' in nav
    assert 'Security' in nav
    assert 'Sessions' in nav
    assert 'Cache Control' in nav
    assert 'Git Log' in nav
    assert 'Upgrade' in nav
    assert 'Login' not in nav

import os
from pathlib import Path

os.environ['ADMIN_USER'] = 'robbie'
os.environ['ADMIN_PASS'] = 'secret'
os.environ.setdefault('OPENAI_API_KEY', 'test')
os.environ['LOGS_DIR'] = 'logs'
registry = Path('logs/session_registry.json')
if registry.exists():
    registry.unlink()

import importlib
import app as app_module
importlib.reload(app_module)
app = app_module.app


def test_login_required_redirect():
    client = app.test_client()
    resp = client.get('/', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_successful_login_and_logout():
    client = app.test_client()
    resp = client.post('/login', data={'username': 'robbie', 'password': 'secret'}, follow_redirects=True)
    assert b'Logged in as robbie' in resp.data
    resp = client.get('/logout', follow_redirects=True)
    assert b'Login' in resp.data


def test_login_bypass_temporarily_allows_access(tmp_path):
    client = app.test_client()
    from login_bypass import enable, disable
    enable(1)
    resp = client.get('/')
    assert resp.status_code == 200
    import time
    time.sleep(2)
    resp = client.get('/', follow_redirects=False)
    assert resp.status_code == 302 and '/login' in resp.headers['Location']
    disable()

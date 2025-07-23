import os
import sys
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ["ADMIN_USERNAME"] = "robbie"
os.environ["ADMIN_PASSWORD"] = "kangaroo123"


def setup_app(tmp_path):
    os.environ['LOGS_DIR'] = str(tmp_path / 'logs')
    for mod in ('config', 'utils.session_tracker', 'routes.auth_routes', 'app'):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    if 'app' not in sys.modules:
        import app  # type: ignore
    app_module = importlib.import_module('app')
    return app_module.app


def test_session_limit_enforced(tmp_path):
    app = setup_app(tmp_path)
    clients = []
    for _ in range(5):
        c = app.test_client()
        resp = c.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=True)
        assert resp.status_code == 200
        clients.append(c)
    extra = app.test_client()
    resp = extra.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=False)
    assert resp.status_code == 403
    assert b'Maximum login limit' in resp.data

    clients[0].get('/logout', follow_redirects=True)
    resp = extra.post('/login', data={'username': 'robbie', 'password': 'kangaroo123'}, follow_redirects=True)
    assert resp.status_code == 200

import os
import sys
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ['ADMIN_USER'] = 'robbie'
os.environ['ADMIN_PASS'] = 'secret'
os.environ.setdefault('OPENAI_API_KEY', 'test')


def setup_app(tmp_path):
    os.environ['LOGS_DIR'] = str(tmp_path / 'logs')
    if 'config' in sys.modules:
        importlib.reload(sys.modules['config'])
    if 'routes.session_tracker' in sys.modules:
        importlib.reload(sys.modules['routes.session_tracker'])
    if 'app' in sys.modules:
        importlib.reload(sys.modules['app'])
    else:
        import app as app_module
    app_module = importlib.import_module('app')
    return app_module.app


def test_max_active_sessions(tmp_path):
    app = setup_app(tmp_path)
    clients = []
    for _ in range(5):
        c = app.test_client()
        resp = c.post('/login', data={'username': 'robbie', 'password': 'secret'}, follow_redirects=True)
        assert b'Logged in as robbie' in resp.data
        clients.append(c)
    sixth = app.test_client()
    resp = sixth.post('/login', data={'username': 'robbie', 'password': 'secret'}, follow_redirects=False)
    assert resp.status_code == 403
    assert b'Maximum active sessions' in resp.data

    clients[0].get('/logout', follow_redirects=True)
    resp = sixth.post('/login', data={'username': 'robbie', 'password': 'secret'}, follow_redirects=True)
    assert b'Logged in as robbie' in resp.data
    os.environ.pop('LOGS_DIR', None)
    if 'config' in sys.modules:
        importlib.reload(sys.modules['config'])
    if 'routes.session_tracker' in sys.modules:
        importlib.reload(sys.modules['routes.session_tracker'])

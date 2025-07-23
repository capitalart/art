import os
import sys
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("OPENAI_API_KEY", "test")


def setup_app(tmp_path):
    os.environ['LOGS_DIR'] = str(tmp_path / 'logs')
    os.environ['DATA_DIR'] = str(tmp_path / 'data')
    for mod in ('config', 'db', 'utils.security', 'utils.user_manager', 'routes.auth_routes', 'routes.admin_security', 'app'):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    if 'app' not in sys.modules:
        import app  # type: ignore
    app_module = importlib.import_module('app')
    return app_module.app


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)


def test_role_required_admin(tmp_path):
    app = setup_app(tmp_path)
    client = app.test_client()
    resp = login(client, 'viewer', 'viewer123')
    assert resp.status_code == 302
    resp = client.get('/admin/', follow_redirects=False)
    assert resp.status_code == 302
    client.get('/logout')
    resp = login(client, 'robbie', 'kangaroo123')
    assert resp.status_code == 302
    resp = client.get('/admin/', follow_redirects=False)
    assert resp.status_code == 200


def test_no_cache_header(tmp_path):
    app = setup_app(tmp_path)
    client = app.test_client()
    admin_login = login(client, 'robbie', 'kangaroo123')
    assert admin_login.status_code == 302
    client.post('/admin/security', data={'action': 'nocache_on', 'minutes': '1'})
    resp = client.get('/')
    assert resp.headers.get('Cache-Control') == 'no-store, no-cache, must-revalidate, max-age=0'


def test_login_lockout(tmp_path):
    app = setup_app(tmp_path)
    client = app.test_client()
    admin_login = login(client, 'robbie', 'kangaroo123')
    assert admin_login.status_code == 302
    client.post('/admin/security', data={'action': 'disable', 'minutes': '1'})
    client.get('/logout')
    resp = login(client, 'viewer', 'viewer123')
    assert resp.status_code == 403


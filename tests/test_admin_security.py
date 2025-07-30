# tests/test_admin_security.py
import os
import sys
import importlib
from pathlib import Path

# Add project root to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OPENAI_API_KEY", "test")

# Import necessary utilities
from utils import user_manager, session_tracker


def setup_app(tmp_path):
    """Sets up a temporary Flask app instance for testing."""
    os.environ['LOGS_DIR'] = str(tmp_path / 'logs')
    os.environ['DATA_DIR'] = str(tmp_path / 'data')
    # Reload modules to ensure they use the new temp paths
    for mod in ('config', 'db', 'utils.security', 'utils.user_manager', 'routes.auth_routes', 'routes.admin_security', 'app'):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    app_module = importlib.import_module('app')
    return app_module.app


def login(client, username, password):
    """Helper function to log in a user."""
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)


def test_role_required_admin(tmp_path):
    """Tests that only users with the 'admin' role can access admin pages."""
    app = setup_app(tmp_path)
    user_manager.add_user("viewer", "viewer", "viewer123")
    
    client = app.test_client()
    # Clear any leftover sessions before starting
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    
    # Test login with non-admin user
    resp = login(client, 'viewer', 'viewer123')
    assert resp.status_code == 302 # Should be a successful login, redirecting
    
    # Test access to admin page as non-admin (should be redirected)
    resp = client.get('/admin/', follow_redirects=False)
    assert resp.status_code == 302
    
    # Test access as admin
    client.get('/logout')
    resp = login(client, 'robbie', 'kangaroo123')
    assert resp.status_code == 302
    resp = client.get('/admin/', follow_redirects=False)
    assert resp.status_code == 200


def test_no_cache_header(tmp_path):
    """Tests that the no-cache header is applied correctly."""
    app = setup_app(tmp_path)
    client = app.test_client()
    # Clear any leftover sessions before starting
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])

    admin_login = login(client, 'robbie', 'kangaroo123')
    assert admin_login.status_code == 302
    client.post('/admin/security', data={'action': 'nocache_on', 'minutes': '1'})
    resp = client.get('/')
    assert resp.headers.get('Cache-Control') == 'no-store, no-cache, must-revalidate, max-age=0'


def test_login_lockout(tmp_path):
    """Tests that a non-admin user is locked out when login is disabled."""
    app = setup_app(tmp_path)
    user_manager.add_user("viewer", "viewer", "viewer123")
    
    client = app.test_client()
    # Clear any leftover sessions before starting
    for s in session_tracker.active_sessions("robbie"):
        session_tracker.remove_session("robbie", s["session_id"])
    
    admin_login = login(client, 'robbie', 'kangaroo123')
    assert admin_login.status_code == 302
    
    # Admin disables login
    client.post('/admin/security', data={'action': 'disable', 'minutes': '1'})
    client.get('/logout')
    
    # Viewer attempts to log in
    resp = login(client, 'viewer', 'viewer123')
    assert resp.status_code == 403 # Should be forbidden
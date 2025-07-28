# routes/admin_security.py
"""
Admin routes for managing site security, user access, and session tracking.

This module provides the backend for the admin dashboard, allowing administrators
to toggle login requirements, manage user accounts, and view active sessions.

INDEX
-----
1.  Imports
2.  Blueprint Setup
3.  Admin Routes
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for

from utils import security, session_tracker, user_manager
from utils.auth_decorators import role_required
import config

# ===========================================================================
# 2. Blueprint Setup
# ===========================================================================
bp = Blueprint("admin", __name__, url_prefix="/admin")


# ===========================================================================
# 3. Admin Routes
# ===========================================================================

@bp.route("/")
@role_required("admin")
def dashboard():
    """Renders the main admin dashboard page."""
    return render_template("admin/dashboard.html")


@bp.route("/security", methods=["GET", "POST"])
@role_required("admin")
def security_page():
    """Handles the security settings page for toggling login and cache control."""
    if request.method == "POST":
        action = request.form.get("action")
        minutes_str = request.form.get("minutes", "5")
        minutes = int(minutes_str) if minutes_str.isdigit() else 5

        if action == "enable":
            security.enable_login()
        elif action == "disable":
            security.disable_login_for(minutes)
        elif action == "nocache_on":
            security.enable_no_cache(minutes)
        elif action == "nocache_off":
            security.disable_no_cache()
        return redirect(url_for("admin.security_page"))

    context = {
        "login_required": security.login_required_enabled(),
        "remaining": security.remaining_minutes(),
        "no_cache": security.force_no_cache_enabled(),
        "cache_remaining": security.no_cache_remaining(),
        "active_sessions": len(session_tracker.active_sessions(config.ADMIN_USERNAME)),
        "max_sessions": session_tracker.MAX_SESSIONS,
    }
    return render_template("admin/security.html", **context)


@bp.route("/users", methods=["GET", "POST"])
@role_required("admin")
def manage_users():
    """Handles the user management page for adding and deleting users."""
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username")
        
        if action == "add" and username:
            role = request.form.get("role", "viewer")
            password = request.form.get("password", "changeme")
            user_manager.add_user(username, role, password)
        elif action == "delete" and username:
            user_manager.delete_user(username)
        
        return redirect(url_for("admin.manage_users"))

    users = user_manager.load_users()
    return render_template("admin/users.html", users=users, config=config)
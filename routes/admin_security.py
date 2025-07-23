"""Admin security routes for toggling login requirement."""
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime

from utils import security, session_tracker, user_manager
from utils.auth_decorators import role_required
import config

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@role_required("admin")
def dashboard():
    return render_template("admin/dashboard.html")


@bp.route("/security", methods=["GET", "POST"])
@role_required("admin")
def security_page():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "enable":
            security.enable_login()
        elif action == "disable":
            minutes = int(request.form.get("minutes", 5))
            security.disable_login_for(minutes)
        elif action == "nocache_on":
            minutes = int(request.form.get("minutes", 5))
            security.enable_no_cache(minutes)
        elif action == "nocache_off":
            security.disable_no_cache()
        return redirect(url_for("admin.security_page"))
    remaining = security.remaining_minutes()
    login_required = security.login_required_enabled()
    no_cache = security.force_no_cache_enabled()
    cache_remaining = security.no_cache_remaining()
    active_count = len(session_tracker.active_sessions(config.ADMIN_USERNAME))
    return render_template(
        "admin/security.html",
        login_required=login_required,
        remaining=remaining,
        no_cache=no_cache,
        cache_remaining=cache_remaining,
        expires=None,
        active=active_count,
        max_sessions=session_tracker.MAX_SESSIONS,
    )


@bp.route("/users", methods=["GET", "POST"])
@role_required("admin")
def manage_users():
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username")
        role = request.form.get("role", "viewer")
        password = request.form.get("password", "changeme")
        if action == "add" and username:
            user_manager.add_user(username, role, password)
        elif action == "delete" and username:
            user_manager.delete_user(username)
    users = user_manager.load_users()
    return render_template("admin/users.html", users=users, config=config)

"""Admin security routes for toggling login requirement."""
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime

from utils import security, session_tracker, user_manager
import config

bp = Blueprint("admin", __name__, url_prefix="/admin")


def is_admin() -> bool:
    return session.get("username") == "robbie"


@bp.route("/")
def dashboard():
    if not session.get("logged_in") or not is_admin():
        return redirect(url_for("auth.login", next=request.path))
    return render_template("admin/dashboard.html")


@bp.route("/security", methods=["GET", "POST"])
def security_page():
    if not session.get("logged_in") or not is_admin():
        return redirect(url_for("auth.login", next=request.path))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "enable":
            security.enable_login()
        elif action == "disable":
            minutes = int(request.form.get("minutes", 5))
            security.disable_login_for(minutes)
        return redirect(url_for("admin.security_page"))
    remaining = security.remaining_minutes()
    login_required = security.login_required_enabled()
    active_count = len(session_tracker.active_sessions(config.ADMIN_USERNAME))
    return render_template(
        "admin/security.html",
        login_required=login_required,
        remaining=remaining,
        expires=security.load_settings().get("expires"),
        active=active_count,
        max_sessions=session_tracker.MAX_SESSIONS,
    )


@bp.route("/users", methods=["GET", "POST"])
def manage_users():
    if not session.get("logged_in") or not is_admin():
        return redirect(url_for("auth.login", next=request.path))
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username")
        role = request.form.get("role", "user")
        if action == "add" and username:
            user_manager.add_user(username, role)
        elif action == "delete" and username:
            user_manager.delete_user(username)
    users = user_manager.load_users()
    return render_template("admin/users.html", users=users, config=config)

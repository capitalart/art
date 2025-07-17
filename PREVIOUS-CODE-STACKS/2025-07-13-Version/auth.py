"""Authentication blueprint for the ART Narrator application.

This module provides login and logout functionality, session tracking and
basic safe URL validation. It logs all login attempts to ``login_attempts.log``
within the configured ``LOGS_DIR``.
"""

from __future__ import annotations

import datetime
import hmac
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse, urljoin

from routes.session_tracker import register_session, remove_session

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app

import config

bp = Blueprint("auth", __name__)

ATTEMPT_LOG = config.LOGS_DIR / "login_attempts.log"


def _log_attempt(username: str, addr: str, success: bool) -> None:
    """Record a login attempt.

    Parameters
    ----------
    username:
        The supplied username.
    addr:
        Remote address of the request.
    success:
        ``True`` if the login was successful, otherwise ``False``.
    """

    ATTEMPT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ATTEMPT_LOG, "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.utcnow().isoformat()
        status = "SUCCESS" if success else "FAIL"
        f.write(f"{timestamp}\t{addr}\t{username}\t{status}\n")


def _is_safe_url(target: str) -> bool:
    """Return ``True`` if ``target`` is a safe local redirect destination."""

    if not target:
        return False
    host_url = request.host_url
    ref = urlparse(urljoin(host_url, target))
    return ref.scheme in {"http", "https"} and ref.netloc == urlparse(host_url).netloc


@bp.route("/login", methods=["GET", "POST"])
def login() -> str:
    """Render the login form and handle authentication."""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        next_url = request.form.get("next")
        admin_user = os.getenv("ADMIN_USER", "robbie")
        admin_pass = os.getenv("ADMIN_PASS", "")
        ok = hmac.compare_digest(username, admin_user) and hmac.compare_digest(password, admin_pass)
        _log_attempt(username, request.remote_addr or "", ok)
        if ok:
            token = str(uuid.uuid4())
            if not register_session(admin_user, token):
                flash("Maximum active sessions reached. Please log out from another device first.", "danger")
                return render_template("auth/login.html", next=next_url), 403
            session.clear()
            session["user"] = admin_user
            session["role"] = "admin"
            session["token"] = token
            session.permanent = True
            if next_url and _is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for("artwork.home"))
        flash("Invalid credentials", "danger")
        return render_template("auth/login.html", next=next_url), 401
    next_url = request.args.get("next")
    return render_template("auth/login.html", next=next_url)


@bp.route("/logout")
def logout() -> str:
    """Terminate the current session and return to the login page."""
    token = session.get("token")
    user = session.get("user")
    if token and user:
        remove_session(user, token)
    session.clear()
    flash("Logged out", "success")
    return redirect(url_for("auth.login"))


@bp.route("/account")
def account() -> str:
    """Display basic account info if logged in."""
    if not session.get("user"):
        return redirect(url_for("auth.login"))
    return render_template("account.html")

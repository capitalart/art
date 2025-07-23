"""Authentication routes for ArtNarrator."""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils import security, session_tracker
import uuid
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from datetime import datetime
import config
from db import SessionLocal, User

load_dotenv()

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Display and handle the login form."""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        with SessionLocal() as db_session:
            user = db_session.query(User).filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                if not security.login_required_enabled() and user.role != "admin":
                    flash("Site locked by admin", "danger")
                    return render_template("login.html"), 403
                token = str(uuid.uuid4())
                if not session_tracker.register_session(username, token):
                    flash(
                        "Maximum login limit reached (5 devices). Log out on another device to continue.",
                        "danger",
                    )
                    return render_template("login.html"), 403
                session["logged_in"] = True
                session["username"] = username
                session["role"] = user.role
                session["session_id"] = token
                user.last_login = datetime.utcnow()
                db_session.commit()
                next_page = request.args.get("next") or url_for("artwork.home")
                return redirect(next_page)
        flash("Invalid username or password", "danger")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    """Clear session and redirect to login."""
    token = session.get("session_id")
    username = session.get("username")
    if token and username:
        session_tracker.remove_session(username, token)
    session.clear()
    return redirect(url_for("auth.login"))

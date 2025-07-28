# routes/auth_routes.py
"""
Authentication routes for the ArtNarrator application.
Handles user login, session creation, and logout.

INDEX
-----
1.  Imports
2.  Blueprint Setup
3.  Authentication Routes
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import logging
import uuid
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

import config
from db import SessionLocal, User
from utils import security, session_tracker

logger = logging.getLogger(__name__)

# ===========================================================================
# 2. Blueprint Setup
# ===========================================================================
bp = Blueprint("auth", __name__)


# ===========================================================================
# 3. Authentication Routes
# ===========================================================================

@bp.route("/login", methods=["GET", "POST"])
def login():
    """Display and handle the user login form."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        with SessionLocal() as db_session:
            user = db_session.query(User).filter_by(username=username).first()
            
            if user and check_password_hash(user.password_hash, password):
                # Check if site is locked by admin (and user is not an admin)
                if not security.login_required_enabled() and user.role != "admin":
                    logger.warning(f"Login attempt by '{username}' failed: Site is locked by admin.")
                    flash("Site is currently locked by an administrator.", "danger")
                    return render_template("login.html"), 403

                # Register session and check against device limit
                token = str(uuid.uuid4())
                if not session_tracker.register_session(username, token):
                    logger.warning(f"Login attempt by '{username}' failed: Maximum session limit reached.")
                    flash("Maximum login limit reached. Please log out on another device to continue.", "danger")
                    return render_template("login.html"), 403

                # Set session variables
                session["logged_in"] = True
                session["username"] = username
                session["role"] = user.role
                session["session_id"] = token
                
                # Update user's last login time in DB
                user.last_login = datetime.utcnow()
                db_session.commit()
                
                logger.info(f"Successful login for user '{username}' with role '{user.role}'.")
                
                next_page = request.args.get("next") or url_for("artwork.home")
                return redirect(next_page)

        logger.warning(f"Failed login attempt for username: '{username}'.")
        flash("Invalid username or password.", "danger")
        
    return render_template("login.html")


@bp.route("/logout")
def logout():
    """Clear the user session and log the user out."""
    token = session.get("session_id")
    username = session.get("username")
    
    if token and username:
        session_tracker.remove_session(username, token)
        logger.info(f"User '{username}' logged out and session '{token}' was removed.")
        
    session.clear()
    return redirect(url_for("auth.login"))
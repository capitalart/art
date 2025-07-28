# utils/auth_decorators.py
"""
Authentication and authorization decorators for Flask routes.

These decorators provide a simple way to protect endpoints by ensuring
the user is logged in and has the required role.

INDEX
-----
1.  Imports
2.  Decorator Functions
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import logging
from functools import wraps

from flask import session, redirect, url_for, request

logger = logging.getLogger(__name__)

# ===========================================================================
# 2. Decorator Functions
# ===========================================================================

def role_required(role: str):
    """
    A decorator to ensure the logged-in user has a specific role.

    If the user is not logged in or does not have the required role, they are
    redirected to the login page.

    Usage:
        @bp.route("/admin")
        @role_required("admin")
        def admin_dashboard():
            return "Welcome, admin!"

    Args:
        role: The role string required to access the endpoint (e.g., "admin").
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_role = session.get("role")
            if user_role != role:
                username = session.get("username", "Anonymous")
                logger.warning(
                    f"Role-based access denied for user '{username}' (role: '{user_role}') "
                    f"to endpoint '{request.endpoint}'. Required role: '{role}'."
                )
                return redirect(url_for("auth.login", next=request.path))
            return func(*args, **kwargs)
        return wrapper
    return decorator
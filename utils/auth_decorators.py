"""Authentication and authorization decorators."""

from __future__ import annotations

from functools import wraps
from flask import session, redirect, url_for, request


def role_required(role: str):
    """Ensure the logged-in user has the specified role."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                return redirect(url_for("auth.login", next=request.path))
            return func(*args, **kwargs)

        return wrapper

    return decorator


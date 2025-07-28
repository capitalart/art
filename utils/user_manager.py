# utils/user_manager.py
"""
Database-backed user management utilities.

This module provides a set of functions to interact with the User model
in the database, allowing for the creation, deletion, and modification of
user accounts.

INDEX
-----
1.  Imports
2.  User Management Functions
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import logging

from werkzeug.security import generate_password_hash

from db import SessionLocal, User

logger = logging.getLogger(__name__)


# ===========================================================================
# 2. User Management Functions
# ===========================================================================

def load_users() -> list[User]:
    """Return all users from the database."""
    with SessionLocal() as session:
        return session.query(User).all()


def add_user(username: str, role: str = "viewer", password: str = "changeme") -> None:
    """Create a new user if one with the same username does not already exist."""
    with SessionLocal() as session:
        if session.query(User).filter_by(username=username).first():
            logger.warning(f"Attempted to add existing user '{username}'. No action taken.")
            return
            
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
        )
        session.add(user)
        session.commit()
        logger.info(f"Successfully added new user '{username}' with role '{role}'.")


def delete_user(username: str) -> None:
    """Delete a user from the database by their username."""
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user:
            session.delete(user)
            session.commit()
            logger.info(f"Successfully deleted user '{username}'.")
        else:
            logger.warning(f"Attempted to delete non-existent user '{username}'.")


def set_role(username: str, role: str) -> None:
    """Update a user's role in the database."""
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user:
            user.role = role
            session.commit()
            logger.info(f"Successfully changed role for user '{username}' to '{role}'.")
        else:
            logger.warning(f"Attempted to set role for non-existent user '{username}'.")
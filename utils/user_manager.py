"""Database-backed user management utilities."""

from __future__ import annotations

from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from db import SessionLocal, User


def load_users() -> list[User]:
    """Return all users."""
    with SessionLocal() as session:
        return session.query(User).all()


def add_user(username: str, role: str = "viewer", password: str = "changeme") -> None:
    """Create a new user if not exists."""
    with SessionLocal() as session:
        if session.query(User).filter_by(username=username).first():
            return
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
        )
        session.add(user)
        session.commit()


def delete_user(username: str) -> None:
    """Delete a user by username."""
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user:
            session.delete(user)
            session.commit()


def set_role(username: str, role: str) -> None:
    """Update a user's role."""
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user:
            user.role = role
            session.commit()

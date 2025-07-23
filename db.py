"""Database initialization and models for ArtNarrator."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import config

DB_PATH = config.DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

Base = declarative_base()


class User(Base):
    """Application user model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    email = Column(String, nullable=True)
    role = Column(String, default="viewer", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)


class SiteSettings(Base):
    """Model storing login/cache settings."""

    __tablename__ = "site_settings"

    id = Column(Integer, primary_key=True)
    login_enabled = Column(Boolean, default=True)
    login_override_until = Column(DateTime, nullable=True)
    force_no_cache = Column(Boolean, default=False)
    force_no_cache_until = Column(DateTime, nullable=True)


def init_db() -> None:
    """Create database tables and seed initial data."""
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if not session.query(User).first():
            from werkzeug.security import generate_password_hash

            admin = User(
                username=config.ADMIN_USERNAME,
                password_hash=generate_password_hash(config.ADMIN_PASSWORD),
                email=config.ADMIN_EMAIL,
                role="admin",
            )
            editor = User(
                username="editor",
                password_hash=generate_password_hash("editor123"),
                email="editor@example.com",
                role="editor",
            )
            viewer = User(
                username="viewer",
                password_hash=generate_password_hash("viewer123"),
                email="viewer@example.com",
                role="viewer",
            )
            session.add_all([admin, editor, viewer])
        if not session.query(SiteSettings).first():
            session.add(SiteSettings())
        session.commit()


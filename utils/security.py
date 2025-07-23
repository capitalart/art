"""Site security helpers backed by the SQLite database."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from db import SessionLocal, SiteSettings


def _get_settings(session: Session) -> SiteSettings:
    settings = session.query(SiteSettings).first()
    if not settings:
        settings = SiteSettings()
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def login_required_enabled() -> bool:
    """Return True if login is currently required."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        if not settings.login_enabled:
            if settings.login_override_until and settings.login_override_until <= datetime.utcnow():
                settings.login_enabled = True
                settings.login_override_until = None
                session.commit()
        return settings.login_enabled


def disable_login_for(minutes: int) -> None:
    """Disable login for all non-admins for a period."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.login_enabled = False
        settings.login_override_until = datetime.utcnow() + timedelta(minutes=minutes)
        session.commit()


def enable_login() -> None:
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.login_enabled = True
        settings.login_override_until = None
        session.commit()


def remaining_minutes() -> int | None:
    """Return minutes left until login re-enables or None."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        if settings.login_override_until:
            delta = settings.login_override_until - datetime.utcnow()
            return max(int(delta.total_seconds() // 60), 0)
        return None


def force_no_cache_enabled() -> bool:
    """Return True if no-cache headers should be sent."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        if settings.force_no_cache and settings.force_no_cache_until and settings.force_no_cache_until <= datetime.utcnow():
            settings.force_no_cache = False
            settings.force_no_cache_until = None
            session.commit()
        return settings.force_no_cache


def enable_no_cache(minutes: int) -> None:
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.force_no_cache = True
        settings.force_no_cache_until = datetime.utcnow() + timedelta(minutes=minutes)
        session.commit()


def disable_no_cache() -> None:
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.force_no_cache = False
        settings.force_no_cache_until = None
        session.commit()


def no_cache_remaining() -> int | None:
    with SessionLocal() as session:
        settings = _get_settings(session)
        if settings.force_no_cache and settings.force_no_cache_until:
            delta = settings.force_no_cache_until - datetime.utcnow()
            return max(int(delta.total_seconds() // 60), 0)
        return None

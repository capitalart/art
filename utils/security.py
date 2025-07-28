# utils/security.py
"""
Site security helpers backed by the SQLite database.

This module provides functions to dynamically enable or disable application-wide
security features like login requirements and browser caching by modifying
records in the database.

INDEX
-----
1.  Imports
2.  Database Helper
3.  Login Security Functions
4.  Cache Control Functions
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from db import SessionLocal, SiteSettings

logger = logging.getLogger(__name__)


# ===========================================================================
# 2. Database Helper
# ===========================================================================

def _get_settings(session: Session) -> SiteSettings:
    """
    Retrieves the site settings object from the database, creating it with
    default values if it doesn't exist.

    Args:
        session: The active SQLAlchemy session.

    Returns:
        The SiteSettings ORM object.
    """
    settings = session.query(SiteSettings).first()
    if not settings:
        logger.info("No site settings found in database; creating new default record.")
        settings = SiteSettings()
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


# ===========================================================================
# 3. Login Security Functions
# ===========================================================================

def login_required_enabled() -> bool:
    """
    Checks if login is currently required.

    This function also automatically re-enables the login requirement if a
    temporary override period has expired.

    Returns:
        True if login is required, False otherwise.
    """
    with SessionLocal() as session:
        settings = _get_settings(session)
        if not settings.login_enabled:
            # Check if the override period has expired
            if settings.login_override_until and settings.login_override_until <= datetime.utcnow():
                logger.info("Login override has expired. Re-enabling login requirement.")
                settings.login_enabled = True
                settings.login_override_until = None
                session.commit()
        return settings.login_enabled


def disable_login_for(minutes: int) -> None:
    """
    Disables the login requirement for all non-admins for a set duration.

    Args:
        minutes: The number of minutes to disable the login requirement for.
    """
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.login_enabled = False
        settings.login_override_until = datetime.utcnow() + timedelta(minutes=minutes)
        session.commit()
        logger.warning(f"ADMIN ACTION: Login requirement has been disabled for {minutes} minutes.")


def enable_login() -> None:
    """Immediately re-enables the login requirement for all non-admins."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.login_enabled = True
        settings.login_override_until = None
        session.commit()
        logger.info("ADMIN ACTION: Login requirement has been re-enabled.")


def remaining_minutes() -> int | None:
    """
    Calculates the remaining minutes until a login override expires.

    Returns:
        The number of whole minutes remaining, or None if no override is active.
    """
    with SessionLocal() as session:
        settings = _get_settings(session)
        if settings.login_override_until and not settings.login_enabled:
            delta = settings.login_override_until - datetime.utcnow()
            return max(int(delta.total_seconds() // 60), 0)
        return None


# ===========================================================================
# 4. Cache Control Functions
# ===========================================================================

def force_no_cache_enabled() -> bool:
    """
    Checks if 'no-cache' headers should be forced on responses.

    Automatically disables the override if its timer has expired.

    Returns:
        True if 'no-cache' headers should be forced, False otherwise.
    """
    with SessionLocal() as session:
        settings = _get_settings(session)
        if settings.force_no_cache and settings.force_no_cache_until and settings.force_no_cache_until <= datetime.utcnow():
            logger.info("Force 'no-cache' override has expired. Disabling.")
            settings.force_no_cache = False
            settings.force_no_cache_until = None
            session.commit()
        return settings.force_no_cache


def enable_no_cache(minutes: int) -> None:
    """
    Forces the 'no-cache' header on all responses for a specified duration.

    Args:
        minutes: The number of minutes to force 'no-cache' headers.
    """
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.force_no_cache = True
        settings.force_no_cache_until = datetime.utcnow() + timedelta(minutes=minutes)
        session.commit()
        logger.warning(f"ADMIN ACTION: Force 'no-cache' has been enabled for {minutes} minutes.")


def disable_no_cache() -> None:
    """Immediately disables the 'no-cache' header override."""
    with SessionLocal() as session:
        settings = _get_settings(session)
        settings.force_no_cache = False
        settings.force_no_cache_until = None
        session.commit()
        logger.info("ADMIN ACTION: Force 'no-cache' has been disabled.")


def no_cache_remaining() -> int | None:
    """
    Calculates the remaining minutes until a 'no-cache' override expires.

    Returns:
        The number of whole minutes remaining, or None if no override is active.
    """
    with SessionLocal() as session:
        settings = _get_settings(session)
        if settings.force_no_cache and settings.force_no_cache_until:
            delta = settings.force_no_cache_until - datetime.utcnow()
            return max(int(delta.total_seconds() // 60), 0)
        return None
# db.py
"""
Database setup and ORM model definitions for the ArtNarrator application.

This module initializes the SQLAlchemy engine, session management, and defines
all database tables as ORM classes using the declarative base.

INDEX
-----
1.  Imports
2.  Database Setup & Configuration
3.  ORM Model Definitions
4.  Database Initialisation Function
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
from __future__ import annotations
import logging
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

from werkzeug.security import generate_password_hash
import config

logger = logging.getLogger(__name__)

# ===========================================================================
# 2. Database Setup & Configuration
# ===========================================================================

# Use the DB_PATH from the central config file
DATABASE_URL = f"sqlite:///{config.DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ===========================================================================
# 3. ORM Model Definitions
# ===========================================================================

class User(Base):
    """Represents a user account in the database."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="viewer", nullable=False)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class SiteSettings(Base):
    """Represents global site security settings stored in the database."""
    __tablename__ = "site_settings"
    id = Column(Integer, primary_key=True)
    login_enabled = Column(Boolean, default=True)
    login_override_until = Column(DateTime, nullable=True)
    force_no_cache = Column(Boolean, default=False)
    force_no_cache_until = Column(DateTime, nullable=True)


# ===========================================================================
# 4. Database Initialisation Function
# ===========================================================================

def init_db():
    """
    Creates all database tables defined in the models.
    If the users table is empty, it creates a default admin user from config.
    """
    try:
        Base.metadata.create_all(bind=engine)
        
        with SessionLocal() as session:
            # Check if any user exists
            if session.query(User).first() is None:
                logger.info("Users table is empty. Creating default admin user.")
                admin_user = User(
                    username=config.ADMIN_USERNAME,
                    password_hash=generate_password_hash(config.ADMIN_PASSWORD),
                    role="admin"
                )
                session.add(admin_user)
                session.commit()
                logger.info(f"Default admin user '{config.ADMIN_USERNAME}' created successfully.")
    except Exception as e:
        logger.critical(f"FATAL: Could not initialize database at {config.DB_PATH}: {e}", exc_info=True)
        raise
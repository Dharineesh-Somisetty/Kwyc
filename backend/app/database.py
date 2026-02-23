"""LabelLens – database setup via SQLAlchemy (SQLite + Postgres-ready).

Set DATABASE_URL env var to switch backends:
  - SQLite  (default): sqlite:///./labellens.db
  - Postgres:          postgresql://user:pass@host:5432/labellens
"""

from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./labellens.db")

# SQLite needs check_same_thread=False; Postgres does not support it.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


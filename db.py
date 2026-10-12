import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def normalize_database_url(url: str) -> str:
    """Rewrite `postgres://` and driverless `postgresql://` to use psycopg2.

    Render's `fromDatabase.connectionString` yields `postgres://`, and a bare
    `postgresql://` names no driver either. SQLAlchemy 2.1 changed the
    default driver for both to psycopg (v3), but this repo depends on
    psycopg2-binary, so we pin the driver explicitly to `psycopg2` to avoid
    breaking on that upgrade. Schemes that already name a driver
    (`postgresql+xxx://`) or aren't postgres (`sqlite:///`, ...) are
    returned unchanged.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def get_sqlalchemy_echo() -> bool:
    return os.getenv("SQLALCHEMY_ECHO", "").strip().lower() in {"1", "true", "yes", "on"}


def create_database_engine(database_url: str) -> Engine:
    return create_engine(
        normalize_database_url(database_url),
        echo=get_sqlalchemy_echo(),
        pool_pre_ping=True,
    )


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Please export DATABASE_URL before starting the app or running database scripts."
    )
DATABASE_URL = normalize_database_url(DATABASE_URL)


engine = create_database_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

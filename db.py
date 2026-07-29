import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def normalize_database_url(url: str) -> str:
    """Rewrite the legacy `postgres://` scheme to `postgresql://`.

    Render's `fromDatabase.connectionString` yields `postgres://`, which the
    SQLAlchemy version pinned in this repo no longer recognizes as a dialect
    (raises NoSuchModuleError). Only the scheme prefix is replaced; other
    schemes (`postgresql://`, `sqlite:///`, ...) are returned unchanged.
    """
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
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

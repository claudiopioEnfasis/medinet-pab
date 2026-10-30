"""Configuración de conexión y sesiones SQLAlchemy."""
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def _database_url():
    # DATABASE_URL solo se usa para pruebas automatizadas (SQLite).
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit
    required = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "DB_HOST")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Faltan variables de conexión: {', '.join(missing)}")
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=5432,
        database=os.environ["POSTGRES_DB"],
    )


engine = create_engine(_database_url(), pool_pre_ping=True, hide_parameters=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

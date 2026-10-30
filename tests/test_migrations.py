"""Migraciones Alembic: se preserva el dato y también funciona en BD vacía."""
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from app.db import Base
import app.models  # noqa: F401


def test_v03_baseline_preserves_existing_data(tmp_path):
    file = tmp_path / "legacy-v03.sqlite3"
    url = f"sqlite:///{file}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO operating_rooms (id,code,name,status) VALUES (17,'PAB-17','Sala anterior','available')"))
    engine.dispose()
    env = {**os.environ, "DATABASE_URL": url}
    cwd = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-m", "scripts.migrate"], cwd=cwd, env=env,
                            capture_output=True, text=True, timeout=30, check=True)
    assert "baseline" in result.stdout.lower()
    engine = create_engine(url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT code FROM operating_rooms WHERE id=17")).scalar() == "PAB-17"
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"
    engine.dispose()


def test_fresh_migration_builds_initial_schema(tmp_path):
    file = tmp_path / "fresh.sqlite3"
    url = f"sqlite:///{file}"
    env = {**os.environ, "DATABASE_URL": url}
    cwd = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, "-m", "scripts.migrate"], cwd=cwd, env=env,
                   capture_output=True, text=True, timeout=30, check=True)
    engine = create_engine(url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"
    engine.dispose()

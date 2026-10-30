"""Ensayo de Alembic, grants mínimos y API con conexión runtime real."""
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.main import app
from app.models import AppUser
from app.security import hash_password


@pytest.mark.postgres
def test_migrations_and_runtime_least_privilege(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requiere PostgreSQL desechable y rol administrativo de pruebas")
    admin = create_engine(url)
    assert admin.dialect.name == "postgresql"
    assert admin.url.database.endswith(("_test", "_ci"))
    assert url != os.getenv("DATABASE_URL")
    # BD separada: no contaminar el seed/migraciones que CI ejecuta después.
    database = "permissions_" + uuid4().hex + "_test"
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f'CREATE DATABASE "{database}"'))
    permissions_url = admin.url.set(database=database)
    admin.dispose()
    admin = create_engine(permissions_url, hide_parameters=True)
    password = secrets.token_hex(32)
    env = {**os.environ, "DATABASE_URL": permissions_url.render_as_string(hide_password=False)}
    cwd = Path(__file__).resolve().parents[1]
    def command(*args, **kwargs):
        result = subprocess.run([sys.executable, *args], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=60, **kwargs)
        # No volcar stderr de drivers que pudieran incluir parámetros privados.
        if result.returncode:
            pytest.fail(f"Falló comando de {args[0]} (salida privada)", pytrace=False)
        return result
    command("-m", "scripts.migrate")
    command("-m", "alembic", "check")
    from scripts import db_privileges
    role = "runtime_" + uuid4().hex
    monkeypatch.setattr(db_privileges, "engine", admin)
    monkeypatch.setattr(db_privileges, "RUNTIME_ROLE", role)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"password": password})))
    db_privileges.provision(create=True)
    db_privileges.provision()
    Session = sessionmaker(bind=admin)
    with Session.begin() as db:
        db.add(AppUser(username="runtime_test", role="admin", password_hash=hash_password("runtime-test-password")))
    runtime = create_engine(admin.url.set(username=role, password=password), hide_parameters=True)
    RuntimeSession = sessionmaker(bind=runtime, expire_on_commit=False)
    try:
        with runtime.connect() as conn:
            flags = conn.execute(text("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()
            assert not any(flags)
        for forbidden in (
            "CREATE TABLE public.forbidden_table (id integer)",
            "CREATE TEMP TABLE forbidden_temp (id integer)",
            "CREATE SCHEMA forbidden_schema",
            "DELETE FROM patients WHERE id=-1",
            "UPDATE app_users SET role='admin' WHERE id=-1",
            "UPDATE app_users SET password_hash='forbidden' WHERE id=-1",
            "INSERT INTO app_users DEFAULT VALUES",
            "UPDATE alembic_version SET version_num='forbidden'",
        ):
            with pytest.raises(DBAPIError) as caught:
                with runtime.begin() as conn:
                    conn.execute(text(forbidden))
            assert caught.value.orig.sqlstate == "42501"
        def override():
            with RuntimeSession() as db:
                yield db
        app.dependency_overrides[get_db] = override
        with TestClient(app) as client:
            result = client.post("/auth/login", json={"username": "runtime_test", "password": "runtime-test-password"})
            assert result.status_code == 200
            client.headers["Authorization"] = "Bearer " + result.json()["access_token"]
            assert client.get("/health/ready").status_code == 200
            room = client.post("/operating-rooms", json={"code": "RT-01", "name": "Sala runtime"}).json()
            patient = client.post("/patients", json={"reference": "RT-P1", "full_name": "Demo runtime"}).json()
            staff = client.post("/medical-staff", json={"reference": "RT-M1", "full_name": "Demo runtime", "specialty": "Cirugía"}).json()
            body = dict(room_id=room["id"], patient_id=patient["id"], staff_ids=[staff["id"]],
                        starts_at="2026-11-05T10:00:00-03:00", ends_at="2026-11-05T12:00:00-03:00", procedure="Prueba runtime")
            created = client.post("/surgeries", json=body)
            assert created.status_code == 201
            sid = created.json()["id"]
            assert client.post("/surgeries", json=body).status_code == 409
            for status in ("in_progress", "completed"):
                assert client.patch(f"/surgeries/{sid}/status", json={"status": status}).status_code == 200
            assert client.get("/surgeries").status_code == 200
            assert client.post("/auth/login", json={"username": "runtime_test", "password": "wrong"}).status_code == 401
        command("-m", "scripts.migrate")
        command("-m", "alembic", "check")
    finally:
        app.dependency_overrides.clear()
        runtime.dispose()
        admin.dispose()

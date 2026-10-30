"""Seguridad e idempotencia del seed contra PostgreSQL real y esquemas aislados."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from itertools import combinations
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AppUser, MedicalStaff, OperatingRoom, Patient, Surgery
from scripts import seed_demo

NOW = datetime(2026, 10, 30, 10, tzinfo=ZoneInfo("America/Santiago"))


@pytest.fixture
def seed_session():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("El seed se comprueba exclusivamente en PostgreSQL de pruebas")
    admin = create_engine(url)
    assert admin.dialect.name == "postgresql"
    assert admin.url.database.endswith(("_test", "_ci"))
    assert url != os.getenv("DATABASE_URL")
    schema = "seed_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    pg = create_engine(url, connect_args={"options": "-csearch_path=" + schema})
    Base.metadata.create_all(pg)
    try:
        yield sessionmaker(bind=pg, expire_on_commit=False, autoflush=False)
    finally:
        pg.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def snapshot(factory):
    with factory() as db:
        return {name: [dict(row) for row in db.execute(table.select()).mappings()]
                for name, table in Base.metadata.tables.items()}


@pytest.mark.postgres
def test_seed_complete_demo_and_four_states(seed_session):
    result = seed_demo.seed(seed_session, now=NOW)
    assert result["totales"] == {"pabellones": 8, "pacientes": 15, "profesionales": 10, "cirugias": 12}
    assert result["omitidos"] == []
    with seed_session() as db:
        rooms = db.scalars(select(OperatingRoom)).all()
        assert {r.code for r in rooms} == {f"PAB-{i:02d}" for i in range(1, 9)}
        assert {r.status for r in rooms} == {"available", "occupied", "sanitizing", "maintenance"}
        surgeries = db.scalars(select(Surgery)).all()
        assert sum(s.status == "in_progress" for s in surgeries) == 2
        assert {s.urgency for s in surgeries} == {"elective", "emergency"}
        assert db.scalar(select(AppUser.id)) is None


@pytest.mark.postgres
def test_seed_rerun_next_day_changes_no_records(seed_session):
    seed_demo.seed(seed_session, now=NOW)
    before = snapshot(seed_session)
    result = seed_demo.seed(seed_session, now=NOW + timedelta(days=1))
    assert all(value == 0 for value in result["creados"].values())
    assert result["ejemplos_conservados"] == 12
    assert snapshot(seed_session) == before


@pytest.mark.postgres
def test_seed_preserves_existing_resources_and_user(seed_session):
    with seed_session.begin() as db:
        db.add_all([
            OperatingRoom(code="PAB-01", name="Sala anterior", status="maintenance"),
            Patient(reference="DEMO-P01", full_name="Paciente anterior ficticio"),
            MedicalStaff(reference="DEMO-M01", full_name="Profesional anterior ficticio", specialty="Especialidad anterior"),
            AppUser(username="original", role="viewer", password_hash="sentinel-hash-unchanged", failed_logins=2),
        ])
    before = snapshot(seed_session)
    result = seed_demo.seed(seed_session, now=NOW)
    after = snapshot(seed_session)
    for table, rows in before.items():
        for row in rows:
            assert row in after[table]
    assert result["omitidos"]


@pytest.mark.postgres
def test_seed_no_overlapping_room_patient_or_staff(seed_session):
    seed_demo.seed(seed_session, now=NOW)
    with seed_session() as db:
        surgeries = db.scalars(select(Surgery)).all()
        for first, second in combinations(surgeries, 2):
            if first.starts_at < second.ends_at and first.ends_at > second.starts_at:
                assert first.room_id != second.room_id
                assert first.patient_id != second.patient_id
                assert not ({m.id for m in first.staff} & {m.id for m in second.staff})


@pytest.mark.postgres
def test_seed_failure_rolls_back_every_insert(seed_session, monkeypatch):
    before = snapshot(seed_session)
    def fail(*args, **kwargs):
        raise RuntimeError("Fallo simulado antes del commit")
    monkeypatch.setattr(seed_demo, "_create_surgery", fail)
    with pytest.raises(RuntimeError, match="Fallo simulado"):
        seed_demo.seed(seed_session, now=NOW)
    assert snapshot(seed_session) == before


@pytest.mark.postgres
def test_two_seeds_are_serialized_without_duplicates(seed_session):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: seed_demo.seed(seed_session, now=NOW), range(2)))
    assert all(result["totales"]["cirugias"] == 12 for result in results)
    assert sorted(result["creados"]["surgeries"] for result in results) == [0, 12]


def test_seed_refuses_sqlite():
    engine = create_engine("sqlite:///:memory:")
    try:
        with pytest.raises(RuntimeError, match="PostgreSQL real"):
            seed_demo.seed(sessionmaker(bind=engine), now=NOW)
    finally:
        engine.dispose()

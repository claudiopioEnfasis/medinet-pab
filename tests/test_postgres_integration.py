"""Pruebas reales PostgreSQL (requerido TEST_DATABASE_URL) con reservas concurrentes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from app.db import get_db
from app.main import app
from app.models import OperatingRoom, Patient, MedicalStaff, AppUser
from app.security import hash_password, make_token
from test_seed_demo import seed_session  # PostgreSQL: esquema aislado, preserva Alembic/public


@pytest.mark.postgres
def test_postgres_parallel_reservations(seed_session):
    Session = seed_session
    try:
        with Session.begin() as session:
            room = OperatingRoom(code="PG-TEST", name="Sala PG", status="available")
            session.add(room)
            p1, p2 = Patient(reference="PG-P1", full_name="Paciente Demo Uno"), Patient(reference="PG-P2", full_name="Paciente Demo Dos")
            d1, d2 = MedicalStaff(reference="PG-D1", full_name="Profesional Uno", specialty="Cirugía"), MedicalStaff(reference="PG-D2", full_name="Profesional Dos", specialty="Cirugía")
            user = AppUser(username="admin_pg", role="admin", password_hash=hash_password("demo-password-test-123"))
            session.add_all([p1, p2, d1, d2, user])
            session.flush()
            room_id, pids, dids, uid = room.id, [p1.id, p2.id], [d1.id, d2.id], user.id
        with Session() as session:
            token, _ = make_token(session.get(AppUser, uid))
        def override_db():
            with Session() as session:
                yield session
        app.dependency_overrides[get_db] = override_db
        gate = Barrier(2)
        def attempt(n):
            gate.wait(timeout=10)
            with TestClient(app) as client:
                return client.post("/surgeries", headers={"Authorization": f"Bearer {token}"}, json={
                    "room_id": room_id, "patient_id": pids[n], "staff_ids": [dids[n]],
                    "starts_at": "2026-11-05T10:00:00-03:00", "ends_at": "2026-11-05T12:00:00-03:00",
                    "procedure": "Prueba de concurrencia", "urgency": "elective"
                }).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        assert sorted(results) == [201, 409], results
    finally:
        app.dependency_overrides.clear()

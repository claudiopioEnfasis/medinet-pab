"""Carreras reales: recursos compartidos, transiciones y bloqueo de login."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import AppUser, MedicalStaff, OperatingRoom, Patient
from app.security import hash_password, make_token
from test_seed_demo import seed_session  # fixture: esquema PostgreSQL aislado


@pytest.fixture
def postgres_client(seed_session):
    with seed_session.begin() as db:
        db.add_all([
            OperatingRoom(id=i, code=f"R-{i}", name=f"Sala {i}", status="available") for i in (1, 2)
        ] + [Patient(id=i, reference=f"P-{i}", full_name=f"Demo {i}") for i in (1, 2)]
          + [MedicalStaff(id=i, reference=f"M-{i}", full_name=f"Demo {i}", specialty="Cirugía") for i in (1, 2)]
          + [AppUser(id=1, username="parallel", role="admin", password_hash=hash_password("parallel-test-password"))])
    with seed_session() as db:
        token, _ = make_token(db.get(AppUser, 1))
    def override():
        with seed_session() as db:
            yield db
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            client.headers["Authorization"] = f"Bearer {token}"
            yield client, seed_session
    finally:
        app.dependency_overrides.clear()


def concurrent(*operations):
    barrier = Barrier(len(operations))
    def attempt(operation):
        barrier.wait(timeout=15)
        return operation().status_code
    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return sorted(pool.map(attempt, operations))


def payload(room=1, patient=1, staff=1, later=False):
    return dict(room_id=room, patient_id=patient, staff_ids=[staff], procedure="Concurrencia real",
                starts_at=f"2026-11-05T{'12' if later else '10'}:00:00-03:00",
                ends_at=f"2026-11-05T{'14' if later else '12'}:00:00-03:00")


@pytest.mark.postgres
@pytest.mark.parametrize("resource", ["room", "patient", "staff"])
def test_parallel_reservations_each_resource(postgres_client, resource):
    client, _ = postgres_client
    other = payload(room=1 if resource == "room" else 2,
                    patient=1 if resource == "patient" else 2,
                    staff=1 if resource == "staff" else 2)
    assert concurrent(lambda: client.post("/surgeries", json=payload()),
                      lambda: client.post("/surgeries", json=other)) == [201, 409]
    assert len(client.get("/surgeries").json()) == 1


@pytest.mark.postgres
@pytest.mark.parametrize("resource", ["patient", "staff"])
def test_parallel_start_shared_resource(postgres_client, resource):
    client, _ = postgres_client
    first = client.post("/surgeries", json=payload()).json()["id"]
    second = client.post("/surgeries", json=payload(room=2, later=True,
                         patient=1 if resource == "patient" else 2,
                         staff=1 if resource == "staff" else 2)).json()["id"]
    assert concurrent(lambda: client.patch(f"/surgeries/{first}/status", json={"status": "in_progress"}),
                      lambda: client.patch(f"/surgeries/{second}/status", json={"status": "in_progress"})) == [200, 409]


@pytest.mark.postgres
def test_parallel_status_same_surgery(postgres_client):
    client, _ = postgres_client
    sid = client.post("/surgeries", json=payload()).json()["id"]
    assert concurrent(lambda: client.patch(f"/surgeries/{sid}/status", json={"status": "in_progress"}),
                      lambda: client.patch(f"/surgeries/{sid}/status", json={"status": "in_progress"})) == [200, 409]


@pytest.mark.postgres
def test_parallel_failed_logins_cannot_bypass_lock(postgres_client):
    client, factory = postgres_client
    def wrong():
        return client.post("/auth/login", json={"username": "parallel", "password": "wrong"})
    assert concurrent(*([wrong] * 8)) == [401] * 8
    assert client.post("/auth/login", json={"username": "parallel", "password": "parallel-test-password"}).status_code == 401
    with factory() as db:
        user = db.scalar(select(AppUser).where(AppUser.username == "parallel"))
        assert user.locked_until_epoch is not None
        assert user.failed_logins == 0


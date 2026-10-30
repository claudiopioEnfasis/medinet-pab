"""Regresiones importantes para rúbrica: respuestas, roles y validación triple."""
from datetime import datetime

from test_api import surgery


def test_health_ready(client):
    assert client.get("/health/ready").json() == {"status": "ready", "database": "ok"}


def test_openapi_documents_errors(client):
    spec = client.get("/openapi.json").json()
    assert spec["info"]["version"] == "0.5.0"
    expected = spec["paths"]["/surgeries"]["post"]["responses"]
    assert {"201", "401", "403", "409", "422"}.issubset(expected)


def test_coordinator_can_schedule(client, basic_data):
    login = client.post("/auth/login", json={"username": "coordinator", "password": "valid-password-test-789"}).json()
    head = {"Authorization": f"Bearer {login['access_token']}"}
    result = client.post("/surgeries", json=surgery(basic_data), headers=head)
    assert result.status_code == 201


def test_sanitizing_room_cannot_be_scheduled(client, basic_data):
    room_id = basic_data["rooms"][0]["id"]
    assert client.patch(f"/operating-rooms/{room_id}/status", json={"status": "sanitizing"}).status_code == 200
    assert client.post("/surgeries", json=surgery(basic_data)).status_code == 409


def test_cancelled_surgery_frees_reservations(client, basic_data):
    created = client.post("/surgeries", json=surgery(basic_data))
    assert created.status_code == 201
    sid = created.json()["id"]
    assert client.patch(f"/surgeries/{sid}/status", json={"status": "cancelled"}).status_code == 200
    assert client.post("/surgeries", json=surgery(basic_data)).status_code == 201


def test_rejects_duplicate_medical_staff(client, basic_data):
    body = surgery(basic_data)
    body["staff_ids"] *= 2
    assert client.post("/surgeries", json=body).status_code == 422


def test_rejects_sql_injection_in_reference(client):
    bad = client.post("/patients", json={"reference": "ABC'; DROP TABLE patients;--", "full_name": "Paciente Demo"})
    assert bad.status_code == 422
    assert client.get("/patients").status_code == 200


def test_invalid_surgery_id_returns_404(client):
    assert client.get("/surgeries/98989").status_code == 404

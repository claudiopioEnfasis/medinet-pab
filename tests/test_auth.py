"""Pruebas de controles de acceso, autenticación y bloqueo."""
import os
from datetime import datetime, timedelta, timezone

import jwt


def test_health_public(client):
    assert client.get("/health").status_code == 200


def test_private_without_auth(client):
    for path in ("/operating-rooms", "/patients", "/surgeries", "/auth/me"):
        assert client.get(path, headers={"Authorization": ""}).status_code == 401


def test_login_success_and_wrong_password(client):
    ok = client.post("/auth/login", json={"username": "admin", "password": "valid-password-test-123"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["role"] == "admin"
    assert client.post("/auth/login", json={"username": "admin", "password": "incorrect"}).status_code == 401


def test_invalid_token_rejected(client):
    assert client.get("/operating-rooms", headers={"Authorization": "Bearer corrupt"}).status_code == 401


def test_viewer_cannot_modify(client):
    token = client.post("/auth/login", json={"username": "viewer", "password": "valid-password-test-456"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/operating-rooms", headers=headers).status_code == 200
    assert client.post("/operating-rooms", headers=headers, json={"code": "Q-01", "name": "Nuevo pabellón"}).status_code == 403
    assert client.post("/surgeries", headers=headers, json={}).status_code == 403


def test_coordinator_cannot_create_patients(client):
    token = client.post("/auth/login", json={"username": "coordinator", "password": "valid-password-test-789"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/patients", headers=headers, json={"reference": "PX", "full_name": "Paciente Ficticio"}).status_code == 403
    assert client.post("/operating-rooms", headers=headers, json={"code": "Q-01", "name": "Nuevo pabellón"}).status_code == 403


def test_login_locked_after_five_attempts(client):
    login = lambda password: client.post("/auth/login", json={"username": "viewer", "password": password})
    for _ in range(5):
        assert login("incorrect").status_code == 401
    assert login("valid-password-test-456").status_code == 401


def test_expired_token_rejected(client):
    expired = jwt.encode(
        {"sub": "1", "iss": "medinet-pab",
         "iat": datetime.now(timezone.utc) - timedelta(hours=2),
         "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_token_with_incorrect_signature_rejected(client):
    forged = jwt.encode(
        {"sub": "1", "iss": "medinet-pab",
         "iat": datetime.now(timezone.utc),
         "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
        "different-secret-at-least-32-characters-long", algorithm="HS256",
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401

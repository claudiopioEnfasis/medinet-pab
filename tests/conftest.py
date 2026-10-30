import os

# Conecta SQLite únicamente para pruebas; producción usa PostgreSQL.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "only-for-tests-random-placeholder-32chars"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.models import AppUser
from app.security import hash_password, make_token
from app.main import app


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    Session = sessionmaker(bind=test_engine, expire_on_commit=False)
    with Session.begin() as session:
        session.add_all([
            AppUser(id=1, username="admin", role="admin", password_hash=hash_password("valid-password-test-123")),
            AppUser(id=2, username="viewer", role="viewer", password_hash=hash_password("valid-password-test-456")),
            AppUser(id=3, username="coordinator", role="coordinator", password_hash=hash_password("valid-password-test-789")),
        ])

    def override_get_db():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        with Session() as session:
            admin = session.get(AppUser, 1)
            token, _ = make_token(admin)
            test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def basic_data(client):
    rooms = [client.post("/operating-rooms", json={"code": f"PAB-0{i}", "name": f"Pabellón {i}"}).json()
             for i in (1, 2)]
    patients = [client.post("/patients", json={"reference": f"P0{i}", "full_name": f"Paciente Demo {i}"}).json()
                for i in (1, 2)]
    staff = [client.post("/medical-staff", json={"reference": f"MED0{i}", "full_name": f"Doctor Demo {i}", "specialty": "Cirugía"}).json()
             for i in (1, 2)]
    return {"rooms": rooms, "patients": patients, "staff": staff}

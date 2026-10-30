DATE1 = "2026-11-05T10:00:00-03:00"
DATE2 = "2026-11-05T12:00:00-03:00"


def surgery(data, room=0, patient=0, staff=(0,), starts_at=DATE1, ends_at=DATE2):
    return {
        "room_id": data["rooms"][room]["id"],
        "patient_id": data["patients"][patient]["id"],
        "staff_ids": [data["staff"][idx]["id"] for idx in staff],
        "starts_at": starts_at, "ends_at": ends_at,
        "procedure": "Cirugía demostrativa", "urgency": "elective",
    }


def test_health_and_swagger(client):
    assert client.get("/health").json()["status"] == "ok"
    spec = client.get("/openapi.json").json()
    assert "/surgeries" in spec["paths"]
    assert "/availability" in spec["paths"]


def test_create_surgery_and_list(client, basic_data):
    response = client.post("/surgeries", json=surgery(basic_data))
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "scheduled"
    assert len(client.get("/surgeries").json()) == 1


def test_prevents_same_room(client, basic_data):
    assert client.post("/surgeries", json=surgery(basic_data)).status_code == 201
    conflict = client.post("/surgeries", json=surgery(basic_data, patient=1, staff=(1,)))
    assert conflict.status_code == 409
    assert "Quirófano" in str(conflict.json())


def test_prevents_same_patient(client, basic_data):
    assert client.post("/surgeries", json=surgery(basic_data)).status_code == 201
    conflict = client.post("/surgeries", json=surgery(basic_data, room=1, staff=(1,)))
    assert conflict.status_code == 409
    assert "Paciente" in str(conflict.json())


def test_prevents_same_doctor(client, basic_data):
    assert client.post("/surgeries", json=surgery(basic_data)).status_code == 201
    conflict = client.post("/surgeries", json=surgery(basic_data, room=1, patient=1))
    assert conflict.status_code == 409
    assert "médico" in str(conflict.json())


def test_allows_non_overlapping_interval(client, basic_data):
    assert client.post("/surgeries", json=surgery(basic_data)).status_code == 201
    later = surgery(basic_data, starts_at=DATE2, ends_at="2026-11-05T14:00:00-03:00")
    assert client.post("/surgeries", json=later).status_code == 201


def test_time_validation(client, basic_data):
    payload = surgery(basic_data, starts_at=DATE2, ends_at=DATE1)
    assert client.post("/surgeries", json=payload).status_code == 422
    payload = surgery(basic_data, starts_at="2026-11-05T10:00:00")
    assert client.post("/surgeries", json=payload).status_code == 422


def test_duplicate_room_code(client, basic_data):
    r = client.post("/operating-rooms", json={"code": "PAB-01", "name": "Repetido"})
    assert r.status_code == 409


def test_bad_status_transition(client, basic_data):
    create = client.post("/surgeries", json=surgery(basic_data))
    sid = create.json()["id"]
    assert client.patch(f"/surgeries/{sid}/status", json={"status": "completed"}).status_code == 409


def test_started_surgery_sets_room_occupied(client, basic_data):
    create = client.post("/surgeries", json=surgery(basic_data))
    sid = create.json()["id"]
    rid = basic_data["rooms"][0]["id"]
    assert client.patch(f"/surgeries/{sid}/status", json={"status": "in_progress"}).status_code == 200
    assert client.post("/surgeries", json=surgery(basic_data, patient=1, staff=(1,))).status_code == 409
    assert client.patch(f"/operating-rooms/{rid}/status", json={"status": "available"}).status_code == 409
    assert client.patch(f"/surgeries/{sid}/status", json={"status": "completed"}).status_code == 200
    room = [r for r in client.get("/operating-rooms").json() if r["id"] == rid][0]
    assert room["status"] == "sanitizing"


def test_availability(client, basic_data):
    assert client.post("/surgeries", json=surgery(basic_data)).status_code == 201
    payload = surgery(basic_data)
    params = [(k, v) for k, v in payload.items() if k in {"room_id", "patient_id", "starts_at", "ends_at"}]
    params.append(("staff_ids", payload["staff_ids"][0]))
    response = client.get("/availability", params=params)
    assert response.status_code == 200, response.text
    assert response.json()["available"] is False


def test_unknown_staff_rejected(client, basic_data):
    payload = surgery(basic_data)
    payload["staff_ids"] = [999]
    assert client.post("/surgeries", json=payload).status_code == 404


def test_availability_invalid_interval_returns_422(client, basic_data):
    payload = surgery(basic_data, starts_at=DATE2, ends_at=DATE1)
    params = [(k, v) for k, v in payload.items() if k in {"room_id", "patient_id", "starts_at", "ends_at"}]
    params.append(("staff_ids", payload["staff_ids"][0]))
    response = client.get("/availability", params=params)
    assert response.status_code == 422

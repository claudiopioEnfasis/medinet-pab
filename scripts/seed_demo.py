"""Carga ficticia, transaccional e idempotente, exclusivamente PostgreSQL.

Uso: docker compose exec -T api python -m scripts.seed_demo
Conserva registros existentes y nunca consulta ni modifica usuarios.
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.db import SessionLocal
from app.locking import lock_keys
from app.main import _conflict_reasons
from app.models import MedicalStaff, OperatingRoom, Patient, Surgery
from app.schemas import SurgeryCreate

SPECIALTIES = (
    "Cirugía general", "Anestesiología", "Traumatología", "Anestesiología",
    "Cirugía pediátrica", "Anestesiología", "Neurocirugía", "Anestesiología",
    "Cirugía vascular", "Anestesiología",
)
COUNTS = {"pabellones": OperatingRoom, "pacientes": Patient,
          "profesionales": MedicalStaff, "cirugias": Surgery}


def _resource(db, model, field, value, created, **kwargs):
    existing = db.scalar(select(model).where(getattr(model, field) == value))
    if existing is not None:
        return existing, False
    record = model(**{field: value}, **kwargs)
    db.add(record)
    db.flush()
    created[model.__tablename__] += 1
    return record, True


def _create_surgery(db, *, marker, room, patient, staff, starts_at, urgency,
                    in_progress=False):
    procedure = f"[DEMO-V05-{marker:02d}] Procedimiento ficticio de presentación"
    if db.scalar(select(Surgery.id).where(Surgery.procedure == procedure)):
        return "conservada"
    db.refresh(room)  # los bloqueos de todos los recursos ya están tomados
    if room.status != "available":
        return "omitida: pabellón existente no disponible"
    for _ in range(168):  # catorce días, sin desplazar reservas existentes
        payload = SurgeryCreate(
            room_id=room.id, patient_id=patient.id, staff_ids=[m.id for m in staff],
            procedure=procedure, urgency=urgency, starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
        )
        conflicts = _conflict_reasons(
            db, room.id, patient.id, payload.staff_ids, payload.starts_at, payload.ends_at,
        )
        if not conflicts:
            db.add(Surgery(
                room=room, patient=patient, staff=staff, procedure=procedure,
                urgency=payload.urgency.value, starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                status="in_progress" if in_progress else "scheduled",
            ))
            if in_progress:
                room.status = "occupied"  # solo pabellones nuevos de esta carga
            db.flush()  # la siguiente reserva debe ver esta transacción
            return "creada"
        if in_progress:
            return "omitida: recurso con una cirugía simultánea"
        starts_at += timedelta(hours=2)
    return "omitida: no se encontró intervalo libre"


def seed(session_factory=SessionLocal, *, now=None):
    now = now or datetime.now(ZoneInfo("America/Santiago"))
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("La fecha de carga debe incluir zona horaria")
    now = now.astimezone(ZoneInfo("America/Santiago"))
    created = {model.__tablename__: 0 for model in COUNTS.values()}
    outcomes = []
    with session_factory() as db, db.begin():
        if db.bind.dialect.name != "postgresql":
            raise RuntimeError("La carga de demostración requiere PostgreSQL real")
        lock_keys(db, ["seed:medinet-pab-v05"])
        rooms, new_rooms = {}, set()
        for i in range(1, 9):
            status = {7: "sanitizing", 8: "maintenance"}.get(i, "available")
            room, added = _resource(
                db, OperatingRoom, "code", f"PAB-{i:02d}", created,
                name=f"Pabellón {i:02d} · DEMOSTRACIÓN", status=status,
            )
            rooms[i] = room
            if added:
                new_rooms.add(i)
        patients, staff = {}, {}
        for i in range(1, 16):
            patients[i], _ = _resource(
                db, Patient, "reference", f"DEMO-P{i:02d}", created,
                full_name=f"Paciente FICTICIO {i:02d} · SIN DATOS REALES",
            )
        for i, specialty in enumerate(SPECIALTIES, 1):
            staff[i], _ = _resource(
                db, MedicalStaff, "reference", f"DEMO-M{i:02d}", created,
                full_name=f"Profesional FICTICIO {i:02d}", specialty=specialty,
            )
        # Mismas claves que en la API; tomar todo el conjunto en orden global
        # protege también pacientes/médicos y evita ciclos entre varias salas.
        lock_keys(db, [f"r:{r.id}" for r in rooms.values()]
                  + [f"p:{p.id}" for p in patients.values()]
                  + [f"m:{m.id}" for m in staff.values()])
        tomorrow = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        for index in range(10):
            first_member = 1 + (2 * index) % 10
            outcomes.append(_create_surgery(
                db, marker=index + 1, room=rooms[index % 4 + 1],
                patient=patients[index + 1], staff=[staff[first_member], staff[first_member + 1]],
                starts_at=tomorrow + timedelta(hours=3 * (index // 4)),
                urgency="emergency" if index % 3 == 0 else "elective",
            ))
        for marker, room_number, patient_number, first_member in [(11, 5, 14, 7), (12, 6, 15, 9)]:
            procedure = f"[DEMO-V05-{marker:02d}] Procedimiento ficticio de presentación"
            if db.scalar(select(Surgery.id).where(Surgery.procedure == procedure)):
                outcomes.append("conservada")
            elif room_number in new_rooms:
                outcomes.append(_create_surgery(
                    db, marker=marker, room=rooms[room_number], patient=patients[patient_number],
                    staff=[staff[first_member], staff[first_member + 1]],
                    starts_at=now - timedelta(minutes=15), urgency="emergency" if marker == 12 else "elective",
                    in_progress=True,
                ))
            else:
                outcomes.append("omitida: conservar estado del pabellón existente")
        created["surgeries"] = outcomes.count("creada")
        totals = {name: db.scalar(select(func.count()).select_from(model))
                  for name, model in COUNTS.items()}
    return {"creados": created, "totales": totals,
            "ejemplos_conservados": outcomes.count("conservada"),
            "omitidos": [value for value in outcomes if value.startswith("omitida")]}


if __name__ == "__main__":
    print(json.dumps(seed(), ensure_ascii=False, indent=2))

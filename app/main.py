"""API REST de quirófanos y cirugías MediNet-Core / PAB."""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from pydantic import ValidationError

from .db import get_db
from .locking import lock_keys
from .models import AppUser, MedicalStaff, OperatingRoom, Patient, Surgery
from .schemas import (
    AvailabilityOut, Interval, MedicalStaffCreate, MedicalStaffOut, PatientCreate,
    PatientOut, RoomCreate, RoomOut, RoomStatus, RoomStatusUpdate, SurgeryCreate,
    SurgeryOut, SurgeryStatus, SurgeryStatusUpdate, LoginRequest, TokenOut, UserOut,
)

from .security import _secret, authenticate, current_user, make_token, require_roles


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # En producción, migraciones Alembic se aplican antes de iniciar la API.
    _secret()  # falla rápido si falta la clave de firma
    yield


app = FastAPI(
    title="MediNet-Core - Módulo 6: Pabellones y Quirófanos (PAB)",
    version="0.5.0",
    description=("Módulo 6 PAB de MediNet-Core. Gestiona pabellones y cirugías "
                 "con validación triple de disponibilidad, JWT y control de roles. "
                 "Solo datos ficticios; IAM/PAC/MED simulados para evaluación."),
    lifespan=lifespan,
)


def _get_or_404(db: Session, model: type, identifier: int, label: str):
    record = db.get(model, identifier)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No existe {label} con ID {identifier}")
    return record


def _insert_unique(db: Session, record):
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El código/referencia ya existe") from None
    return record


def _advisory_locks(db: Session, room_id: int, patient_id: int | None, staff_ids: list[int]):
    """Serializa en PostgreSQL las reservas que comparten recurso.

    Se obtienen en orden global para evitar deadlocks entre solicitudes concurrentes.
    El lock es de transacción y se libera automáticamente al commit/rollback.
    """
    keys = [f"r:{room_id}"]
    if patient_id is not None:
        keys.append(f"p:{patient_id}")
    keys += [f"m:{i}" for i in staff_ids]
    lock_keys(db, keys)


def _conflict_reasons(
    db: Session, room_id: int, patient_id: int, staff_ids: list[int],
    starts_at: datetime, ends_at: datetime,
) -> list[str]:
    # Dos intervalos se solapan si A.inicio < B.fin y A.fin > B.inicio.
    active = db.scalars(
        select(Surgery)
        .options(selectinload(Surgery.staff))
        .where(
            Surgery.status.in_(["scheduled", "in_progress"]),
            Surgery.starts_at < ends_at,
            Surgery.ends_at > starts_at,
            or_(
                Surgery.room_id == room_id,
                Surgery.patient_id == patient_id,
                Surgery.staff.any(MedicalStaff.id.in_(staff_ids)),
            ),
        )
    ).unique().all()
    reasons: set[str] = set()
    for surgery in active:
        if surgery.room_id == room_id:
            reasons.add("Quirófano ocupado en ese horario")
        if surgery.patient_id == patient_id:
            reasons.add("Paciente con otra intervención simultánea")
        if any(member.id in staff_ids for member in surgery.staff):
            reasons.add("Integrante del equipo médico con tope de horario")
    return sorted(reasons)


def _surgery_response(surgery: Surgery) -> SurgeryOut:
    return SurgeryOut(
        id=surgery.id, room_id=surgery.room_id, patient_id=surgery.patient_id,
        staff_ids=[m.id for m in surgery.staff], procedure=surgery.procedure,
        urgency=surgery.urgency, status=surgery.status,
        starts_at=surgery.starts_at, ends_at=surgery.ends_at,
    )


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok", "module": "PAB"}


@app.get("/health/ready", tags=["Sistema"], summary="Estado de conexión a PostgreSQL")
def health_ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Base de datos no disponible") from None
    return {"status": "ready", "database": "ok"}


@app.post("/auth/login", response_model=TokenOut, tags=["Autenticación"],
          responses={401: {"description": "Credenciales incorrectas o cuenta bloqueada"}})
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(payload.username, payload.password, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas o cuenta bloqueada")
    token, ttl = make_token(user)
    return TokenOut(access_token=token, expires_in=ttl)


@app.get("/auth/me", response_model=UserOut, tags=["Autenticación"])
def me(user: AppUser = Depends(current_user)):
    return user


@app.get("/operating-rooms", response_model=list[RoomOut], tags=["Pabellones"], dependencies=[Depends(current_user)])
def list_rooms(db: Session = Depends(get_db)):
    return db.scalars(select(OperatingRoom).order_by(OperatingRoom.id)).all()


@app.post("/operating-rooms", response_model=RoomOut, status_code=201, tags=["Pabellones"], dependencies=[Depends(require_roles("admin"))])
def create_room(payload: RoomCreate, db: Session = Depends(get_db)):
    return _insert_unique(db, OperatingRoom(**payload.model_dump()))


@app.patch("/operating-rooms/{room_id}/status", response_model=RoomOut, tags=["Pabellones"], dependencies=[Depends(require_roles("admin", "coordinator"))])
def update_room_status(room_id: int, payload: RoomStatusUpdate, db: Session = Depends(get_db)):
    _advisory_locks(db, room_id, None, [])
    room = _get_or_404(db, OperatingRoom, room_id, "quirófano")
    # Impide marcar un quirófano como libre durante una cirugía iniciada.
    started = db.scalar(select(Surgery.id).where(
        Surgery.room_id == room_id, Surgery.status == "in_progress",
    ).limit(1))
    if started and payload.status != RoomStatus.occupied:
        raise HTTPException(status_code=409, detail="No se puede cambiar el estado durante una cirugía en curso")
    room.status = payload.status.value
    db.commit()
    db.refresh(room)
    return room


@app.get("/patients", response_model=list[PatientOut], tags=["Datos de prueba"], dependencies=[Depends(current_user)])
def list_patients(db: Session = Depends(get_db)):
    return db.scalars(select(Patient).order_by(Patient.id)).all()


@app.post("/patients", response_model=PatientOut, status_code=201, tags=["Datos de prueba"], dependencies=[Depends(require_roles("admin"))])
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    return _insert_unique(db, Patient(**payload.model_dump()))


@app.get("/medical-staff", response_model=list[MedicalStaffOut], tags=["Datos de prueba"], dependencies=[Depends(current_user)])
def list_staff(db: Session = Depends(get_db)):
    return db.scalars(select(MedicalStaff).order_by(MedicalStaff.id)).all()


@app.post("/medical-staff", response_model=MedicalStaffOut, status_code=201, tags=["Datos de prueba"], dependencies=[Depends(require_roles("admin"))])
def create_staff(payload: MedicalStaffCreate, db: Session = Depends(get_db)):
    return _insert_unique(db, MedicalStaff(**payload.model_dump()))


@app.get("/surgeries", response_model=list[SurgeryOut], tags=["Cirugías"], dependencies=[Depends(current_user)])
def list_surgeries(db: Session = Depends(get_db)):
    records = db.scalars(select(Surgery).options(selectinload(Surgery.staff)).order_by(Surgery.starts_at)).all()
    return [_surgery_response(item) for item in records]


@app.get("/surgeries/{surgery_id}", response_model=SurgeryOut, tags=["Cirugías"], dependencies=[Depends(current_user)])
def get_surgery(surgery_id: int, db: Session = Depends(get_db)):
    surgery = db.scalar(
        select(Surgery).options(selectinload(Surgery.staff)).where(Surgery.id == surgery_id)
    )
    if not surgery:
        raise HTTPException(status_code=404, detail="Cirugía no encontrada")
    return _surgery_response(surgery)


@app.get("/availability", response_model=AvailabilityOut, tags=["Cirugías"], dependencies=[Depends(current_user)])
def check_availability(
    room_id: int = Query(gt=0), patient_id: int = Query(gt=0),
    staff_ids: list[int] = Query(min_length=1),
    starts_at: datetime = Query(), ends_at: datetime = Query(),
    db: Session = Depends(get_db),
):
    try:
        interval = Interval(starts_at=starts_at, ends_at=ends_at)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    room = _get_or_404(db, OperatingRoom, room_id, "quirófano")
    _get_or_404(db, Patient, patient_id, "paciente")
    if len(set(staff_ids)) != len(staff_ids) or any(sid <= 0 for sid in staff_ids):
        raise HTTPException(422, detail="staff_ids debe contener identificadores positivos y distintos")
    members = db.scalars(select(MedicalStaff).where(MedicalStaff.id.in_(staff_ids))).all()
    if len(members) != len(staff_ids):
        raise HTTPException(404, detail="Algún integrante del equipo médico no existe")
    conflicts = _conflict_reasons(db, room_id, patient_id, staff_ids, interval.starts_at, interval.ends_at)
    if room.status != "available":
        conflicts.insert(0, f"Quirófano no disponible: {room.status}")
    return AvailabilityOut(available=not conflicts, conflicts=conflicts)


@app.post("/surgeries", response_model=SurgeryOut, status_code=201, tags=["Cirugías"],
          responses={409: {"description": "Conflicto de quirófano, médico o paciente"}},
          dependencies=[Depends(require_roles("admin", "coordinator"))])
def schedule_surgery(payload: SurgeryCreate, db: Session = Depends(get_db)):
    _advisory_locks(db, payload.room_id, payload.patient_id, payload.staff_ids)
    room = _get_or_404(db, OperatingRoom, payload.room_id, "quirófano")
    patient = _get_or_404(db, Patient, payload.patient_id, "paciente")
    members = db.scalars(select(MedicalStaff).where(MedicalStaff.id.in_(payload.staff_ids))).all()
    if len(members) != len(payload.staff_ids):
        raise HTTPException(404, detail="Algún integrante del equipo médico no existe")
    if room.status != "available":
        raise HTTPException(409, detail=f"Quirófano no disponible: {room.status}")
    conflicts = _conflict_reasons(
        db, payload.room_id, payload.patient_id, payload.staff_ids,
        payload.starts_at, payload.ends_at,
    )
    if conflicts:
        raise HTTPException(status_code=409, detail=conflicts)
    surgery = Surgery(
        room=room, patient=patient, staff=members,
        starts_at=payload.starts_at, ends_at=payload.ends_at,
        procedure=payload.procedure, urgency=payload.urgency.value,
    )
    db.add(surgery)
    db.commit()
    db.refresh(surgery)
    return _surgery_response(surgery)


@app.patch("/surgeries/{surgery_id}/status", response_model=SurgeryOut, tags=["Cirugías"], dependencies=[Depends(require_roles("admin", "coordinator"))])
def change_surgery_status(surgery_id: int, payload: SurgeryStatusUpdate, db: Session = Depends(get_db)):
    surgery = db.scalar(select(Surgery).options(selectinload(Surgery.staff)).where(Surgery.id == surgery_id))
    if surgery is None:
        raise HTTPException(404, detail="Cirugía no encontrada")
    allowed = {
        "scheduled": {"in_progress", "cancelled"},
        "in_progress": {"completed"},
        "completed": set(), "cancelled": set(),
    }
    if payload.status.value not in allowed[surgery.status]:
        raise HTTPException(409, detail=f"Transición no permitida: {surgery.status} → {payload.status.value}")
    _advisory_locks(db, surgery.room_id, surgery.patient_id, [m.id for m in surgery.staff])
    # Evita transiciones basadas en una lectura anterior al bloqueo (concurrencia).
    db.expire(surgery)
    surgery = db.scalar(
        select(Surgery).where(Surgery.id == surgery_id).with_for_update()
    )
    if payload.status.value not in allowed[surgery.status]:
        raise HTTPException(409, detail=f"Transición no permitida: {surgery.status} → {payload.status.value}")
    room = surgery.room
    if payload.status == SurgeryStatus.in_progress:
        if room.status != "available":
            raise HTTPException(409, detail="Quirófano no disponible para comenzar")
        room.status = "occupied"
    if payload.status == SurgeryStatus.completed:
        room.status = "sanitizing"
    surgery.status = payload.status.value
    db.commit()
    return _surgery_response(surgery)


# Respuestas documentadas para Swagger/OpenAPI; no altera códigos reales.
from fastapi.openapi.utils import get_openapi

def _custom_openapi():
    if app.openapi_schema is not None:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version,
                         description=app.description, routes=app.routes)
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "patch", "put", "delete"}:
                continue
            responses = operation.setdefault("responses", {})
            responses.setdefault("422", {"description": "Solicitud inválida (Pydantic)"})
            if path not in {"/health", "/health/ready", "/auth/login"}:
                responses.setdefault("401", {"description": "Token JWT ausente, inválido o vencido"})
                if method != "get":
                    responses.setdefault("403", {"description": "Permiso insuficiente para el rol"})
            if path.startswith("/surgeries/") or path.startswith("/operating-rooms/"):
                responses.setdefault("404", {"description": "Recurso no encontrado"})
            if path.startswith("/surgeries") or (path.startswith("/operating-rooms") and method != "get"):
                responses.setdefault("409", {"description": "Conflicto de estado, disponibilidad o datos duplicados"})
    app.openapi_schema = schema
    return schema

app.openapi = _custom_openapi

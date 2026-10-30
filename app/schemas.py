"""Validaciones de solicitudes y esquemas OpenAPI."""
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RoomStatus(str, Enum):
    available = "available"
    occupied = "occupied"
    sanitizing = "sanitizing"
    maintenance = "maintenance"


class SurgeryStatus(str, Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class Urgency(str, Enum):
    elective = "elective"
    emergency = "emergency"


class RoomCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    code: str = Field(min_length=2, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=3, max_length=100)


class RoomOut(RoomCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: RoomStatus


class RoomStatusUpdate(BaseModel):
    status: RoomStatus


class PatientCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reference: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    full_name: str = Field(min_length=3, max_length=120)


class PatientOut(PatientCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class MedicalStaffCreate(PatientCreate):
    specialty: str = Field(min_length=3, max_length=100)


class MedicalStaffOut(MedicalStaffCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class Interval(BaseModel):
    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Indica zona horaria, por ejemplo 2026-11-05T10:00:00-03:00")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def valid_range(self):
        if self.starts_at >= self.ends_at:
            raise ValueError("La hora de término debe ser posterior al inicio")
        return self


class SurgeryCreate(Interval):
    model_config = ConfigDict(str_strip_whitespace=True)
    room_id: int = Field(gt=0)
    patient_id: int = Field(gt=0)
    staff_ids: list[int] = Field(min_length=1, max_length=30)
    procedure: str = Field(min_length=3, max_length=200)
    urgency: Urgency = Urgency.elective

    @field_validator("staff_ids")
    @classmethod
    def validate_staff_ids(cls, value: list[int]) -> list[int]:
        if any(staff_id <= 0 for staff_id in value):
            raise ValueError("Los ID del equipo médico deben ser positivos")
        if len(set(value)) != len(value):
            raise ValueError("No se puede repetir un integrante del equipo médico")
        return value


class SurgeryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    room_id: int
    patient_id: int
    staff_ids: list[int]
    procedure: str
    urgency: Urgency
    status: SurgeryStatus
    starts_at: datetime
    ends_at: datetime


class SurgeryStatusUpdate(BaseModel):
    status: SurgeryStatus


class AvailabilityOut(BaseModel):
    available: bool
    conflicts: list[str]


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-z][a-z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str

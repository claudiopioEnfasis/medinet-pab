"""Modelo relacional del módulo PAB (incluye datos simulados de PAC/MED)."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


surgery_staff = Table(
    "surgery_staff",
    Base.metadata,
    Column("surgery_id", ForeignKey("surgeries.id", ondelete="CASCADE"), primary_key=True),
    Column("staff_id", ForeignKey("medical_staff.id", ondelete="RESTRICT"), primary_key=True),
)


class OperatingRoom(Base):
    __tablename__ = "operating_rooms"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available','occupied','sanitizing','maintenance')",
            name="ck_room_status",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    surgeries: Mapped[list["Surgery"]] = relationship(back_populates="room")


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    surgeries: Mapped[list["Surgery"]] = relationship(back_populates="patient")


class MedicalStaff(Base):
    __tablename__ = "medical_staff"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    specialty: Mapped[str] = mapped_column(String(100))
    surgeries: Mapped[list["Surgery"]] = relationship(secondary=surgery_staff, back_populates="staff")


class Surgery(Base):
    __tablename__ = "surgeries"
    __table_args__ = (
        CheckConstraint("starts_at < ends_at", name="ck_surgery_time_order"),
        CheckConstraint("urgency IN ('elective','emergency')", name="ck_surgery_urgency"),
        CheckConstraint(
            "status IN ('scheduled','in_progress','completed','cancelled')",
            name="ck_surgery_status",
        ),
        Index("ix_surgeries_room_interval", "room_id", "starts_at", "ends_at"),
        Index("ix_surgeries_patient_interval", "patient_id", "starts_at", "ends_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("operating_rooms.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    procedure: Mapped[str] = mapped_column(String(200))
    urgency: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(16), default="scheduled")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    room: Mapped[OperatingRoom] = relationship(back_populates="surgeries")
    patient: Mapped[Patient] = relationship(back_populates="surgeries")
    staff: Mapped[list[MedicalStaff]] = relationship(secondary=surgery_staff, back_populates="surgeries")


class AppUser(Base):
    """Usuarios locales de demostración; se integrarán con el módulo IAM posteriormente."""
    __tablename__ = "app_users"
    __table_args__ = (
        CheckConstraint("role IN ('admin','coordinator','viewer')", name="ck_app_user_role"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)

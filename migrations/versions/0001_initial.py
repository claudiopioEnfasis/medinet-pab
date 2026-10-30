"""Esquema base de PAB v0.3, compatible con base existente.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("operating_rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(24), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("status IN ('available','occupied','sanitizing','maintenance')", name="ck_room_status"))
    op.create_index("ix_operating_rooms_code", "operating_rooms", ["code"], unique=True)
    op.create_table("patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(32), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False))
    op.create_index("ix_patients_reference", "patients", ["reference"], unique=True)
    op.create_table("medical_staff",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(32), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("specialty", sa.String(100), nullable=False))
    op.create_index("ix_medical_staff_reference", "medical_staff", ["reference"], unique=True)
    op.create_table("app_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(40), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_logins", sa.Integer(), nullable=False),
        sa.Column("locked_until_epoch", sa.Integer(), nullable=True),
        sa.CheckConstraint("role IN ('admin','coordinator','viewer')", name="ck_app_user_role"))
    op.create_index("ix_app_users_username", "app_users", ["username"], unique=True)
    op.create_table("surgeries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("operating_rooms.id"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("procedure", sa.String(200), nullable=False),
        sa.Column("urgency", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("starts_at < ends_at", name="ck_surgery_time_order"),
        sa.CheckConstraint("urgency IN ('elective','emergency')", name="ck_surgery_urgency"),
        sa.CheckConstraint("status IN ('scheduled','in_progress','completed','cancelled')", name="ck_surgery_status"))
    op.create_index("ix_surgeries_room_id", "surgeries", ["room_id"])
    op.create_index("ix_surgeries_patient_id", "surgeries", ["patient_id"])
    op.create_index("ix_surgeries_room_interval", "surgeries", ["room_id", "starts_at", "ends_at"])
    op.create_index("ix_surgeries_patient_interval", "surgeries", ["patient_id", "starts_at", "ends_at"])
    op.create_table("surgery_staff",
        sa.Column("surgery_id", sa.Integer(), sa.ForeignKey("surgeries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("medical_staff.id", ondelete="RESTRICT"), primary_key=True))


def downgrade():
    op.drop_table("surgery_staff")
    op.drop_table("surgeries")
    op.drop_table("app_users")
    op.drop_table("medical_staff")
    op.drop_table("patients")
    op.drop_table("operating_rooms")

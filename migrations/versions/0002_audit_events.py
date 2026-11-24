"""Registra acciones de Agenda/PAB sin datos clínicos ni contenido de solicitudes."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("surgery_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.CheckConstraint("action IN ('surgery.scheduled', 'surgery.status_changed')", name="ck_audit_event_action"),
    )


def downgrade():
    raise RuntimeError("La reversión de 0002 no debe eliminar el historial de auditoría")

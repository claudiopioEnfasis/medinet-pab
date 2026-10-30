"""Migración segura desde v0.3 sin destruir ni recrear los registros existentes.

- BD vacía: aplicar revision 0001.
- BD v0.3 con TODAS sus tablas esperadas, sin alembic_version: validar columnas
  y estampar 0001, sin ejecutar DDL sobre datos existentes.
- Esquema parcial o incompatible: detener y pedir revisión manual.
"""
from pathlib import Path
from sqlalchemy import inspect
from alembic import command
from alembic.config import Config
from app.db import Base, engine
import app.models  # noqa: F401


def migrate():
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected = set(Base.metadata.tables)
    if "alembic_version" not in tables and (expected & tables):
        if not expected.issubset(tables):
            raise RuntimeError("Esquema v0.3 incompleto: migración automática bloqueada; restaura respaldo")
        for name, table in Base.metadata.tables.items():
            actual_cols = {col["name"] for col in inspector.get_columns(name)}
            required_cols = {col.name for col in table.columns}
            if not required_cols.issubset(actual_cols):
                raise RuntimeError(f"Esquema incompatible en {name}: faltan {required_cols - actual_cols}")
        print("Esquema v0.3 verificado; registrando baseline Alembic 0001 sin borrar datos")
        command.stamp(cfg, "0001")
    command.upgrade(cfg, "head")
    print("Migraciones aplicadas correctamente")


if __name__ == "__main__":
    migrate()

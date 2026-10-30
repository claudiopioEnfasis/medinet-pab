"""Bloqueos de reserva compartidos por API y carga de demostración."""
from hashlib import sha256

from sqlalchemy import text
from sqlalchemy.orm import Session


def lock_keys(db: Session, keys: list[str]) -> None:
    """Orden global y misma identidad de bloqueo que en v0.5 original."""
    if db.bind.dialect.name != "postgresql":
        return  # Las pruebas unitarias de endpoints usan SQLite.
    for key in sorted(set(keys)):
        value = int.from_bytes(sha256(key.encode("utf-8")).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": value})

"""Entorno de migraciones: usa exactamente la conexión definida en app.db."""
from alembic import context
from app.db import Base, engine
import app.models  # noqa: F401: registra modelos en metadata

config = context.config
target_metadata = Base.metadata

def run_migrations_online():
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    raise RuntimeError("Migraciones offline deshabilitadas para evitar SQL sin verificar")
else:
    run_migrations_online()

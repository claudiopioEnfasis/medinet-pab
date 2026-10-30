"""Permisos runtime explícitos. Ejecutar solo con conexión administrativa.

--create recibe una contraseña aleatoria por stdin JSON (nunca por argumentos).
Sin --create reaplica grants después de una migración, sin cambiar contraseñas.
"""
import argparse
import json
import re
import sys

from psycopg import sql
from app.db import engine

RUNTIME_ROLE = "medinet_runtime"
BUSINESS_TABLES = ("operating_rooms", "patients", "medical_staff", "surgeries")


def provision(create=False):
    role = sql.Identifier(RUNTIME_ROLE)
    with engine.begin() as connection:
        cursor = connection.connection.driver_connection.cursor()
        cursor.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = %s", (RUNTIME_ROLE,))
        existing = cursor.fetchone()
        if create:
            if existing is not None:
                raise RuntimeError("El rol ya existe: no se cambia ni se rota automáticamente")
            password = json.load(sys.stdin)["password"]
            if not re.fullmatch(r"[A-Za-z0-9_-]{48,128}", password):
                raise ValueError("Se requiere una contraseña aleatoria de al menos 48 caracteres")
            cursor.execute("SET LOCAL password_encryption = 'scram-sha-256'")
            cursor.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}").format(role, sql.Literal(password)))
        elif existing is None or any(existing):
            raise RuntimeError("Falta el rol runtime restringido o tiene atributos inseguros")
        cursor.execute("SELECT 1 FROM pg_auth_members WHERE member = (SELECT oid FROM pg_roles WHERE rolname = %s)", (RUNTIME_ROLE,))
        if cursor.fetchone() is not None:
            raise RuntimeError("El rol runtime no debe pertenecer a otros roles")
        cursor.execute("SELECT current_database()")
        database = sql.Identifier(cursor.fetchone()[0])
        cursor.execute(sql.SQL("REVOKE TEMPORARY ON DATABASE {} FROM PUBLIC").format(database))
        cursor.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database, role))
        cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        for table in BUSINESS_TABLES:
            cursor.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE ON TABLE {} TO {}").format(sql.Identifier(table), role))
            cursor.execute(sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}").format(sql.Identifier(table + "_id_seq"), role))
        cursor.execute(sql.SQL("GRANT SELECT, INSERT ON surgery_staff TO {}").format(role))
        cursor.execute(sql.SQL("GRANT SELECT ON app_users TO {}").format(role))
        cursor.execute(sql.SQL("GRANT UPDATE (failed_logins, locked_until_epoch) ON app_users TO {}").format(role))
        cursor.close()
    print("Permisos runtime aplicados; credenciales ocultas")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true")
    try:
        provision(parser.parse_args().create)
    except Exception:
        # Un error SQL de CREATE ROLE podría incluir la contraseña en su consulta.
        print("No se pudo aprovisionar: transacción revertida; revisar conexión, rol y esquema con el administrador", file=sys.stderr)
        sys.exit(1)

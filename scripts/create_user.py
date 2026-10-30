"""Crea usuarios demo sin contraseñas en CLI, logs ni repositorio.

Uso: docker compose exec -it api python -m scripts.create_user admin admin
"""
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import AppUser
from app.security import hash_password

ROLES = {"admin", "coordinator", "viewer"}


def main():
    if len(sys.argv) != 3:
        sys.exit("Uso: python -m scripts.create_user <usuario> <admin|coordinator|viewer>")
    username, role = sys.argv[1:]
    if role not in ROLES or not 3 <= len(username) <= 40 or not username[0].islower() or not all(c in 'abcdefghijklmnopqrstuvwxyz0123456789_.-' for c in username):
        sys.exit("Usuario o rol inválido. Usuario: minúsculas, números, guion, punto y guion bajo.")
    with SessionLocal() as db:
        if db.scalar(select(AppUser.id).where(AppUser.username == username)):
            sys.exit("El usuario ya existe. No se modificó ninguna contraseña.")
        password = getpass.getpass("Contraseña (12-128 caracteres, no se mostrará): ")
        confirm = getpass.getpass("Repetir contraseña: ")
        if password != confirm:
            sys.exit("Las contraseñas no coinciden")
        try:
            pw_hash = hash_password(password)
        except ValueError as exc:
            sys.exit(str(exc))
        db.add(AppUser(username=username, role=role, password_hash=pw_hash))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            sys.exit("El usuario ya existe")
    print(f"Usuario '{username}' con rol '{role}' creado correctamente.")


if __name__ == "__main__":
    main()

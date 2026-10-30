"""Autenticación local para el módulo PAB. No sustituye IAM corporativo."""
import os
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import AppUser

PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=19456, parallelism=1)
TOKEN_SCHEME = HTTPBearer(auto_error=False)
ISSUER = "medinet-pab"
TOKEN_MINUTES = 30


def _secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET debe contener al menos 32 caracteres aleatorios")
    return secret


def hash_password(raw: str) -> str:
    if len(raw) < 12 or len(raw) > 128:
        raise ValueError("La contraseña debe tener entre 12 y 128 caracteres")
    return PASSWORD_HASHER.hash(raw)


def verify_password(raw: str, stored_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(stored_hash, raw)
    except (VerificationError, InvalidHashError):
        return False


DUMMY_HASH = PASSWORD_HASHER.hash("dummy-password-not-a-real-user")


def make_token(user: AppUser) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user.id), "iss": ISSUER, "iat": now,
         "exp": now + timedelta(minutes=TOKEN_MINUTES)},
        _secret(), algorithm="HS256",
    )
    return token, TOKEN_MINUTES * 60


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(TOKEN_SCHEME),
    db: Session = Depends(get_db),
) -> AppUser:
    invalid = HTTPException(status_code=401, detail="No autenticado", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise invalid
    try:
        claims = jwt.decode(
            credentials.credentials, _secret(), algorithms=["HS256"],
            issuer=ISSUER, options={"require": ["sub", "exp", "iss", "iat"]},
        )
        identifier = int(claims["sub"])
        if identifier <= 0:
            raise ValueError("ID inválido")
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise invalid from None
    user = db.get(AppUser, identifier)
    if user is None or not user.is_active:
        raise invalid
    return user


def require_roles(*roles: str):
    def dependency(user: AppUser = Depends(current_user)) -> AppUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="No tienes permisos para esta acción")
        return user
    return dependency


def authenticate(username: str, password: str, db: Session) -> AppUser | None:
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    user = db.scalar(select(AppUser).where(AppUser.username == username))
    # Verificación ficticia para reducir filtración por tiempo cuando no existe usuario.
    valid = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if user is None or not user.is_active:
        return None
    if user.locked_until_epoch and user.locked_until_epoch > now_epoch:
        return None
    if not valid:
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until_epoch = now_epoch + 15 * 60
            user.failed_logins = 0
        db.commit()
        return None
    user.failed_logins = 0
    user.locked_until_epoch = None
    db.commit()
    return user

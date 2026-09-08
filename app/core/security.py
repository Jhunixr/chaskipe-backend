"""
Utilidades de autenticacion: hash de contrasenas y tokens JWT.

Las contrasenas se guardan con **bcrypt**, nunca en claro. Los tokens se
firman con `settings.secret_key`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

# bcrypt explicito (no `recommended()`, que exige argon2). Es el algoritmo
# declarado en requirements.txt.
_hasher = PasswordHash((BcryptHasher(),))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Compara en tiempo constante. Nunca lanza: un hash corrupto es False."""
    try:
        return _hasher.verify(password, hashed)
    except Exception:
        return False


def create_access_token(user_id: int) -> str:
    """Token de acceso con el id del usuario en `sub` y caducidad."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int | None:
    """
    Devuelve el id del usuario, o None si el token es invalido, caducado o
    esta manipulado.
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        return None
    return int(sub)

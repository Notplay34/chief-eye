"""Хеширование паролей и JWT для веб-авторизации."""
from datetime import datetime, timedelta
from typing import Any, Optional

import bcrypt
import jwt

from app.config import settings
from app.core.logging_config import get_logger
from app.models.employee import EmployeeRole

logger = get_logger(__name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    subject: int,
    role: str,
    name: str,
    login: str,
) -> str:
    now = datetime.utcnow()
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(subject),
        "role": role,
        "name": name,
        "login": login,
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as e:
        logger.warning("JWT decode failed: %s", str(e))
        return None

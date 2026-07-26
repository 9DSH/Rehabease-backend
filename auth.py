"""
Password hashing + session token helpers.

Note on the token flow: the Android client (ApiService.kt) does NOT read
the token from the JSON response body. It reads it from the
`Authorization` *response header* on a successful /login call, then
echoes that exact string back as the `Authorization` *request header* on
every later call. So the server must:
  1. On successful login, set response.headers["Authorization"] = <token>
  2. On every protected route, read request.headers["Authorization"]

We use a signed JWT as the token value so it's self-contained (no server
side session store needed), but the client treats it as an opaque string.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import secrets
import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jose import jwt, JWTError

# SECRET_KEY and ADMIN_PASSWORD must come from the environment -- no
# hardcoded fallback. A default value here would end up committed to git
# and become a permanent, silent backdoor if anyone forgot to override it.
def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            f"Set it in your .env file (see .env.example) before starting the server."
        )
    return value


SECRET_KEY = _require_env("REHABEASE_JWT_SECRET")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 30  # 30 days, adjust as needed


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(subject_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": subject_id, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ==================== Admin panel auth ====================
# Single shared username/password protecting the /admin panel. Both must
# come from the environment -- no default (same reasoning as SECRET_KEY
# above).
ADMIN_USERNAME = _require_env("REHABEASE_ADMIN_USER")
ADMIN_PASSWORD = _require_env("REHABEASE_ADMIN_PASSWORD")

_basic_security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(_basic_security)) -> str:
    """Browser will show its native login prompt. Compares using
    secrets.compare_digest to avoid timing attacks."""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
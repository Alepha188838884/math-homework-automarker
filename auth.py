from __future__ import annotations

# pyright: reportMissingModuleSource=false

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "change-this-in-production")
ALGORITHM = os.getenv("AUTH_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
PBKDF2_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "260000"))
SALT_BYTES = 16

try:
    import bcrypt  # type: ignore
except Exception:
    bcrypt = None


def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, PBKDF2_ITERATIONS)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{PBKDF2_SCHEME}${PBKDF2_ITERATIONS}${salt_b64}${digest_b64}"


def _b64_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _verify_pbkdf2(plain_password: str, stored_hash: str) -> bool:
    try:
        scheme, iteration_text, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if scheme != PBKDF2_SCHEME:
            return False
        iterations = int(iteration_text)
        salt = _b64_decode(salt_b64)
        expected_digest = _b64_decode(digest_b64)
    except Exception:
        return False

    computed = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(computed, expected_digest)


def _verify_legacy_bcrypt(plain_password: str, stored_hash: str) -> bool:
    if bcrypt is None:
        return False
    try:
        # Keep compatibility with existing bcrypt hashes created earlier.
        secret = plain_password.encode("utf-8")
        # New bcrypt versions may raise on >72 bytes; bcrypt itself uses first 72 bytes.
        if len(secret) > 72:
            secret = secret[:72]
        return bool(bcrypt.checkpw(secret, stored_hash.encode("utf-8")))
    except Exception:
        return False


def verify_password(plain_password: str, password_hash: str) -> bool:
    if password_hash.startswith(f"{PBKDF2_SCHEME}$"):
        return _verify_pbkdf2(plain_password, password_hash)
    if password_hash.startswith("$2"):
        return _verify_legacy_bcrypt(plain_password, password_hash)
    return False


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if not isinstance(payload, dict):
        raise ValueError("Invalid token payload")
    return payload

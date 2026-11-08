"""Opaque revocable login tokens, PBKDF2 password hashing and role validation."""
import hashlib
import hmac
import secrets
from datetime import timedelta, timezone
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models
from app.config import settings
from app.db import get_db

ROLES = {'admin', 'viewer'}

def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 1024:
        raise ValueError('Password length must be 12–1024 characters')
    salt = secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600_000)
    return f'pbkdf2_sha256$600000${salt.hex()}${value.hex()}'

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, key_hex = encoded.split('$')
        if algorithm != 'pbkdf2_sha256': return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(actual, bytes.fromhex(key_hex))
    except (ValueError, TypeError, OverflowError):
        return False

def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def issue_session(db: Session, user: models.User) -> str:
    token = secrets.token_urlsafe(48)
    db.add(models.LoginSession(user_id=user.id, token_hash=token_digest(token),
                               expires_at=models.now() + timedelta(hours=12)))
    db.commit()
    return token

def authenticate(authorization: str | None = Header(None), x_api_key: str | None = Header(None),
                 db: Session = Depends(get_db)) -> models.User | None:
    # Developer-only API-key fallback maintains compatibility with earlier phases.
    if settings.environment != 'production' and x_api_key and hmac.compare_digest(x_api_key, settings.api_key):
        return None  # None stands for local development administrator.
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Sign in required', headers={'WWW-Authenticate': 'Bearer'})
    token = authorization[7:]
    if len(token) > 256:
        raise HTTPException(401, 'Invalid session')
    record = db.scalar(select(models.LoginSession).where(models.LoginSession.token_hash == token_digest(token)))
    if not record or record.expires_at.replace(tzinfo=timezone.utc) <= models.now():
        raise HTTPException(401, 'Session expired or invalid')
    user = db.get(models.User, record.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, 'Inactive account')
    return user

def require_admin(user: models.User | None = Depends(authenticate)):
    if user is not None and user.role != 'admin':
        raise HTTPException(403, 'Administrator role required')
    return user

"""Usage: ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m app.bootstrap_admin"""
import os
from sqlalchemy import select
from app.auth import hash_password
from app.db import SessionLocal
from app.models import User

email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
password = os.environ.get('ADMIN_PASSWORD', '')
if not email or '@' not in email or not password:
    raise SystemExit('Set ADMIN_EMAIL and ADMIN_PASSWORD (12+ chars) in the command environment')
with SessionLocal.begin() as db:
    if db.scalar(select(User).where(User.email == email)):
        raise SystemExit('Account already exists; refusing to overwrite')
    db.add(User(email=email, password_hash=hash_password(password), role='admin'))
print('Administrator account created. Remove credentials from your shell history and environment.')

"""Phase 5 session, role, lockout, and revocation checks."""
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db import Base, get_db
from app.main import app
from app import models
from app.auth import hash_password, verify_password


def test_password_hash():
    encoded = hash_password('a-secure-password-2026')
    assert verify_password('a-secure-password-2026', encoded)
    assert not verify_password('wrong', encoded)
    assert encoded != hash_password('a-secure-password-2026')


def test_login_roles_revocation_lockout():
    with tempfile.TemporaryDirectory() as temp:
        engine = create_engine('sqlite+pysqlite:///' + str(Path(temp) / 'accounts.db'))
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        with factory.begin() as db:
            db.add_all([
                models.User(email='admin@example.com', password_hash=hash_password('secure-admin-password'), role='admin'),
                models.User(email='viewer@example.com', password_hash=hash_password('secure-viewer-password'), role='viewer'),
            ])
        def override():
            with factory() as db:
                yield db
        app.dependency_overrides[get_db] = override
        try:
            client = TestClient(app)
            assert client.get('/api/v1/monitors').status_code == 401
            result = client.post('/api/v1/auth/login', json={'email':'viewer@example.com','password':'secure-viewer-password'})
            assert result.status_code == 200, result.text
            token = result.json()['access_token']
            headers = {'Authorization': 'Bearer ' + token}
            assert client.get('/api/v1/auth/me',headers=headers).json()['role']=='viewer'
            assert client.get('/api/v1/monitors',headers=headers).status_code == 200
            assert client.post('/api/v1/users',headers=headers,json={'email':'new@example.com','password':'passwordpass1234','role':'admin'}).status_code==403
            assert client.delete('/api/v1/monitors/1',headers=headers).status_code==403
            assert client.post('/api/v1/auth/logout',headers=headers).status_code==204
            assert client.get('/api/v1/auth/me',headers=headers).status_code==401
            result=client.post('/api/v1/auth/login',json={'email':'admin@example.com','password':'secure-admin-password'})
            assert result.status_code == 200
            headers={'Authorization':'Bearer '+result.json()['access_token']}
            result=client.post('/api/v1/users',headers=headers,json={'email':'new@example.com','password':'passwordpass1234','role':'viewer'})
            assert result.status_code==201, result.text
            assert len(client.get('/api/v1/users',headers=headers).json())==3
            assert client.post('/api/v1/users',headers=headers,json={'email':'new@example.com','password':'passwordpass1234'}).status_code==409
            for _ in range(5):
                assert client.post('/api/v1/auth/login',json={'email':'new@example.com','password':'bad'}).status_code==401
            assert client.post('/api/v1/auth/login',json={'email':'new@example.com','password':'passwordpass1234'}).status_code==429
        finally:
            app.dependency_overrides.clear()
            engine.dispose()

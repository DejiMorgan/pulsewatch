"""Phase 4 security, readiness and worker lease regression tests."""
import os
import tempfile
from pathlib import Path
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import models, worker
from app.checks import Probe
from app.main import app
from app.db import Base


def test_health_readiness_and_auth():
    with tempfile.TemporaryDirectory() as directory:
        engine = create_engine(f"sqlite+pysqlite:///{Path(directory) / 'health.db'}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        from app.db import get_db
        def db_override():
            with factory() as session:
                yield session
        app.dependency_overrides[get_db] = db_override
        try:
            client = TestClient(app)
            assert client.get('/health').status_code == 200
            assert client.get('/ready').json() == {'status': 'ready'}
            assert client.get('/api/v1/monitors').status_code == 401
        finally:
            app.dependency_overrides.clear()
            engine.dispose()


def test_claim_recovery_and_stale_claim_rejection(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        engine = create_engine(f"sqlite+pysqlite:///{Path(directory) / 'leases.db'}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(worker, 'SessionLocal', factory)
        with factory.begin() as session:
            session.add(models.Monitor(name='Example', url='https://example.com', next_check_at=models.now() - timedelta(seconds=10)))
        claim = worker.claim_due()
        assert claim and claim[0] == 1
        assert worker.claim_due() is None
        with factory.begin() as session:
            m = session.get(models.Monitor, 1)
            m.check_lease_until = models.now() - timedelta(seconds=1)
        recovered = worker.claim_due()
        assert recovered and recovered[1] != claim[1]
        outcome = Probe(True, 200, 30.0, None)
        worker.save_claimed_probe(*claim, outcome)
        with factory() as session:
            assert session.scalar(select(models.CheckResult)) is None
        worker.save_claimed_probe(*recovered, outcome)
        with factory() as session:
            assert session.scalar(select(models.CheckResult)) is not None
            m = session.get(models.Monitor, 1)
            assert m.check_lease_token is None
            assert m.check_lease_until is None
            assert m.next_check_at.replace(tzinfo=None) > models.now().replace(tzinfo=None)
        engine.dispose()

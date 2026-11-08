from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Incident, Monitor
from app.checks import Probe, save_probe, validate_target
import pytest

@pytest.fixture
def session():
    engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()

def test_incident_opens_after_three_failures_and_closes_on_recovery(session):
    monitor = Monitor(name='Demo', url='https://example.com', failure_threshold=3)
    session.add(monitor)
    session.commit()
    for _ in range(2):
        save_probe(session, monitor, Probe(False, 503, 100.0, 'Unexpected HTTP 503'))
    assert session.scalars(select(Incident)).all() == []
    save_probe(session, monitor, Probe(False, 503, 120.0, 'Unexpected HTTP 503'))
    incidents = session.scalars(select(Incident)).all()
    assert len(incidents) == 1 and incidents[0].resolved_at is None
    save_probe(session, monitor, Probe(False, 503, 120.0, 'Unexpected HTTP 503'))
    assert len(session.scalars(select(Incident)).all()) == 1
    save_probe(session, monitor, Probe(True, 200, 75.0, None))
    assert session.scalars(select(Incident)).first().resolved_at is not None
    assert monitor.consecutive_failures == 0

def test_private_ip_is_blocked():
    with pytest.raises(ValueError, match='blocked'):
        validate_target('http://127.0.0.1:8000/health')

def test_url_credentials_blocked():
    with pytest.raises(ValueError, match='credentials'):
        validate_target('https://user:pass@example.com')

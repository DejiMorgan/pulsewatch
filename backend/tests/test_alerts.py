import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import AlertEvent, AlertRule, Incident, Monitor
from app.checks import Probe, save_probe


@pytest.fixture
def session():
    engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_incident_alerts_are_deduplicated_and_recovery_sent_once(session):
    monitor = Monitor(name='Service', url='https://example.com', failure_threshold=2)
    session.add(monitor)
    session.flush()
    session.add(AlertRule(monitor_id=monitor.id, name='Pager', channel='email', destination='ops@example.com'))
    session.commit()
    failure = Probe(False, 503, 150, 'HTTP 503')
    save_probe(session, monitor, failure)
    assert session.scalars(select(AlertEvent)).all() == []
    save_probe(session, monitor, failure)
    assert len(session.scalars(select(AlertEvent)).all()) == 1
    save_probe(session, monitor, failure)
    assert len(session.scalars(select(AlertEvent)).all()) == 1
    save_probe(session, monitor, Probe(True, 200, 100, None))
    assert [event.event_type for event in session.scalars(select(AlertEvent).order_by(AlertEvent.id)).all()] == ['opened', 'resolved']
    save_probe(session, monitor, Probe(True, 200, 100, None))
    assert len(session.scalars(select(AlertEvent)).all()) == 2
    assert session.scalar(select(Incident)).resolved_at is not None


def test_disabled_rules_do_not_enqueue(session):
    monitor = Monitor(name='A', url='https://example.com', failure_threshold=1)
    session.add(monitor)
    session.flush()
    session.add(AlertRule(monitor_id=monitor.id, name='Disabled', channel='email',
                          destination='ops@example.com', is_active=False))
    session.commit()
    save_probe(session, monitor, Probe(False, 500, 10, 'HTTP 500'))
    assert session.scalars(select(AlertEvent)).all() == []


def test_alert_recovery_opt_out(session):
    monitor = Monitor(name='A', url='https://example.com', failure_threshold=1)
    session.add(monitor)
    session.flush()
    session.add(AlertRule(monitor_id=monitor.id, name='Open only', channel='email',
                          destination='ops@example.com', notify_on_recovery=False))
    session.commit()
    save_probe(session, monitor, Probe(False, 500, 10, 'HTTP 500'))
    save_probe(session, monitor, Probe(True, 200, 10, None))
    assert [a.event_type for a in session.scalars(select(AlertEvent)).all()] == ['opened']


def test_delivery_succeeds_and_records_attempt(session, monkeypatch):
    import app.alerts as alerts
    from sqlalchemy.orm import sessionmaker
    monitor = Monitor(name='Test', url='https://example.com', failure_threshold=1)
    session.add(monitor)
    session.flush()
    session.add(AlertRule(monitor_id=monitor.id, name='Email', channel='email', destination='ops@example.com'))
    session.commit()
    save_probe(session, monitor, Probe(False, 500, 10, 'down'))
    event_id = session.scalar(select(AlertEvent)).id
    monkeypatch.setattr(alerts, 'SessionLocal', sessionmaker(bind=session.bind))
    recorded = []
    monkeypatch.setattr(alerts, 'deliver', lambda channel, destination, payload: recorded.append(payload))
    alerts.process_alert(event_id)
    session.expire_all()
    event = session.get(AlertEvent, event_id)
    assert event.status == 'sent' and event.attempts == 1 and event.delivered_at
    assert recorded[0]['event_type'] == 'opened'


def test_failed_delivery_retries_then_exhausts(session, monkeypatch):
    import app.alerts as alerts
    from sqlalchemy.orm import sessionmaker
    monitor = Monitor(name='Test', url='https://example.com', failure_threshold=1)
    session.add(monitor)
    session.flush()
    session.add(AlertRule(monitor_id=monitor.id, name='Email', channel='email', destination='ops@example.com'))
    session.commit()
    save_probe(session, monitor, Probe(False, 500, 10, 'down'))
    event_id = session.scalar(select(AlertEvent)).id
    monkeypatch.setattr(alerts, 'SessionLocal', sessionmaker(bind=session.bind))
    monkeypatch.setattr(alerts.settings, 'alert_max_attempts', 2)
    def broken(*args):
        raise RuntimeError('SMTP offline')
    monkeypatch.setattr(alerts, 'deliver', broken)
    alerts.process_alert(event_id)
    session.expire_all()
    assert session.get(AlertEvent, event_id).status == 'retry'
    alerts.process_alert(event_id)
    session.expire_all()
    result = session.get(AlertEvent, event_id)
    assert result.status == 'failed' and result.attempts == 2
    assert 'SMTP offline' in result.last_error

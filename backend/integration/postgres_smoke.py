"""Run after Alembic upgrade against a disposable PostgreSQL CI database.

DATABASE_URL must use postgresql+psycopg. Creates an isolated monitor, exercises
incident persistence, verifies recovery, and removes the monitor. The schema
is managed by Alembic, not by create_all().
"""
import os
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app import models
from app.checks import Probe, save_probe

url = os.environ['DATABASE_URL']
if not url.startswith('postgresql+psycopg://'):
    raise SystemExit('PostgreSQL smoke test requires a PostgreSQL database')
engine = create_engine(url, pool_pre_ping=True)
with engine.begin() as conn:
    version = conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    assert version == '0003_accounts', f'Unexpected migration version: {version}'
with Session(engine) as db:
    monitor = models.Monitor(name='CI PostgreSQL smoke', url='https://example.com', failure_threshold=2)
    db.add(monitor)
    db.commit()
    monitor_id = monitor.id
    try:
        save_probe(db, monitor, Probe(False, 503, 230.0, 'failure'))
        save_probe(db, monitor, Probe(False, 503, 250.0, 'failure'))
        incident = db.scalar(select(models.Incident).where(models.Incident.monitor_id == monitor_id))
        assert incident is not None and incident.resolved_at is None
        save_probe(db, monitor, Probe(True, 200, 110.0, None))
        db.refresh(incident)
        assert incident.resolved_at is not None
        assert db.scalar(select(models.CheckResult).where(models.CheckResult.monitor_id == monitor_id).limit(1))
        print('PASS: PostgreSQL migrations, check persistence, incidents and recovery')
    finally:
        db.delete(monitor)
        db.commit()
engine.dispose()

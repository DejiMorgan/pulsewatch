import logging
import time
import uuid
from datetime import timedelta
from sqlalchemy import select
from app import models
from app.checks import probe, save_probe
from app.alerts import claim_alert, process_alert
from app.config import settings
from app.db import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('pulsewatch-worker')

def claim_due():
    """Atomically lease one due monitor. Expired leases are recoverable."""
    with SessionLocal.begin() as session:
        current = models.now()
        monitor = session.scalar(select(models.Monitor).where(
            models.Monitor.is_active.is_(True),
            models.Monitor.next_check_at <= current,
            (models.Monitor.check_lease_until.is_(None)) | (models.Monitor.check_lease_until <= current),
        ).order_by(models.Monitor.next_check_at, models.Monitor.id)
         .with_for_update(skip_locked=True).limit(1))
        if monitor is None:
            return None
        token = uuid.uuid4().hex
        monitor.check_lease_token = token
        monitor.check_lease_until = current + timedelta(seconds=settings.check_lease_seconds)
        return monitor.id, token


def save_claimed_probe(monitor_id, token, outcome):
    """Discard stale claims after lease expiry and claim transfer."""
    with SessionLocal() as session:
        monitor = session.scalar(select(models.Monitor).where(
            models.Monitor.id == monitor_id).with_for_update())
        if not monitor or monitor.check_lease_token != token:
            log.warning('Discarding stale probe for monitor=%s', monitor_id)
            return
        save_probe(session, monitor, outcome, commit=False)
        monitor.check_lease_token = None
        monitor.check_lease_until = None
        monitor.next_check_at = models.now() + timedelta(seconds=monitor.interval_seconds)
        session.commit()


def run():
    log.info('Worker started')
    while True:
        try:
            event_id = claim_alert()
            if event_id is not None:
                process_alert(event_id)
                continue
            claim = claim_due()
            if claim is None:
                time.sleep(settings.worker_poll_seconds)
                continue
            monitor_id, token = claim
            with SessionLocal() as session:
                monitor = session.get(models.Monitor, monitor_id)
                target = (monitor.url, monitor.method, monitor.expected_status) if monitor and monitor.is_active else None
            if target is not None:
                outcome = probe(*target)
                save_claimed_probe(monitor_id, token, outcome)
                log.info('monitor=%s success=%s latency_ms=%s', monitor_id, outcome.success, outcome.latency_ms)
        except Exception:
            log.exception('Worker failure; retrying')
            time.sleep(settings.worker_poll_seconds)

if __name__ == '__main__':
    run()

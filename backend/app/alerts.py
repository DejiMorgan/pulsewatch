"""Durable incident notification outbox and bounded-delivery integrations."""
import logging
import smtplib
from datetime import timedelta
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.checks import validate_target
from app.config import settings
from app.db import SessionLocal

log = logging.getLogger('pulsewatch-alerts')


def queue_incident_events(session: Session, incident: models.Incident, event_type: str) -> None:
    """Call inside the same transaction as the incident state change."""
    rules = session.scalars(select(models.AlertRule).where(
        models.AlertRule.monitor_id == incident.monitor_id,
        models.AlertRule.is_active.is_(True),
        models.AlertRule.notify_on_open.is_(True) if event_type == 'opened'
        else models.AlertRule.notify_on_recovery.is_(True),
    )).all()
    for rule in rules:
        # One event per incident transition and rule (DB unique constraint).
        session.add(models.AlertEvent(
            alert_rule_id=rule.id, incident_id=incident.id, event_type=event_type,
            status='pending', next_attempt_at=models.now(),
        ))


def deliver(channel: str, destination: str, payload: dict) -> None:
    if channel == 'webhook':
        # DNS is validated at creation and again before each delivery. This
        # reduces SSRF risk, but production needs network egress controls to
        # prevent DNS-rebinding / connect-time resolution gaps.
        validate_target(destination, allow_private=False)
        from app.safe_http import safe_client
        with safe_client(settings.alert_timeout_seconds) as client:
            response = client.post(destination, json=payload)
            response.raise_for_status()
    elif channel == 'email':
        if not settings.smtp_host or not settings.smtp_from:
            raise RuntimeError('SMTP_HOST and SMTP_FROM must be configured')
        msg = EmailMessage()
        msg['From'] = settings.smtp_from
        msg['To'] = destination
        msg['Subject'] = f"[PulseWatch] {payload['event_type'].upper()}: {payload['monitor_name']}"
        msg.set_content('\n'.join(f'{key}: {value}' for key, value in payload.items()))
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.alert_timeout_seconds) as server:
            if settings.smtp_starttls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
    else:
        raise ValueError('Invalid alert channel')


def claim_alert() -> int | None:
    with SessionLocal.begin() as session:
        event = session.scalar(select(models.AlertEvent).where(
            models.AlertEvent.status.in_(['pending', 'retry']),
            models.AlertEvent.next_attempt_at <= models.now(),
            (models.AlertEvent.locked_until.is_(None)) | (models.AlertEvent.locked_until < models.now()),
        ).order_by(models.AlertEvent.next_attempt_at, models.AlertEvent.id)
            .with_for_update(skip_locked=True).limit(1))
        if event is None:
            return None
        event.locked_until = models.now() + timedelta(seconds=settings.alert_lease_seconds)
        return event.id


def process_alert(event_id: int) -> None:
    """Perform network I/O without a database lock; persist delivery outcome."""
    with SessionLocal() as session:
        event = session.get(models.AlertEvent, event_id)
        if event is None or event.status not in ('pending', 'retry'):
            return
        rule = session.get(models.AlertRule, event.alert_rule_id)
        incident = session.get(models.Incident, event.incident_id)
        monitor = session.get(models.Monitor, incident.monitor_id) if incident else None
        if not (rule and incident and monitor):
            error = 'Alert references an unavailable rule, incident, or monitor'
            success = False
        else:
            payload = {
                'event_id': event.id, 'event_type': event.event_type,
                'incident_id': incident.id, 'monitor_id': monitor.id,
                'monitor_name': monitor.name, 'incident_reason': incident.reason,
                'opened_at': incident.opened_at.isoformat(),
                'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None,
            }
            try:
                deliver(rule.channel, rule.destination, payload)
                success, error = True, None
            except Exception as exc:
                success, error = False, f'{type(exc).__name__}: {str(exc)[:300]}'
                log.warning('alert_id=%s delivery failed: %s', event_id, error)
        # Update under a row lock to avoid stale writes after lease expiry.
        event = session.scalar(select(models.AlertEvent).where(models.AlertEvent.id == event_id).with_for_update())
        if event is None or event.status not in ('pending', 'retry'):
            return
        event.attempts += 1
        event.locked_until = None
        event.last_error = error
        if success:
            event.status = 'sent'
            event.delivered_at = models.now()
        elif event.attempts >= settings.alert_max_attempts:
            event.status = 'failed'
        else:
            event.status = 'retry'
            event.next_attempt_at = models.now() + timedelta(seconds=min(300, 2 ** event.attempts * 10))
        session.commit()

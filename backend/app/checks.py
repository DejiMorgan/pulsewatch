import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlsplit
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models
from app.config import settings

@dataclass
class Probe:
    success: bool
    status_code: int | None
    latency_ms: float | None
    error: str | None

def validate_target(url: str, *, allow_private: bool = False) -> None:
    from app.safe_http import validate_public_url
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('Only HTTP(S) URLs are supported')
    if parsed.username or parsed.password:
        raise ValueError('Embedded URL credentials are not supported')
    if not allow_private:
        validate_public_url(url)

def probe(url: str, method: str, expected_status: int) -> Probe:
    try:
        validate_target(url, allow_private=settings.allow_private_targets)
        start = time.perf_counter()
        # No redirects, and no inherited environment proxies.
        from app.safe_http import safe_client
        with safe_client(settings.check_timeout_seconds, allow_private=settings.allow_private_targets) as client:
            response = client.request(method, url)
        latency = round((time.perf_counter() - start) * 1000, 2)
        success = response.status_code == expected_status
        return Probe(success, response.status_code, latency, None if success else f'Unexpected HTTP {response.status_code}')
    except (ValueError, httpx.HTTPError) as exc:
        return Probe(False, None, None, f'{type(exc).__name__}: {str(exc)[:250]}')

def save_probe(session: Session, monitor: models.Monitor, result: Probe, *, commit: bool = True) -> models.CheckResult:
    # Serialize state transitions across manual and worker probes.
    session.refresh(monitor, with_for_update=True)
    item = models.CheckResult(monitor_id=monitor.id, success=result.success, status_code=result.status_code,
                              latency_ms=result.latency_ms, error=result.error)
    session.add(item)
    open_incident = session.scalar(select(models.Incident).where(models.Incident.monitor_id == monitor.id,
                                           models.Incident.resolved_at.is_(None)).order_by(models.Incident.id.desc()).limit(1))
    if result.success:
        monitor.consecutive_failures = 0
        if open_incident:
            open_incident.resolved_at = models.now()
            from app.alerts import queue_incident_events
            queue_incident_events(session, open_incident, 'resolved')
    else:
        monitor.consecutive_failures += 1
        if monitor.consecutive_failures >= monitor.failure_threshold and not open_incident:
            incident = models.Incident(monitor_id=monitor.id, reason=result.error or 'Health check failed')
            session.add(incident)
            session.flush()
            from app.alerts import queue_incident_events
            queue_incident_events(session, incident, 'opened')
    if commit:
        session.commit()
        session.refresh(item)
    else:
        session.flush()
    return item

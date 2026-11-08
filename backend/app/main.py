from datetime import datetime, timedelta, timezone
import hmac
from sqlalchemy import text as sql_text
from sqlalchemy.exc import SQLAlchemyError
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app import models, schemas
from app.checks import probe, save_probe, validate_target
from app.config import settings
from app.db import get_db
from app.auth import authenticate, require_admin, hash_password, verify_password, issue_session, token_digest
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import delete

app = FastAPI(title='PulseWatch API', version='0.5.0')

if settings.environment == 'production':
    if settings.allow_private_targets:
        raise RuntimeError('ALLOW_PRIVATE_TARGETS must be false in production')

# Roles are enforced at the route boundary; development API key is disabled in production.
require_key = authenticate

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)

class NewUser(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)
    role: str = 'viewer'

@app.post('/api/v1/auth/login')
def login(body: LoginRequest, session: Session = Depends(get_db)):
    user = session.scalar(select(models.User).where(models.User.email == str(body.email).lower()))
    if not user or not user.is_active:
        raise HTTPException(401, 'Invalid credentials')
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > models.now():
        raise HTTPException(429, 'Account temporarily locked')
    if not verify_password(body.password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until = models.now() + timedelta(minutes=15)
            user.failed_logins = 0
        session.commit()
        raise HTTPException(401, 'Invalid credentials')
    user.failed_logins = 0
    user.locked_until = None
    session.commit()
    return {'access_token': issue_session(session, user), 'token_type': 'bearer',
            'expires_in': 43200, 'role': user.role}

@app.get('/api/v1/auth/me')
def me(user: models.User | None = Depends(authenticate)):
    return {'email': user.email if user else 'development-admin',
            'role': user.role if user else 'admin'}

@app.post('/api/v1/auth/logout', status_code=204)
def logout(authorization: str | None = Header(None), user=Depends(authenticate), session: Session = Depends(get_db)):
    if authorization and authorization.startswith('Bearer '):
        session.execute(delete(models.LoginSession).where(models.LoginSession.token_hash == token_digest(authorization[7:])))
        session.commit()

@app.post('/api/v1/users', status_code=201, dependencies=[Depends(require_admin)])
def add_user(body: NewUser, session: Session = Depends(get_db)):
    if body.role not in {'admin', 'viewer'}:
        raise HTTPException(422, 'role must be admin or viewer')
    email = str(body.email).lower()
    if session.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(409, 'User already exists')
    user = models.User(email=email, password_hash=hash_password(body.password), role=body.role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return {'id': user.id, 'email': user.email, 'role': user.role}

@app.get('/api/v1/users', dependencies=[Depends(require_admin)])
def list_users(session: Session = Depends(get_db)):
    return [{'id': u.id, 'email': u.email, 'role': u.role, 'is_active': u.is_active}
            for u in session.scalars(select(models.User).order_by(models.User.id)).all()]

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/ready')
def ready(session: Session = Depends(get_db)):
    try:
        session.execute(sql_text('SELECT 1'))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail='Database unavailable') from exc
    return {'status': 'ready'}

@app.post('/api/v1/monitors', response_model=schemas.MonitorOut, status_code=201, dependencies=[Depends(require_admin)])
def create_monitor(data: schemas.MonitorCreate, session: Session = Depends(get_db)):
    try:
        validate_target(str(data.url), allow_private=settings.allow_private_targets)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    monitor = models.Monitor(**{**data.model_dump(exclude={'url'}), 'url': str(data.url)})
    session.add(monitor)
    session.commit()
    session.refresh(monitor)
    return monitor

@app.get('/api/v1/monitors', response_model=list[schemas.MonitorOut], dependencies=[Depends(require_key)])
def list_monitors(session: Session = Depends(get_db)):
    return session.scalars(select(models.Monitor).order_by(models.Monitor.id)).all()

@app.patch('/api/v1/monitors/{monitor_id}', response_model=schemas.MonitorOut, dependencies=[Depends(require_admin)])
def update_monitor(monitor_id: int, data: schemas.MonitorUpdate, session: Session = Depends(get_db)):
    monitor = session.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(404, 'Monitor not found')
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(monitor, field, value)
    session.commit()
    session.refresh(monitor)
    return monitor

@app.delete('/api/v1/monitors/{monitor_id}', status_code=204, dependencies=[Depends(require_admin)])
def delete_monitor(monitor_id: int, session: Session = Depends(get_db)):
    monitor = session.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(404, 'Monitor not found')
    session.delete(monitor)
    session.commit()

@app.post('/api/v1/monitors/{monitor_id}/check', response_model=schemas.CheckOut, dependencies=[Depends(require_admin)])
def check_now(monitor_id: int, session: Session = Depends(get_db)):
    monitor = session.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(404, 'Monitor not found')
    return save_probe(session, monitor, probe(monitor.url, monitor.method, monitor.expected_status))

@app.get('/api/v1/monitors/{monitor_id}/metrics', dependencies=[Depends(require_key)])
def metrics(monitor_id: int, hours: int = Query(24, ge=1, le=720), session: Session = Depends(get_db)):
    if not session.get(models.Monitor, monitor_id):
        raise HTTPException(404, 'Monitor not found')
    since = models.now() - timedelta(hours=hours)
    rows = session.scalars(select(models.CheckResult).where(models.CheckResult.monitor_id == monitor_id,
                          models.CheckResult.checked_at >= since).order_by(models.CheckResult.checked_at.desc()).limit(10000)).all()
    latencies = sorted(r.latency_ms for r in rows if r.latency_ms is not None)
    def percentile(p):
        if not latencies:
            return None
        return latencies[round((len(latencies)-1) * p)]
    return {'monitor_id': monitor_id, 'window_hours': hours, 'sample_count': len(rows),
            'availability_pct': round(100 * sum(r.success for r in rows) / len(rows), 2) if rows else None,
            'avg_latency_ms': round(sum(latencies)/len(latencies), 2) if latencies else None,
            'p50_latency_ms': percentile(0.5), 'p95_latency_ms': percentile(0.95), 'p99_latency_ms': percentile(0.99),
            'checks': [schemas.CheckOut.model_validate(r).model_dump(mode='json') for r in rows[:200]]}

@app.get('/api/v1/incidents', response_model=list[schemas.IncidentOut], dependencies=[Depends(require_key)])
def list_incidents(session: Session = Depends(get_db)):
    return session.scalars(select(models.Incident).order_by(models.Incident.opened_at.desc()).limit(200)).all()

@app.get('/api/v1/dashboard/summary', dependencies=[Depends(require_key)])
def summary(session: Session = Depends(get_db)):
    return {'monitored_apis': session.scalar(select(func.count(models.Monitor.id))),
            'active_monitors': session.scalar(select(func.count(models.Monitor.id)).where(models.Monitor.is_active.is_(True))),
            'open_incidents': session.scalar(select(func.count(models.Incident.id)).where(models.Incident.resolved_at.is_(None)))}

@app.post('/api/v1/alert-rules', response_model=schemas.AlertRuleOut, status_code=201, dependencies=[Depends(require_admin)])
def create_alert_rule(data: schemas.AlertRuleCreate, session: Session = Depends(get_db)):
    from app.alerts import validate_target
    if session.get(models.Monitor, data.monitor_id) is None:
        raise HTTPException(404, 'Monitor not found')
    if data.channel == 'webhook':
        try:
            validate_target(data.destination, allow_private=False)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not data.destination.startswith('https://'):
            raise HTTPException(422, 'Webhook delivery requires HTTPS')
    elif not __import__('re').fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', data.destination):
        raise HTTPException(422, 'Invalid email destination')
    rule = models.AlertRule(**data.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule

@app.get('/api/v1/alert-rules', response_model=list[schemas.AlertRuleOut], dependencies=[Depends(require_key)])
def list_alert_rules(monitor_id: int | None = None, session: Session = Depends(get_db)):
    query = select(models.AlertRule).order_by(models.AlertRule.id)
    if monitor_id is not None:
        query = query.where(models.AlertRule.monitor_id == monitor_id)
    return session.scalars(query).all()

@app.delete('/api/v1/alert-rules/{rule_id}', status_code=204, dependencies=[Depends(require_admin)])
def delete_alert_rule(rule_id: int, session: Session = Depends(get_db)):
    rule = session.get(models.AlertRule, rule_id)
    if rule is None:
        raise HTTPException(404, 'Alert rule not found')
    # Historical deliveries reference the rule: disable it instead of deleting.
    rule.is_active = False
    session.commit()

@app.get('/api/v1/alert-events', response_model=list[schemas.AlertEventOut], dependencies=[Depends(require_key)])
def list_alert_events(monitor_id: int | None = None, session: Session = Depends(get_db)):
    query = select(models.AlertEvent).order_by(models.AlertEvent.id.desc()).limit(200)
    if monitor_id is not None:
        query = query.join(models.Incident).where(models.Incident.monitor_id == monitor_id)
    return session.scalars(query).all()

@app.get('/api/v1/incidents/{incident_id}/report', dependencies=[Depends(require_key)])
def incident_report(incident_id: int, session: Session = Depends(get_db)):
    incident = session.get(models.Incident, incident_id)
    if incident is None:
        raise HTTPException(404, 'Incident not found')
    monitor = session.get(models.Monitor, incident.monitor_id)
    end = incident.resolved_at or models.now()
    duration = max(0, (end - incident.opened_at).total_seconds())
    return {'incident_id': incident.id, 'monitor_id': incident.monitor_id,
            'monitor_name': monitor.name, 'reason': incident.reason,
            'status': 'resolved' if incident.resolved_at else 'open',
            'opened_at': incident.opened_at, 'resolved_at': incident.resolved_at,
            'duration_seconds': round(duration, 2),
            'notification_events': [{'id': e.id, 'type': e.event_type, 'status': e.status}
                 for e in session.scalars(select(models.AlertEvent).where(models.AlertEvent.incident_id == incident.id)).all()]}

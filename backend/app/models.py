from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

def now():
    return datetime.now(timezone.utc)

class Monitor(Base):
    __tablename__ = "monitors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(2048))
    method: Mapped[str] = mapped_column(String(10), default="GET")
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    failure_threshold: Mapped[int] = mapped_column(Integer, default=3)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    check_lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    check_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    checks: Mapped[list['CheckResult']] = relationship(back_populates="monitor", cascade="all, delete-orphan")
    incidents: Mapped[list['Incident']] = relationship(back_populates="monitor", cascade="all, delete-orphan")

class CheckResult(Base):
    __tablename__ = "check_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey('monitors.id', ondelete='CASCADE'))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    monitor: Mapped[Monitor] = relationship(back_populates="checks")
    __table_args__ = (Index('ix_checks_monitor_time', 'monitor_id', 'checked_at'),)

class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey('monitors.id', ondelete='CASCADE'))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    monitor: Mapped[Monitor] = relationship(back_populates="incidents")
    __table_args__ = (Index('ix_incidents_monitor_resolved', 'monitor_id', 'resolved_at'),)


class AlertRule(Base):
    __tablename__ = 'alert_rules'
    id: Mapped[int] = mapped_column(primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey('monitors.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(20))  # email | webhook
    destination: Mapped[str] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_open: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_recovery: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (Index('ix_alert_rules_monitor', 'monitor_id'),)


class AlertEvent(Base):
    __tablename__ = 'alert_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_rule_id: Mapped[int] = mapped_column(ForeignKey('alert_rules.id', ondelete='CASCADE'))
    incident_id: Mapped[int] = mapped_column(ForeignKey('incidents.id', ondelete='CASCADE'))
    event_type: Mapped[str] = mapped_column(String(20))  # opened | resolved
    status: Mapped[str] = mapped_column(String(20), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (
        UniqueConstraint('alert_rule_id', 'incident_id', 'event_type', name='uq_alert_transition'),
        Index('ix_alert_events_pending', 'status', 'next_attempt_at'),
    )


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default='viewer')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class LoginSession(Base):
    __tablename__ = 'login_sessions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

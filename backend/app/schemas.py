from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from typing import Literal

class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    method: Literal['GET', 'HEAD'] = 'GET'
    expected_status: int = Field(default=200, ge=100, le=599)
    interval_seconds: int = Field(default=60, ge=30, le=86400)
    failure_threshold: int = Field(default=3, ge=1, le=20)

class MonitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    interval_seconds: int | None = Field(default=None, ge=30, le=86400)
    failure_threshold: int | None = Field(default=None, ge=1, le=20)
    is_active: bool | None = None

class MonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    url: str
    method: str
    expected_status: int
    interval_seconds: int
    failure_threshold: int
    consecutive_failures: int
    is_active: bool
    next_check_at: datetime

class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    monitor_id: int
    checked_at: datetime
    latency_ms: float | None
    status_code: int | None
    success: bool
    error: str | None

class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    monitor_id: int
    opened_at: datetime
    resolved_at: datetime | None
    reason: str

class AlertRuleCreate(BaseModel):
    monitor_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    channel: Literal['email', 'webhook']
    destination: str = Field(min_length=3, max_length=2048)
    notify_on_open: bool = True
    notify_on_recovery: bool = True

class AlertRuleOut(AlertRuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime

class AlertEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alert_rule_id: int
    incident_id: int
    event_type: str
    status: str
    attempts: int
    delivered_at: datetime | None
    last_error: str | None

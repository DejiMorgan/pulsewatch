import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://pulsewatch:pulsewatch@db:5432/pulsewatch"
    api_key: str = "change-me-before-deployment"
    environment: str = "development"
    allow_private_targets: bool = False
    check_timeout_seconds: float = 8.0
    worker_poll_seconds: float = 2.0
    check_lease_seconds: int = 60
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_from: str = ''
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_starttls: bool = True
    alert_timeout_seconds: float = 8.0
    alert_lease_seconds: int = 60
    alert_max_attempts: int = 5
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

settings = Settings()

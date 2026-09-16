from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./dev.db"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    limitless_base_url: str = "https://play.limitlesstcg.com"
    limitless_username: str = ""
    limitless_password: str = ""
    limitless_application_id: str = ""

    discord_webhook_url: str = ""
    dashboard_base_url: str = ""

    cors_allowed_origins: str = "http://localhost:5173"

    application_status_check_interval_hours: int = 4
    resubmit_times_utc: str = "09:00,21:00"
    tournament_ingest_interval_hours: int = 1
    tournament_ingest_limit: int = 1000
    tournament_backfill_months: int = 3

    organizer_scan_interval_hours: int = 24
    organizer_scan_limit: int = 50
    organizer_scan_start_id: int = 2722

    session_validation_timeout_ms: int = 10000

    scraper_debug: bool = False

    display_timezone: str = "America/Chicago"

    api_keys: str = ""


settings = Settings()

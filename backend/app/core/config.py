from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="d:/Project/BlinkChat/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    secret_key: str = Field(default_factory=lambda: secrets.token_hex(32))
    algorithm: str = "HS256"

    database_url: str = "sqlite+aiosqlite:///d:/Project/BlinkChat/blinkchat.db"

    # Session cookie
    session_cookie_name: str = "blinkchat_session"
    session_max_age: int = 3600  # 1 hour

    # Room lifecycle
    temp_room_max_lifetime_seconds: int = 4 * 3600       # 4 hours
    temp_room_inactivity_timeout_seconds: int = 30 * 60  # 30 minutes
    saved_room_max_lifetime_seconds: int = 7 * 24 * 3600 # 7 days

    # Reconnect grace period
    reconnect_grace_seconds: int = 60

    # Message limits
    max_message_length: int = 4000

    # Rate limiting
    join_rate_limit: str = "10/minute"

    # CORS
    allowed_origins: list[str] = ["http://127.0.0.1:8000", "http://localhost:8000"]

    # Production flag
    is_production: bool = False


settings = Settings()

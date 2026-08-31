from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Restaurant Order Management System"
    API_V1_STR: str = "/api"

    # Database - required from environment
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        # Normalize PostgreSQL URL formats from cloud providers (e.g., Render/Supabase)
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    # Security & JWT Authentication - required from environment
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Slow-Order Alerts Configuration (in minutes)
    ALERT_THRESHOLD_MINUTES: int = 15
    ALERT_REAPPEAR_MINUTES: int = 10

    # CORS Configuration
    CORS_ORIGINS: List[Union[str, AnyHttpUrl]] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ]

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

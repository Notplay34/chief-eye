import secrets
from typing import Literal, Optional

from pydantic import Field, PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/eye_w"
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 дней

    # Суперпользователь создаётся только если все SUPERUSER_* заданы явно.
    superuser_login: Optional[str] = None
    superuser_password: Optional[str] = None
    superuser_name: Optional[str] = None

    # CORS: через переменную CORS_ORIGINS (через запятую).
    # По умолчанию разрешены только локальные origin для разработки.
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,http://127.0.0.1:3000"
    _generated_jwt_secret: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if not self.jwt_secret:
            if self.app_env == "production":
                raise ValueError("JWT_SECRET must be set when APP_ENV=production")
            self.jwt_secret = secrets.token_urlsafe(32)
            self._generated_jwt_secret = True

        if self.app_env == "production":
            origins = self.cors_origin_list
            if not origins or "*" in origins:
                raise ValueError("CORS_ORIGINS must be explicitly set when APP_ENV=production")

        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in (self.cors_origins or "").split(",") if origin.strip()]

    @property
    def generated_jwt_secret(self) -> bool:
        return self._generated_jwt_secret

    @property
    def should_create_superuser(self) -> bool:
        return bool(self.superuser_login and self.superuser_password and self.superuser_name)

    @property
    def has_partial_superuser_config(self) -> bool:
        values = [self.superuser_login, self.superuser_password, self.superuser_name]
        return any(values) and not all(values)


settings = Settings()

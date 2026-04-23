from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/eye_w"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 дней

    # Суперпользователь создаётся при первом запуске, если такого логина ещё нет.
    # Задайте в .env свои значения и смените пароль после первого входа.
    superuser_login: str = "sergey151"
    superuser_password: str = "1wq21wq2"
    superuser_name: str = "Сергей"

    # CORS: через переменную CORS_ORIGINS (через запятую, например https://eye34z.duckdns.org,http://localhost:3000).
    # Не задано или пусто — разрешаются все origins (для разработки).
    cors_origins: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

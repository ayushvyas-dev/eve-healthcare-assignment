from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://user:password@localhost/eve_healthcare"
    jwt_secret_key: str = "development-only-change-this-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    redis_url: str = "redis://localhost:6379/0"
    webhook_signing_secret: str = "development-webhook-secret"
    environment: str = "development"

    @field_validator("database_url")
    @classmethod
    def use_async_postgres_driver(cls, value: str) -> str:
        # Hosted Postgres providers commonly supply postgresql:// URLs. The
        # service uses SQLAlchemy's async engine, so explicitly select asyncpg.
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        if value.startswith("postgresql+psycopg://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql+psycopg://")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

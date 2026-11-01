from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
                                      case_sensitive=False, extra="ignore")

    app_name: str = "CampusGuard API"
    app_version: str = "3.0.0"
    environment: str = "development"
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "campusguard"
    db_password: SecretStr
    db_name: str = "campusguard"
    secret_key: SecretStr = Field(min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    refresh_token_expire_days: int = Field(default=7, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

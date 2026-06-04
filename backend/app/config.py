from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./siem_dev.db"
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False

    # JWT — en prod las claves vienen de variables de entorno (strings)
    # En dev se leen desde archivos .pem
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_private_key_path: str = "./keys/private.pem"
    jwt_public_key_path: str = "./keys/public.pem"
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 60

    app_env: str = "development"
    cors_origins: str = "http://localhost:5173"

    rate_limit_per_minute: int = 60
    ingest_rate_limit_per_minute: int = 300

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def private_key(self) -> str:
        # Prioridad: variable de entorno → archivo .pem
        if self.jwt_private_key:
            return self.jwt_private_key.replace("\\n", "\n")
        with open(self.jwt_private_key_path) as f:
            return f.read()

    @property
    def public_key(self) -> str:
        if self.jwt_public_key:
            return self.jwt_public_key.replace("\\n", "\n")
        with open(self.jwt_public_key_path) as f:
            return f.read()

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()

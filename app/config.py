import os
from pydantic import BaseModel
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    """Everything configurable comes from environment variables (see .env.example)."""

    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: str = os.getenv("POSTGRES_PORT", "5432")
    postgres_db: str = os.getenv("POSTGRES_DB", "postgres")

    app_port: int = int(os.getenv("API_PORT", 8000))
    env: str = os.getenv("API_ENV", "dev")


@lru_cache()
def get_settings():
    """Settings are built once and cached, so every import shares the same object."""
    return Settings()

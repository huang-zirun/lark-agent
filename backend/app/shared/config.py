from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "DevFlow Engine"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/devflow.db"
    ARTIFACT_STORAGE_PATH: str = "./data/artifacts"
    WORKSPACE_ROOT_PATH: str = "./data/workspaces"

    ENCRYPTION_KEY: str = "devflow-default-encryption-key-32b"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def ensure_directories():
    Path(settings.ARTIFACT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.WORKSPACE_ROOT_PATH).mkdir(parents=True, exist_ok=True)
    Path("./data").mkdir(parents=True, exist_ok=True)

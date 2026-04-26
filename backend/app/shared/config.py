from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "DevFlow Engine"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/devflow.db"
    ARTIFACT_STORAGE_PATH: str = "./data/artifacts"
    WORKSPACE_ROOT_PATH: str = "./data/workspaces"
    LOG_DIR: str = "./data/logs"

    ENCRYPTION_KEY: str = "devflow-default-encryption-key-32b"

    DEFAULT_PROVIDER_TYPE: str = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_DEFAULT_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_DEFAULT_MODEL: str = "claude-sonnet-4-20250514"

    LLM_TIMEOUT_SECONDS: int = 120
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BASE_DELAY: float = 1.0

    TEST_COMMAND: str = "uv run pytest -xvs"
    TEST_TIMEOUT: int = 300

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def ensure_directories():
    Path(settings.ARTIFACT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.WORKSPACE_ROOT_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path("./data").mkdir(parents=True, exist_ok=True)

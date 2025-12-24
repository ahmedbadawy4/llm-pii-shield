import os
from dataclasses import dataclass
from pathlib import Path


def _str_to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    ollama_base_url: str
    database_path: Path
    log_level: str
    redact_assistant: bool
    admin_api_key: str | None
    llm_provider: str
    azure_openai_endpoint: str | None
    azure_openai_deployment: str | None


def load_settings() -> Settings:
    """
    Read configuration from environment variables with safe defaults.
    """
    db_path = Path(os.getenv("DATABASE_PATH", "./data/audit.db")).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        ollama_base_url=os.getenv(
            "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
        ),
        database_path=db_path,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        redact_assistant=_str_to_bool(os.getenv("REDACT_ASSISTANT"), False),
        admin_api_key=os.getenv("ADMIN_API_KEY"),
        llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    )

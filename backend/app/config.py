"""Configuration management for aria-local-agent."""

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment or defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server binding
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    aria_env: str = Field(default="development", alias="ARIA_ENV")

    # Local data storage (~/.aria/)
    aria_data_dir: str = Field(default="~/.aria", alias="ARIA_DATA_DIR")
    aria_secret_key: str = Field(default="", alias="ARIA_SECRET_KEY")

    # Ollama runtime settings
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_chat_model: str = Field(default="qwen2.5:7b-instruct", alias="OLLAMA_CHAT_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="OLLAMA_EMBED_MODEL")

    # CORS settings for frontend & Tailscale clients
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    @property
    def data_dir_path(self) -> Path:
        """Resolved absolute path to local data storage directory."""
        path = Path(self.aria_data_dir).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_path(self) -> Path:
        """Absolute path to the SQLite database file."""
        return self.data_dir_path / "aria.db"

    @property
    def persona_path(self) -> Path:
        """Absolute path to the user-editable persona markdown file."""
        return self.data_dir_path / "persona.md"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def get_or_create_secret_key(self) -> str:
        """Return the secret key, generating and saving one in data_dir if not set."""
        if self.aria_secret_key and self.aria_secret_key.strip():
            return self.aria_secret_key.strip()

        secret_file = self.data_dir_path / "secret.key"
        if secret_file.exists():
            return secret_file.read_text(encoding="utf-8").strip()

        generated = secrets.token_hex(32)
        secret_file.write_text(generated, encoding="utf-8")
        return generated


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()

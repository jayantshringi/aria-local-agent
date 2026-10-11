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

    # Phase 4: Agent Tool & Safety Controls
    folder_whitelist: str = Field(default="", alias="ARIA_FOLDER_WHITELIST")
    web_search_enabled: bool = Field(default=False, alias="ARIA_WEB_SEARCH_ENABLED")
    searxng_url: str = Field(default="http://127.0.0.1:8080", alias="SEARXNG_URL")
    shell_enabled: bool = Field(default=False, alias="ARIA_SHELL_ENABLED")
    shell_allowlist: str = Field(
        default="python,git,dir,ls,echo,date", alias="ARIA_SHELL_ALLOWLIST"
    )
    apps_allowlist: str = Field(
        default="notepad,calc,calculator,explorer,code", alias="ARIA_APPS_ALLOWLIST"
    )

    # Phase 5: Voice & Proactivity
    whisper_model: str = Field(default="base", alias="ARIA_WHISPER_MODEL")
    whisper_device: str = Field(default="cpu", alias="ARIA_WHISPER_DEVICE")
    whisper_compute_type: str = Field(default="int8", alias="ARIA_WHISPER_COMPUTE_TYPE")
    piper_voice_model: str = Field(default="en_US-lessac-medium", alias="ARIA_PIPER_VOICE_MODEL")
    piper_voice_dir: str = Field(default="", alias="ARIA_PIPER_VOICE_DIR")
    aria_language: str = Field(default="en", alias="ARIA_LANGUAGE")
    briefing_hour: int = Field(default=8, alias="ARIA_BRIEFING_HOUR")
    briefing_minute: int = Field(default=0, alias="ARIA_BRIEFING_MINUTE")
    reminder_poll_interval: int = Field(default=30, alias="ARIA_REMINDER_POLL_INTERVAL")

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

    @property
    def whitelisted_directories(self) -> list[Path]:
        """Parsed and resolved list of whitelisted directories for filesystem tools."""
        paths: list[Path] = []
        if self.folder_whitelist.strip():
            for p in self.folder_whitelist.split(","):
                clean = p.strip()
                if clean:
                    resolved = Path(clean).expanduser().resolve()
                    resolved.mkdir(parents=True, exist_ok=True)
                    paths.append(resolved)
        else:
            # Default to a dedicated sandbox subfolder inside ~/.aria/
            sandbox = self.data_dir_path / "sandbox"
            sandbox.mkdir(parents=True, exist_ok=True)
            paths.append(sandbox)
        return paths

    @property
    def allowed_shell_commands_list(self) -> list[str]:
        """Parsed list of allowed shell commands."""
        return [cmd.strip().lower() for cmd in self.shell_allowlist.split(",") if cmd.strip()]

    @property
    def allowed_apps_list(self) -> list[str]:
        """Parsed list of allowed applications."""
        return [app.strip().lower() for app in self.apps_allowlist.split(",") if app.strip()]

    @property
    def whisper_dir_path(self) -> Path:
        """Resolved path to local faster-whisper models directory."""
        path = self.data_dir_path / "models" / "whisper"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def piper_dir_path(self) -> Path:
        """Resolved path to local Piper TTS models directory."""
        if self.piper_voice_dir.strip():
            path = Path(self.piper_voice_dir).expanduser().resolve()
        else:
            path = self.data_dir_path / "models" / "piper"
        path.mkdir(parents=True, exist_ok=True)
        return path

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

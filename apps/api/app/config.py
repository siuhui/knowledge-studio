from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_env_dir = Path(__file__).resolve().parent.parent  # apps/api/


class DatabaseConfig(BaseSettings):
    url: str
    pg_vector_extension: str = "vector"


class JWTConfig(BaseSettings):
    secret: SecretStr
    algorithm: str
    expiry_minutes: int


class ObjectStorageConfig(BaseSettings):
    endpoint: str
    access_key: str
    secret_key: SecretStr
    bucket: str
    region: str
    presign_expire_seconds: int
    max_upload_size_bytes: int
    public_endpoint: str | None = None  # override for presigned URLs (e.g. localhost vs docker hostname)


class EmbeddingConfig(BaseSettings):
    """Embedding provider configuration (OpenAI-compatible API).

    Uses DashScope text-embedding-v4 by default (1024 dim).
    """

    model_config = SettingsConfigDict(extra="ignore")

    api_key: SecretStr
    base_url: str | None = None
    model: str = "text-embedding-v4"
    dimension: int = 1024
    batch_size: int = 100


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    provider: str = "openai"
    api_key: SecretStr
    base_url: str | None = None
    chat_model: str = "gpt-4o-mini"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KB_",
        env_nested_delimiter="__",
        # Absolute paths so env_file works regardless of CWD
        env_file=(
            str(_env_dir / ".env"),
            str(_env_dir / ".env.local"),
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str
    env: str
    debug: bool

    database: DatabaseConfig
    jwt: JWTConfig
    llm: LLMConfig
    embedding: EmbeddingConfig
    object_storage: ObjectStorageConfig
    cors_origins: list[str]

    auto_create_tables: bool = True  # v0.x dev mode

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in ("dev", "test", "prod"):
            raise ValueError(f"env must be dev/test/prod, got {v}")
        return v


settings = Settings()  # type: ignore[call-arg]

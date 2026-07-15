from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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
    """Embedding provider configuration (OpenAI-compatible API)."""

    model_config = SettingsConfigDict(extra="ignore")

    api_key: SecretStr
    base_url: str | None = None
    model: str
    dimension: int
    batch_size: int


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    provider: str
    api_key: SecretStr
    base_url: str | None = None
    chat_model: str


class TelemetryConfig(BaseSettings):
    """OpenTelemetry + Langfuse Cloud observability (v4 SDK).

    Set KS_TELEMETRY__ENABLED=false to disable all tracing (e.g. in tests).
    Keys must be provided via env vars — no defaults for SecretStr fields.
    """

    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = False
    langfuse_secret_key: SecretStr | None = None
    langfuse_public_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    environment: str = "development"
    release: str | None = None  # LANGFUSE_RELEASE


class IngestionConfig(BaseSettings):
    """Web content ingestion configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    trafilatura_timeout: int = 30
    playwright_timeout: int = 30_000  # ms
    fallback_ratio: float = 0.2  # trafilatura extraction ratio below which Playwright is triggered


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KS_",
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
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    cors_origins: list[str]

    auto_create_tables: bool = False
    auto_create_bucket: bool = False

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in ("dev", "test", "prod"):
            raise ValueError(f"env must be dev/test/prod, got {v}")
        return v


settings = Settings()  # type: ignore[call-arg]

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    url: str  # postgresql://postgres:postgres@localhost:5432/knowledgebase
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


class LLMConfig(BaseSettings):
    provider: str = "openai"
    api_key: SecretStr
    base_url: str | None = None
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KB_",
        env_nested_delimiter="__",
        env_file=(".env", ".env.local"),
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

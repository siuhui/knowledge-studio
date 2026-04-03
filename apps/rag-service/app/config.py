from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "knowledge-base-rag-service"
    env: str = "dev"
    database_url: str = "sqlite:///./knowledge_base.db"
    auto_create_tables: bool = True
    object_storage_provider: str = "minio"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = "minioadmin"
    object_storage_bucket: str = "kb-source"
    object_storage_region: str = "us-east-1"
    object_storage_presign_expire_seconds: int = 900
    object_storage_max_upload_size_bytes: int = 20 * 1024 * 1024

    model_config = SettingsConfigDict(env_prefix="KB_", env_file=".env", extra="ignore")


settings = Settings()

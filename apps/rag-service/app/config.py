from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "knowledge-base-rag-service"
    database_url: str = "sqlite:///./knowledge_base.db"

    model_config = SettingsConfigDict(env_prefix="KB_", env_file=".env", extra="ignore")


settings = Settings()

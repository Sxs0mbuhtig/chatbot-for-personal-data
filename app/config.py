import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    TYPESENSE_HOST: str = "localhost"
    TYPESENSE_PORT: str = "8108"
    TYPESENSE_API_KEY: str = "xyz_secret_key_123"
    TYPESENSE_COLLECTION: str = "omnisense_lexicon"
    GEMINI_API_KEY: str = ""
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

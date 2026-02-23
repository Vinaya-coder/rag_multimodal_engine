import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    DATABASE_URL: str = Field(..., alias="DATABASE_URL")
    GEMINI_API_KEY: str = Field(..., alias="GEMINI_API_KEY")
    PROJECT_NAME: str = "Multimodal RAG Engine"
    UPLOAD_DIR: str = "file_vault/raw_uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def setup_directories(self):
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
settings = Settings()
settings.setup_directories()
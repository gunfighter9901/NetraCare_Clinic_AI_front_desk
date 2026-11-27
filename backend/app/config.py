from datetime import datetime
from functools import lru_cache
from os import getenv
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NETRACARE_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "sqlite:///./netracare.db"
    data_pack_path: Path = Path("../Project_Resources/data-pack-Iteration_01")
    data_pack_2_path: Path = Path("../Project_Resources/data-pack-Iteration_02")
    data_pack_3_path: Path = Path("../Project_Resources/data-pack-Iteration_03")
    clinic_timezone: str = "Asia/Kolkata"
    clinic_now: datetime | None = None
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    llm_timeout_seconds: float = 20.0
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY", "NETRACARE_GOOGLE_API_KEY"),
    )
    weaviate_url: str | None = Field(default=None, validation_alias=AliasChoices("WEAVIATE_URL"))
    weaviate_api_key: str | None = Field(default=None, validation_alias=AliasChoices("WEAVIATE_API_KEY"))
    rag_collection: str = "NetraCareChunks"
    rag_embedding_model: str = "Snowflake/snowflake-arctic-embed-m-v1.5"
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 100
    rag_top_k: int = 4

    @property
    def google_api_key(self) -> str | None:
        if self.llm_api_key:
            return self.llm_api_key
        return getenv("GOOGLE_API_KEY") or getenv("GEMINI_API_KEY") or getenv("NETRACARE_GOOGLE_API_KEY")

    @property
    def weaviate_cluster_url(self) -> str | None:
        url = self.weaviate_url or getenv("WEAVIATE_URL")
        if not url:
            return None
        url = url.strip().strip('"').strip("'")
        if url and not url.startswith("http"):
            url = "https://" + url
        return url or None

    @property
    def weaviate_key(self) -> str | None:
        if self.weaviate_api_key:
            return self.weaviate_api_key.strip().strip('"').strip("'")
        raw = getenv("WEAVIATE_API_KEY")
        return raw.strip().strip('"').strip("'") if raw else None


@lru_cache
def get_settings() -> Settings:
    return Settings()

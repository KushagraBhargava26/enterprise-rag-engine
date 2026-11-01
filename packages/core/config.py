from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_SECRET_KEY: str = "development-secret-key-32-chars-min"

    # Authentication & JWT
    JWT_SECRET: str = "supersecretkey-change-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rag_engine"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/rag_engine"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # S3 / MinIO Storage
    S3_ENDPOINT_URL: Optional[str] = "http://localhost:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "documents"
    S3_REGION: str = "us-east-1"
    S3_SECURE: bool = False

    # Model Provider: "mock", "gemini", "openai"
    MODEL_PROVIDER: str = "mock"
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    COMPLETION_MODEL: str = "gpt-4o-mini"
    EMBEDDING_DIMENSIONS: int = 1536

    # RAG parameters
    CHUNK_SIZE_TOKENS: int = 800
    CHUNK_OVERLAP_TOKENS: int = 100
    RETRIEVAL_TOP_K: int = 8
    MIN_RELEVANCE_SCORE: float = 0.3

    # Upload & rate limits
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_MIME_TYPES: List[str] = ["application/pdf"]

@lru_cache()
def get_settings() -> Settings:
    return Settings()

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Directory (relative to the backend working dir, or absolute) where
    # uploaded documents are persisted. Git-ignored at runtime.
    UPLOAD_DIR: str = "uploads"
    # Maximum allowed upload size in bytes (default 50 MB).
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024

    # --- Phase 5 & 6: Embeddings + Qdrant Vector Database ---
    # Qdrant connection URL (defaults to the docker-compose service).
    QDRANT_URL: str = "http://qdrant:6333"
    # Default Qdrant collection storing document chunk vectors.
    QDRANT_COLLECTION: str = "documents"
    # Default embedding provider name ("minilm", "bge" or "openai").
    DEFAULT_EMBEDDING_MODEL: str = "minilm"
    # Optional OpenAI API key — enables the OpenAI embedding provider.
    OPENAI_API_KEY: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
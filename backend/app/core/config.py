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

    class Config:
        env_file = ".env"

settings = Settings()
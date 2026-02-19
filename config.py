from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "bunkbuddies"
    
    # Google OAuth
    google_client_id: str = "dev-client-id"
    google_client_secret: str = "dev-client-secret"
    google_redirect_uri: str = "http://localhost:8000/auth/callback"
    
    # JWT
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    
    # Server
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

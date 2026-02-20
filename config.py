from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )
    
    # MongoDB
    mongodb_url: str = Field(default="mongodb://localhost:27017", validation_alias="MONGODB_URI")
    database_name: str = "bunkbuddies"
    
    # Google OAuth
    google_client_id: str = "dev-client-id"
    google_client_secret: str = "dev-client-secret"
    google_redirect_uri: str = "http://localhost:3000/api/auth/callback/google"
    
    # JWT
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    
    # Server
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 3000
    
settings = Settings()

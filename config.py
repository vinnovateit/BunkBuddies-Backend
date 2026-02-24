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
    port: int = Field(default=8000, validation_alias="PORT")

    # Public URLs / scheduled digests
    backend_public_url: str = Field(default="http://127.0.0.1:8000", validation_alias="BACKEND_PUBLIC_URL")
    frontend_public_url: str = Field(
        default="https://bunkbuddies.vinnovateit.com",
        validation_alias="FRONTEND_PUBLIC_URL",
    )
    nodemailer_api_url: str = Field(
        default="https://nodemailer-lac.vercel.app/api/send-email",
        validation_alias="NODEMAILER_API_URL",
    )
    nodemailer_timeout_seconds: int = Field(default=20, validation_alias="NODEMAILER_TIMEOUT_SECONDS")
    group_request_digest_enabled: bool = Field(default=True, validation_alias="GROUP_REQUEST_DIGEST_ENABLED")
    group_request_digest_interval_hours: int = Field(default=5, validation_alias="GROUP_REQUEST_DIGEST_INTERVAL_HOURS")
    group_request_digest_batch_size: int = Field(default=3, validation_alias="GROUP_REQUEST_DIGEST_BATCH_SIZE")
    
settings = Settings()

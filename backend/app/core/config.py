"""Application configuration using Pydantic BaseSettings."""
# ruff: noqa: I001 - Imports structured for Jinja2 template conditionals

from pathlib import Path
from typing import Literal

from pydantic import computed_field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_env_file() -> Path | None:
    """Find .env file in current or parent directories."""
    current = Path.cwd()
    for path in [current, current.parent]:
        env_file = path / ".env"
        if env_file.exists():
            return env_file
    return None


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=find_env_file(),
        env_ignore_empty=True,
        extra="ignore",
    )

    # === Project ===
    PROJECT_NAME: str = "ai_agent"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "local", "staging", "production"] = "local"
    TIMEZONE: str = "UTC"  # IANA timezone (e.g. "UTC", "Europe/Warsaw", "America/New_York")
    MODELS_CACHE_DIR: Path = Path("./models_cache")
    MEDIA_DIR: Path = Path("./media")
    MAX_UPLOAD_SIZE_MB: int = 50  # Max file upload size in MB

    # === Shared Storage (EFS) ===
    EFS_MOUNT_DIR: Path = Path("/mnt/efs/shared")
    EFS_MAX_UPLOAD_SIZE_MB: int = 100

    # === Logfire ===
    LOGFIRE_TOKEN: str | None = None
    LOGFIRE_SERVICE_NAME: str = "ai_agent"
    LOGFIRE_ENVIRONMENT: str = "development"

    # === Database (PostgreSQL async) ===
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "ai_agent"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        """Build async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Build sync PostgreSQL connection URL (for Alembic)."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Pool configuration
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # === Auth (SECRET_KEY for JWT/Session/Admin) ===
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info: ValidationInfo) -> str:
        """Validate SECRET_KEY is secure in production."""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        # Get environment from values if available
        env = info.data.get("ENVIRONMENT", "local") if info.data else "local"
        if v == "change-me-in-production-use-openssl-rand-hex-32" and env == "production":
            raise ValueError(
                "SECRET_KEY must be changed in production! "
                "Generate a secure key with: openssl rand -hex 32"
            )
        return v

    # === JWT Settings ===
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    # === Auth (API Key) ===
    API_KEY: str = "change-me-in-production"
    API_KEY_HEADER: str = "X-API-Key"

    @field_validator("API_KEY")
    @classmethod
    def validate_api_key(cls, v: str, info: ValidationInfo) -> str:
        """Validate API_KEY is set in production."""
        env = info.data.get("ENVIRONMENT", "local") if info.data else "local"
        if v == "change-me-in-production" and env == "production":
            raise ValueError(
                "API_KEY must be changed in production! "
                "Generate a secure key with: openssl rand -hex 32"
            )
        return v

    # === Redis ===
    REDIS_ENABLED: bool = True
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0
    REDIS_SSL: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URL(self) -> str:
        """Build Redis connection URL. Uses rediss:// when REDIS_SSL is True."""
        scheme = "rediss" if self.REDIS_SSL else "redis"
        if self.REDIS_PASSWORD:
            return f"{scheme}://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"{scheme}://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # === Rate Limiting ===
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds

    # === Sentry ===
    SENTRY_DSN: str | None = None

    # === Prometheus ===
    PROMETHEUS_METRICS_PATH: str = "/metrics"
    PROMETHEUS_INCLUDE_IN_SCHEMA: bool = False

    # === CloudWatch Custom Metrics ===
    CLOUDWATCH_METRICS_ENABLED: bool = False
    CLOUDWATCH_METRICS_NAMESPACE: str = "webapp-group10/backend"
    CLOUDWATCH_METRICS_SERVICE_NAME: str = "backend"
    CLOUDWATCH_METRICS_INTERVAL_SECONDS: int = 60

    # === File Storage (S3/MinIO) ===
    S3_ENDPOINT: str | None = None
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "ai_agent"
    S3_REGION: str = "us-east-1"

    # === Media File Storage (S3) ===
    S3_MEDIA_BUCKET: str = ""
    S3_MEDIA_REGION: str = "us-east-1"
    S3_MEDIA_PREFIX: str = "media"

    # === AWS Bedrock ===
    AWS_REGION: str = "us-east-1"
    BEDROCK_KNOWLEDGE_BASE_ID: str = ""
    BEDROCK_KB_DATA_SOURCE_ID: str = ""
    BEDROCK_KB_S3_BUCKET: str = ""
    BEDROCK_KB_S3_PREFIX: str = "rag-documents/"

    # === AI Agent (pydantic_ai) ===
    AI_MODEL: str = "us.anthropic.claude-sonnet-4-20250514"
    AI_TEMPERATURE: float = 0.7
    AI_AVAILABLE_MODELS: list[str] = [
        "us.anthropic.claude-sonnet-4-20250514",
        "us.anthropic.claude-haiku-4-20250414",
        "us.meta.llama3-3-70b-instruct-v1:0",
        "us.meta.llama4-maverick-17b-instruct-v1:0",
        "us.amazon.nova-pro-v1:0",
        "us.amazon.nova-lite-v1:0",
    ]
    AI_FRAMEWORK: str = "pydantic_ai"
    LLM_PROVIDER: str = "bedrock"

    # === RAG (Retrieval Augmented Generation) ===
    # Retrieval
    RAG_DEFAULT_COLLECTION: str = "documents"
    RAG_TOP_K: int = 10

    # Document Parser
    # PDF Parser runtime selection
    PDF_PARSER: str = "pymupdf"  # For RAG ingestion: pymupdf, llamaparse, liteparse
    CHAT_PDF_PARSER: str = "pymupdf"  # For chat file attachments: pymupdf, llamaparse, liteparse
    LLAMAPARSE_API_KEY: str = ""
    LLAMAPARSE_TIER: str = "agentic"  # fast, cost_effective, agentic, agentic_plus
    # Image Description (LLM vision)
    RAG_ENABLE_IMAGE_DESCRIPTION: bool = True  # set to false to disable LLM image description
    RAG_IMAGE_DESCRIPTION_MODEL: str = ""  # empty = use AI_MODEL

    # Google Drive (optional, for document ingestion via service account)
    GOOGLE_DRIVE_CREDENTIALS_FILE: str = "credentials/google-drive-sa.json"

    # S3 (optional, for document ingestion from S3/MinIO)
    S3_RAG_ENDPOINT: str | None = None
    S3_RAG_ACCESS_KEY: str = ""
    S3_RAG_SECRET_KEY: str = ""
    S3_RAG_BUCKET: str = "ai_agent-rag"
    S3_RAG_REGION: str = "us-east-1"

    # === Cookie Settings ===
    COOKIE_DOMAIN: str | None = None
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"
    COOKIE_HTTPONLY: bool = True
    COOKIE_PATH: str = "/"
    ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"

    # === CORS ===
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: list[str], info: ValidationInfo) -> list[str]:
        """Warn if CORS_ORIGINS is too permissive in production."""
        env = info.data.get("ENVIRONMENT", "local") if info.data else "local"
        if "*" in v and env == "production":
            raise ValueError(
                "CORS_ORIGINS cannot contain '*' in production! Specify explicit allowed origins."
            )
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rag(self) -> "RAGSettings":
        """Build RAG-specific settings."""
        from app.rag.config import RAGSettings, DocumentParser, PdfParser

        pdf_parser = PdfParser(
            method=self.PDF_PARSER,
            api_key=self.LLAMAPARSE_API_KEY,
            tier=self.LLAMAPARSE_TIER,
        )

        return RAGSettings(
            collection_name=self.RAG_DEFAULT_COLLECTION,
            knowledge_base_id=self.BEDROCK_KNOWLEDGE_BASE_ID,
            data_source_id=self.BEDROCK_KB_DATA_SOURCE_ID,
            kb_s3_bucket=self.BEDROCK_KB_S3_BUCKET,
            kb_s3_prefix=self.BEDROCK_KB_S3_PREFIX,
            top_k=self.RAG_TOP_K,
            document_parser=DocumentParser(),
            pdf_parser=pdf_parser,
            enable_image_description=self.RAG_ENABLE_IMAGE_DESCRIPTION,
            image_description_model=self.RAG_IMAGE_DESCRIPTION_MODEL,
        )


# Rebuild Settings to resolve RAGSettings forward reference
from app.rag.config import RAGSettings

Settings.model_rebuild()


settings = Settings()

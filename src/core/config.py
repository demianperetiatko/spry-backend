from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = Field(default="Spry Backend v2", description="Application name")
    APP_VERSION: str = Field(default="2.0.0", description="Application version")
    APP_ENV: str = Field(default="dev", description="Application environment")

    DEBUG: bool = Field(default=False, description="Debug mode")

    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://spry:spry_pwd@db:5432/spry_v2",
        description="Database connection URL",
    )

    SECRET_KEY: str = Field(
        default="",
        description="Secret key for session middleware",
    )

    CORS_ORIGINS: str | list[str] = Field(
        default="http://localhost:3000,https://app.spryplan.com",
        description="Allowed CORS origins (comma-separated string or list)",
    )

    MAILJET_API_KEY: str = Field(
        default="",
        description="Mailjet API key",
    )
    MAILJET_SECRET_KEY: str = Field(
        default="",
        description="Mailjet secret key",
    )

    DEMO_GOOGLE_ACCOUNT_SERVICE_FOLDER: str = Field(
        default="demo_google_account_service_key",
        description="Demo Google account service folder path",
    )

    GCP_SERVICE_KEY_PATH: str = Field(
        default="gcp_service_account.json",
        description="GCP service account key file path",
    )
    GCP_BUCKET_NAME: str = Field(
        default="app-spryplan-bucket",
        description="GCP bucket name",
    )
    GCP_DEFAULT_UPLOAD_PREFIX: str = Field(
        default="image/profile/",
        description="GCP default upload prefix",
    )

    GOOGLE_CLIENT_ID: str = Field(
        default="",
        description="Google OAuth client ID",
    )
    GOOGLE_CLIENT_SECRET: str = Field(
        default="",
        description="Google OAuth client secret",
    )
    GOOGLE_AUTHORIZATION_ENDPOINT: str = Field(
        default="https://accounts.google.com/o/oauth2/v2/auth",
        description="Google OAuth authorization endpoint",
    )
    GOOGLE_TOKEN_ENDPOINT: str = Field(
        default="https://oauth2.googleapis.com/token",
        description="Google OAuth token endpoint",
    )
    GOOGLE_USERINFO_ENDPOINT: str = Field(
        default="https://openidconnect.googleapis.com/v1/userinfo",
        description="Google OAuth userinfo endpoint",
    )
    GOOGLE_REDIRECT_URI: str = Field(
        default="http://localhost:8000/auth/callback/google/",
        description="Google OAuth redirect URI for development",
    )
    GOOGLE_SCOPE: list[str] = Field(
        default=[
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",
        ],
        description="Google OAuth scopes",
    )

    FRONTEND_DOMAIN: str = Field(
        default="http://localhost:3000",
        description="Frontend domain for development",
    )
    BACKEND_DOMAIN: str = Field(
        default="http://localhost:8000",
        description="Backend domain for development",
    )
    ADMIN_API_KEY: str = Field(
        default="",
        description="Admin API key for organization creation",
    )
    INVITATION_API_PREFIX: str = Field(
        default="/invitations",
        description="Backend API prefix for invitation endpoints",
    )

    FRONTEND_INVITATION_ACCEPTED_REDIRECT: str = Field(
        default="/login",
        description="Frontend redirect path after invitation acceptance",
    )

    # Temporary compatibility flag: v1 frontend expects single-organization users.
    # Set to False to re-enable multi-organization membership when redesign is ready.
    SINGLE_ORG_POLICY_ENABLED: bool = Field(default=True, description="Enforce single org per user (temporary)")

    @property
    def cors_origins_list(self) -> list[str]:
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return self.CORS_ORIGINS

    @property
    def google_redirect_uri(self) -> str:
        return self.GOOGLE_REDIRECT_URI

    @property
    def frontend_domain(self) -> str:
        return self.FRONTEND_DOMAIN

    @property
    def backend_domain(self) -> str:
        return self.BACKEND_DOMAIN

    def get_invitation_link(self, token: str) -> str:
        return f"{self.backend_domain}{self.INVITATION_API_PREFIX}/{token}"

    def get_invitation_accepted_redirect_url(self) -> str:
        redirect_path = self.FRONTEND_INVITATION_ACCEPTED_REDIRECT
        if not redirect_path.startswith("/"):
            redirect_path = f"/{redirect_path}"
        return f"{self.frontend_domain}{redirect_path}"


settings = Settings()

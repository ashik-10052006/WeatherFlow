from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import urllib.parse


class Settings(BaseSettings):
    """Application and Database configuration loaded from environment variables or .env."""

    # Database Configuration
    db_server: str = Field(default=r".\SQLEXPRESS", validation_alias="DB_SERVER")
    db_database: str = Field(default="WeatherDataWarehouse", validation_alias="DB_DATABASE")
    db_driver: str = Field(default="ODBC Driver 17 for SQL Server", validation_alias="DB_DRIVER")
    db_trusted_connection: str = Field(default="yes", validation_alias="DB_TRUSTED_CONNECTION")
    db_user: Optional[str] = Field(default=None, validation_alias="DB_USER")
    db_password: Optional[str] = Field(default=None, validation_alias="DB_PASSWORD")

    # Weather API Configuration
    weather_api_base_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        validation_alias="WEATHER_API_BASE_URL",
    )
    weather_api_timeout_seconds: int = Field(default=10, validation_alias="WEATHER_API_TIMEOUT_SECONDS")

    # Application Configuration
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    app_host: str = Field(default="127.0.0.1", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Construct a SQLAlchemy-compatible connection URL for SQL Server using pyodbc."""
        if self.db_user and self.db_password:
            # SQL Authentication
            driver_str = urllib.parse.quote_plus(self.db_driver)
            user_str = urllib.parse.quote_plus(self.db_user)
            pwd_str = urllib.parse.quote_plus(self.db_password)
            return (
                f"mssql+pyodbc://{user_str}:{pwd_str}@{self.db_server}/{self.db_database}"
                f"?driver={driver_str}&TrustServerCertificate=yes"
            )
        else:
            # Windows Trusted Authentication
            params = urllib.parse.quote_plus(
                f"DRIVER={{{self.db_driver}}};"
                f"SERVER={self.db_server};"
                f"DATABASE={self.db_database};"
                f"Trusted_Connection={self.db_trusted_connection};"
                f"TrustServerCertificate=yes;"
            )
            return f"mssql+pyodbc:///?odbc_connect={params}"


settings = Settings()

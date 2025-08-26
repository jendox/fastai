from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ("settings",)


class DeepseekSettings(BaseSettings):
    api_key: SecretStr
    max_connections: int = Field(5, gt=0)
    timeout: int = 5


class UnsplashSettings(BaseSettings):
    api_key: SecretStr
    max_connections: int = Field(5, gt=0)
    timeout: int = 20


class S3Settings(BaseSettings):
    endpoint_url: str
    access_key: SecretStr
    secret_key: SecretStr
    bucket: str
    max_connections: int = Field(10, gt=0)
    connect_timeout: int = 50
    read_timeout: int = 30


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    debug: bool = False
    deepseek: DeepseekSettings
    unsplash: UnsplashSettings
    s3: S3Settings


settings = AppSettings()

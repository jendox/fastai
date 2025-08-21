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


settings = AppSettings()

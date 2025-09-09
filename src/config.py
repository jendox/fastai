import re
from contextvars import ContextVar
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.libs.gotenberg_client import GotenbergImageFormat

__all__ = (
    "AppSettings",
    "app_settings",
)

app_settings: ContextVar["AppSettings"] = ContextVar("app_settings")

BUCKET_REGEXP = r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$"
IP_REGEXP = r"^\d+\.\d+\.\d+\.\d+$"
S3_RESERVED_PREFIXES = ('xn--', 'sthree-', 'sthree-config')
VALID_PROTOCOLS = "http://", "https://"


def validate_url(value: str) -> str:
    if not value.startswith(VALID_PROTOCOLS):
        raise ValueError(f"URL должен начинаться с протокола ({', '.join(VALID_PROTOCOLS)}).")
    return value.rstrip("/")


def validate_bucket_name(value: str) -> str:
    if not re.match(BUCKET_REGEXP, value):
        raise ValueError(
            "Имя бакета может содержать только строчные буквы, цифры, точки и дефисы. "
            "Должно начинаться и заканчиваться буквой или цифрой.",
        )
    if re.match(IP_REGEXP, value):
        raise ValueError("Имя бакета не может быть IP-адресом.")
    if ".." in value or ".-" in value or "-." in value:
        raise ValueError("Имя бакета не может содержать последовательные точки и дефисы.")
    if value.startswith(S3_RESERVED_PREFIXES):
        raise ValueError("Имя бакета содержит зарезервированный префикс.")
    return value


HttpUrl = Annotated[str, AfterValidator(validate_url)]
BucketName = Annotated[
    str,
    Field(..., min_length=3, max_length=63),
    AfterValidator(validate_bucket_name),
]


class DeepseekSettings(BaseModel):
    api_key: SecretStr
    """API ключ для Deepseek"""
    max_connections: int = Field(5, gt=0)
    """Максимальное количество соединений"""
    timeout: float = 5
    """Таймаут запросов в секундах"""


class UnsplashSettings(BaseModel):
    api_key: SecretStr
    """API ключ для Unsplash"""
    max_connections: int = Field(5, gt=0)
    """Максимальное количество соединений"""
    timeout: float = 20
    """Таймаут запросов в секундах"""


class S3Settings(BaseModel):
    endpoint_url: HttpUrl
    """Адрес S3-совместимого хранилища
    Примеры:\n
    - Локальный MinIO: http://localhost:9000\n
    - AWS S3: https://s3.eu-west-1.amazonaws.com\n
    - Yandex Cloud: https://storage.yandexcloud.net\n
    - DigitalOcean: https://fra1.digitaloceanspaces.com
    """
    access_key: SecretStr
    """Access key ID для аутентификации в S3-совместимом хранилище"""
    secret_key: SecretStr
    """Secret access key для аутентификации в S3-совместимом хранилище"""
    bucket: BucketName
    """Имя S3 бакета
    Требования:\n
    - Длина 3-63 символа\n
    - Только строчные буквы, цифры, точки и дефисы\n
    - Должно начинаться и заканчиваться буквой или цифрой\n
    - Не может быть IP-адресом (например, 192.168.1.1)\n
    - Не может содержать последовательные точки или дефисы\n
    - Не может содержать зарезервированные префиксы (xn--, sthree- и др.)
    """
    max_connections: int = Field(10, gt=0)
    """Максимальное количество одновременных подключений к S3"""
    connect_timeout: float = 50
    """Таймаут подключения к S3 в секундах"""
    read_timeout: float = 30
    """Таймаут чтения данных из S3 в секундах"""


class GotenbergSettings(BaseModel):
    api_url: HttpUrl
    """URL API сервера Gotenberg
    Примеры:\n
    - Локальный сервер: http://127.0.0.1:3000\n
    - Демо-версия API Gotenberg: https://demo.gotenberg.dev
    """
    max_connections: int = Field(5, gt=0)
    """Максимальное количество одновременных подключений к Gotenberg API"""
    screenshot_width: int = Field(ge=375, le=1920)
    """Ширина скриншота в пикселях"""
    screenshot_format: GotenbergImageFormat
    """Формат изображения для скриншотов
    Поддерживаемые форматы: jpeg, png, webp
    """
    screenshot_timeout: float = 10
    """Таймаут генерации скриншотов в секундах"""
    screenshot_animation_delay: float = 8
    """Задержка перед скриншотом для анимаций в секундах
    Важно: время ожидания завершения анимаций должно быть меньше таймаута асинхронного клиента,
    иначе всегда будет TimeoutError.\n
    Рекомендуемая разница между временем ожидания и таймаутом составляет от 2 до 5 секунд.
    """


class AppSettings(BaseSettings):
    app_debug: bool = False
    page_generator_debug: bool = False
    deepseek: DeepseekSettings
    unsplash: UnsplashSettings
    s3: S3Settings
    gotenberg: GotenbergSettings

    @classmethod
    def load(cls) -> "AppSettings":
        try:
            settings = cls()
            print("✅ Настройки приложения успешно загружены")
            return settings
        except ValidationError as e:
            print("❌ Ошибка валидации настроек приложения:")
            for error in e.errors():
                field = " → ".join(str(loc) for loc in error["loc"])
                print(f"   {field}: {error['msg']}")
            raise
        except Exception as e:
            print(f"❌ Критическая ошибка загрузки настроек приложения: {e}")
            raise

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        json_schema_extra={
            "examples": [{
                "app_debug": False,
                "deepseek": {
                    "api_key": "sk-...",
                    "max_connections": 5,
                    "timeout": 5,
                },
                "unsplash": {
                    "api_key": "abc123...",
                    "max_connections": 5,
                    "timeout": 20,
                },
                "s3": {
                    "endpoint_url": "http://localhost:9000",
                    "access_key": "myaccesskey",
                    "secret_key": "mysecretkey",
                    "bucket": "my-bucket",
                    "max_connections": 10,
                    "connect_timeout": 50,
                    "read_timeout": 30,
                },
            }],
        },
    )

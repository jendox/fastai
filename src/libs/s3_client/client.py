from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import ClassVar

import aioboto3
from aiobotocore.config import AioConfig
from pydantic import SecretStr
from types_aiobotocore_s3.client import S3Client

from .exceptions import AsyncS3ClientError, UploadError
from .schemas import S3UploadParams

__all__ = (
    "AsyncS3Client",
)


def extract_secret(value: str | SecretStr) -> str:
    return value.get_secret_value() if isinstance(value, SecretStr) else value


class AsyncS3Client:
    """Асинхронный клиент для взаимодействия с S3-совместимым объектным хранилищем.

    Использует глобальный singleton-инстанс, который инициализируется методом `setup`
    и доступен через `get_client`. Клиент не должен создаваться напрямую.
    """
    _client: ClassVar[S3Client | None] = None

    def __init__(self):
        """Запрещает прямое создание экземпляров класса.

        Raises:
            AsyncS3ClientError: При попытке создать экземпляр напрямую.
        """
        raise AsyncS3ClientError(
            "AsyncS3Client не должен создаваться напрямую. "
            "Используйте методы класса для работы с клиентом.",
        )

    @classmethod
    @asynccontextmanager
    async def setup(
        cls,
        endpoint_url: str,
        access_key: str | SecretStr,
        secret_key: str | SecretStr,
        max_pool_connections: int,
        connect_timeout: int,
        read_timeout: int,
    ) -> AsyncGenerator[S3Client]:
        """Инициализирует глобальный S3 клиент для использования в lifespan приложения.

        Args:
            endpoint_url: URL S3-совместимого хранилища.
            access_key: Ключ доступа (access key) для аутентификации.
            secret_key: Секретный ключ (secret key) для аутентификации.
            max_pool_connections: Максимальное количество соединений в пуле.
            connect_timeout: Таймаут подключения в секундах.
            read_timeout: Таймаут чтения в секундах.

        Yields:
            S3Client: Инициализированный асинхронный S3 клиент.

        Raises:
            AsyncS3ClientError: При ошибках инициализации клиента.
        """
        ak = extract_secret(access_key)
        sk = extract_secret(secret_key)
        session = aioboto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk)
        config = AioConfig(
            max_pool_connections=max_pool_connections,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
        try:
            async with session.client("s3", config=config, endpoint_url=endpoint_url) as client:
                cls._client = client
                yield client
        finally:
            await cls._client.close()

    @classmethod
    def get_client(cls) -> S3Client:
        """Возвращает инициализированный глобальный S3 клиент.

        Returns:
            S3Client: Инициализированный асинхронный S3 клиент.

        Raises:
            AsyncS3ClientError: Если клиент не был инициализирован через `setup`.
        """
        if client := cls._client:
            return client
        raise AsyncS3ClientError(
            "Клиент AsyncS3Client не был проинициализирован. "
            "Воспользуйтесь методом setup() для инициализации клиента.",
        )

    @classmethod
    async def upload(cls, upload_params: S3UploadParams):
        """Загружает объект в S3-совместимое хранилище.

        Args:
            upload_params: Параметры загрузки, содержащие данные объекта,
                            имя бакета, ключ объекта и метаданные.

        Raises:
            UploadError: При ошибке загрузки объекта в S3.
            AsyncS3ClientError: Если клиент не инициализирован.

        Example:
            ```python
            upload_params = S3UploadParams(
                bucket="my-bucket",
                key="path/to/file.txt",
                body=b"file content",
                content_type="text/plain"
            )
            await AsyncS3Client.upload(upload_params)
            ```
        """
        client: S3Client = cls.get_client()
        try:
            await client.put_object(**upload_params.to_s3_kwargs())
        except Exception as e:
            raise UploadError(str(e)) from e

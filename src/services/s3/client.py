import os
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any, ClassVar, Optional, Self

import aioboto3
import aiofiles
from aiobotocore.config import AioConfig
from aiofiles.threadpool.binary import AsyncBufferedReader
from pydantic import SecretStr
from types_aiobotocore_s3.client import S3Client

from .exceptions import AsyncS3ClientError, UploadError
from .schemas import ContentDispositionType, S3UploadParams

AWS_SERVICE_NAME = "s3"
DEFAULT_ENCODING = "utf-8"

MAX_PARTS_COUNT = 10000  # Максимальное количество частей для multipart
MAX_OBJECT_SIZE = 5 * 1024 * 1024 * 1024 * 1024  # 5TB
MINIMUM_ALLOWED_OBJECT_SIZE = 5 * 1024 * 1024  # 5MB
MAX_CHUNK_SIZE = 100 * 1024 * 1024  # 100MB


@dataclass(frozen=True)
class _InitState:
    session: aioboto3.Session
    config: AioConfig
    endpoint_url: str


class AsyncS3Client:
    """Асинхронный клиент для работы с S3-совместимым хранилищем."""

    _state: ClassVar[Optional[_InitState]]

    _client_manager: AbstractAsyncContextManager[S3Client] | None = None
    _client: S3Client | None = None

    def __init__(self) -> None:
        """Инициализирует экземпляр клиента."""
        if self._state is None:
            raise AsyncS3ClientError(
                "Клиент AsyncS3Client не был проинициализирован. "
                "Воспользуйтесь методом setup() для инициализации клиента.",
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
    ) -> AsyncGenerator[None, None]:
        """
        Инициализирует конфигурацию клиента S3 (lifespan FastAPI)

        Args:
            endpoint_url: URL endpoint S3-совместимого хранилища
            access_key: Логин для аутентификации
            secret_key: Пароль для аутентификации
            max_pool_connections: Максимальное количество соединений в пуле
            connect_timeout: Таймаут подключения в секундах
            read_timeout: Таймаут чтения в секундах

        Yields:
            None: Контекстный менеджер для управления жизненным циклом клиента
        """
        try:
            ak = cls._extract_secret(access_key)
            sk = cls._extract_secret(secret_key)
            session = cls._build_session(ak, sk)
            config = cls._build_config(
                max_pool_connections=max_pool_connections,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
            )
            cls._set_state(endpoint_url=endpoint_url, session=session, config=config)
            yield
        finally:
            cls._reset_state()

    async def __aenter__(self) -> Self:
        """Вход в асинхронный контекстный менеджер."""
        self._client_manager = self._state.session.client(
            service_name=AWS_SERVICE_NAME,
            config=self._state.config,
            endpoint_url=self._state.endpoint_url,
        )
        self._client = await self._client_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Выход из асинхронного контекстного менеджера."""
        if self._client_manager:
            await self._client_manager.__aexit__(exc_type, exc_val, exc_tb)
            self._client_manager = None
            self._client = None

    @classmethod
    @asynccontextmanager
    async def get_client(cls) -> AsyncGenerator["AsyncS3Client", None]:
        """
        Предоставляет инициализированный экземпляр клиента S3.

        Удобный контекстный менеджер для использования в коде. Автоматически
        управляет созданием и закрытием клиента.

        Yields:
            AsyncS3Client: Инициализированный экземпляр клиента

        Raises:
            AsyncS3ClientError: Если клиент не был инициализирован через setup()
        """
        async with cls() as client:
            yield client

    # ──────────────────────────────────────────────────────────────────────
    # Публичные операции
    # ──────────────────────────────────────────────────────────────────────

    async def upload_file(
        self,
        bucket: str,
        key: str,
        filepath: str,
        content_type: str,
        content_disposition: ContentDispositionType = "inline",
        metadata: dict | None = None,
    ) -> bool:
        """
        Загружает файл в S3 bucket с автоматическим выбором стратегии.

        Автоматически определяет оптимальный способ загрузки (singlepart/multipart)
        based on размера файла. Для файлов меньше 5MB использует singlepart upload,
        для больших файлов - multipart upload.

        Args:
            bucket: Название S3 bucket
            key: Ключ (путь) объекта в bucket
            filepath: Локальный путь к файлу
            content_type: MIME-тип содержимого
            content_disposition: Директива Content-Disposition ('inline' или 'attachment')
            metadata: Метаданные объекта в виде словаря

        Returns:
            bool: True если загрузка успешна

        Raises:
            UploadError: Если произошла ошибка при загрузке
        """
        try:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Файл {filepath} не найден")

            upload_params = S3UploadParams(
                bucket=bucket,
                key=key,
                body=None,
                content_type=content_type,
                content_disposition=content_disposition,
                metadata=metadata,
            )
            return await self._upload_stream(filepath, upload_params)

        except Exception as e:
            raise UploadError(f"Ошибка загрузки файла: {str(e)}") from e

    # ──────────────────────────────────────────────────────────────────────
    # Внутренняя логика загрузок
    # ──────────────────────────────────────────────────────────────────────

    async def _upload_stream(
        self,
        filepath: str,
        upload_params: S3UploadParams,
        chunk_size: int = MINIMUM_ALLOWED_OBJECT_SIZE,
    ):
        chunk_size = self._validate_chunk_size(chunk_size)
        file_size = self._validate_file_size(filepath, chunk_size)
        async with aiofiles.open(filepath, "rb") as file_stream:
            if file_size < MINIMUM_ALLOWED_OBJECT_SIZE:
                return await self._upload_small_file(file_stream, upload_params)
            return await self._upload_large_file(file_stream, upload_params, chunk_size)

    @staticmethod
    def _validate_chunk_size(chunk_size: int) -> int:
        chunk_size = max(chunk_size, MINIMUM_ALLOWED_OBJECT_SIZE)
        return min(chunk_size, MAX_CHUNK_SIZE)

    @staticmethod
    def _validate_file_size(filepath: str, chunk_size: int) -> int:
        file_size = os.path.getsize(filepath)
        if file_size > MAX_OBJECT_SIZE:
            raise ValueError(f"Размер файла превышает допустимый размер в {MAX_OBJECT_SIZE} байт")
        estimated_parts = (file_size + chunk_size - 1) // chunk_size
        if estimated_parts > MAX_PARTS_COUNT:
            raise ValueError(f"Требуется {estimated_parts} частей, что превышает максимум в {MAX_PARTS_COUNT}")
        return file_size

    async def _upload_small_file(self, file_stream: AsyncBufferedReader, upload_params: S3UploadParams) -> bool:
        upload_params.body = await file_stream.read()
        upload_data = upload_params.model_dump(exclude_none=True)
        await self._client.put_object(**upload_data)
        return True

    async def _upload_large_file(
        self,
        file_stream: AsyncBufferedReader,
        upload_params: S3UploadParams,
        chunk_size: int,
    ) -> bool:
        upload_id = None
        try:
            upload_id = await self._init_upload(upload_params)
            parts = await self._upload_parts(file_stream, upload_params, upload_id, chunk_size)
            await self._complete_upload(upload_params, upload_id, parts)
            return True

        except Exception:
            if upload_id:
                await self._abort_upload(upload_params, upload_id)
            raise

    async def _init_upload(self, upload_params: S3UploadParams) -> str:
        upload_data = upload_params.model_dump(exclude_none=True)
        create_response = await self._client.create_multipart_upload(**upload_data)
        return create_response["UploadId"]

    async def _upload_parts(
        self,
        file_stream: AsyncBufferedReader,
        upload_params: S3UploadParams,
        upload_id: str,
        chunk_size: int,
    ) -> list[dict[str, Any]]:
        parts = []
        part_number = 1

        while chunk := await file_stream.read(chunk_size):
            upload_response = await self._client.upload_part(
                Bucket=upload_params.bucket,
                Key=upload_params.key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=chunk,
            )
            parts.append({
                "PartNumber": part_number,
                "ETag": upload_response["ETag"],
            })
            part_number += 1
        return parts

    async def _complete_upload(
        self,
        upload_params: S3UploadParams,
        upload_id: str,
        parts: list[dict[str, Any]],
    ) -> None:
        await self._client.complete_multipart_upload(
            Bucket=upload_params.bucket,
            Key=upload_params.key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

    async def _abort_upload(self, upload_params: S3UploadParams, upload_id: str) -> None:
        await self._client.abort_multipart_upload(
            Bucket=upload_params.bucket,
            Key=upload_params.key,
            UploadId=upload_id,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Приватные хелперы (внутри класса — стандартный подход)
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_secret(value: str | SecretStr) -> str:
        return value.get_secret_value() if isinstance(value, SecretStr) else value

    @staticmethod
    def _build_session(access_key: str, secret_key: str) -> aioboto3.Session:
        return aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    @staticmethod
    def _build_config(
        *,
        max_pool_connections: int,
        connect_timeout: int,
        read_timeout: int,
    ) -> AioConfig:
        return AioConfig(
            max_pool_connections=max_pool_connections,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )

    @classmethod
    def _set_state(cls, *, endpoint_url: str, session: aioboto3.Session, config: AioConfig):
        cls._state = _InitState(endpoint_url=endpoint_url, session=session, config=config)

    @classmethod
    def _reset_state(cls) -> None:
        cls._state = None

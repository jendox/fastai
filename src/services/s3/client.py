"""Асинхронный клиент для работы с S3-совместимыми хранилищами.

Модуль предоставляет:
    Глобальную инициализацию конфигурации через `AsyncS3Client.setup(...)`.
    Экземплярный контекст (`async with AsyncS3Client()`) для открытия/закрытия
    низкоуровневого клиента `S3Client` из aioboto3.
    Конвейерную загрузку больших файлов (multipart upload) с управлением
размером частей и уровнем параллельности.

Потокобезопасность:
    Все операции с состоянием (`_state`, `_active_clients`, `_teardown_pending`)
    синхронизированы с помощью `anyio.Lock`.
    Объект `_InitState` является неизменяемым (frozen=True); ссылка может быть
    сброшена при teardown, но содержимое не мутируется.

Особенности дизайна:
    В `__aenter__` создаётся «снимок» состояния под локом, чтобы чтение session/config/endpoint
    было атомарным и устойчивым к изменениям в будущем.
    Счётчик `_active_clients` инкрементируется до создания клиента и откатывается при ошибке.
    Флаг `teardown_pending` гарантирует корректное завершение: состояние сбрасывается
    только после закрытия последнего активного клиента.

Загрузка:
    Малые данные отправляются через `put_object`.
    Крупные данные обрабатываются через multipart upload: продюсер режет поток
    на части фиксированного размера, несколько воркеров отправляют части параллельно,
    затем выполняется `complete_multipart_upload`.
    В пайплайне реализованы повторные попытки (`UPLOAD_RETRY_ATTEMPTS`) для каждого `upload_part`
    с экспоненциальной паузой.
"""
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, ClassVar, Optional, Self, TypeVar, overload

import aioboto3
import anyio
from aiobotocore.config import AioConfig
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from anyio.to_thread import run_sync
from pydantic import SecretStr
from types_aiobotocore_s3.client import S3Client
from types_aiobotocore_s3.type_defs import (
    AbortMultipartUploadOutputTypeDef,
    CompletedPartTypeDef,
    CompleteMultipartUploadOutputTypeDef,
    PutObjectOutputTypeDef,
    UploadPartOutputTypeDef,
)

from .exceptions import AsyncS3ClientError, UploadError
from .schemas import S3UploadParams

__all__ = (
    "AsyncS3Client",
)

# Максимальное количество повторов для внутреннего retry-механизма botocore.
MAX_RETRY_ATTEMPTS = 10

# Количество попыток повтора при загрузке отдельной части multipart (наш уровень).
UPLOAD_RETRY_ATTEMPTS = 4

# Жёсткое ограничение S3: максимум 10 000 частей в multipart upload.
MAX_PARTS_COUNT = 10000

# Жёсткое ограничение S3: максимальный размер объекта — 5 ТБ.
MAX_OBJECT_SIZE = 5 * 1024 * 1024 * 1024 * 1024

# Минимально допустимый размер части для multipart — 5 МБ.
MINIMUM_ALLOWED_OBJECT_SIZE = 5 * 1024 * 1024

# Практическое ограничение на размер части (100 МБ). Баланс между памятью и скоростью.
MAX_CHUNK_SIZE = 100 * 1024 * 1024

# Количество воркеров, отправляющих части параллельно.
UPLOAD_CONCURRENCY = 5

# Поддерживаемые in-memory данные: строки кодируются в UTF-8.
InMemoryPayload = str | bytes | bytearray | memoryview

# Сообщение в конвейере producer→consumer: (номер части, содержимое байтов).
ChunkMsg = tuple[int, bytes]

# Сигнатура продюсера для конвейера multipart.
TStream = TypeVar("TStream")
ProducerFunc = Callable[[TStream, int, MemoryObjectSendStream[ChunkMsg]], Awaitable[None]]


@dataclass(frozen=True)
class _InitState:
    """Неизменяемое состояние инициализации клиента.

    Содержит:
    Сессию aioboto3.
    Конфигурацию AioConfig.
    URL эндпоинта.

    Экземпляр не изменяется после создания.
    При teardown ссылка на объект может быть сброшена на None, но сам объект не мутируется.
    """
    session: aioboto3.Session
    config: AioConfig
    endpoint_url: str


class AsyncS3Client:
    """Асинхронный клиент для S3-совместимых хранилищ.

        Архитектура:
        Глобальная (class-level) инициализация через `setup(...)` с хранением
        конфигурации (_InitState) в `AsyncS3Client._state`.
        Экземплярный контекст (`async with AsyncS3Client()`) создаёт/закрывает
        низкоуровневый `S3Client` из aioboto3.
        Защита от гонок: все операции с состоянием/счётчиком (`_active_clients`)
        выполняются под `anyio.Lock()`.
        Механизм `teardown_pending`: если lifecyle-контекст `setup()` завершён,
        но ещё остаются активные клиенты, сброс `_state` откладывается до
        момента, когда `_active_clients` станет 0.

        Производительность:
        Мультичастичная загрузка с конвейером (producer/consumers),
        управляемая параметрами `chunk_size` и `concurrency`.
        Повторные попытки (`UPLOAD_RETRY_ATTEMPTS`) на уровне `upload_part`
        (экспоненциальная пауза между попытками).
        """
    _state: ClassVar[Optional[_InitState]] = None
    _state_lock = anyio.Lock()
    _active_clients: ClassVar[int] = 0
    _teardown_pending: ClassVar[bool] = False

    def __init__(self) -> None:
        if self._state is None:
            raise AsyncS3ClientError(
                "Клиент AsyncS3Client не был проинициализирован. "
                "Воспользуйтесь методом setup() для инициализации клиента.",
            )
        self._client_manager: AbstractAsyncContextManager[S3Client] | None = None
        self._client: S3Client | None = None

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
        """Глобальная инициализация клиента (lifespan уровня приложения).

        Инициализирует `_state` (endpoint/session/config) один раз на процесс.
        Повторные вызовы `setup()` во время активного состояния игнорируются
        (сохраняется первая конфигурация). При выходе из контекста помечает
        `teardown_pending=True` и пытается сбросить состояние; если ещё есть
        активные экземпляры (`_active_clients > 0`), фактический сброс произойдёт
        позже — при закрытии последнего клиента.

        Этот метод потокобезопасен: все операции со `_state` и служебными
        флагами выполняются под `_state_lock`.

        Args:
            endpoint_url: URL S3-эндпоинта.
            access_key: Ключ доступа (строка или `SecretStr`).
            secret_key: Секретный ключ (строка или `SecretStr`).
            max_pool_connections: Максимум соединений в пуле HTTP.
            connect_timeout: Таймаут установки соединения (сек).
            read_timeout: Таймаут чтения ответа (сек).

        Yields:
            Ничего: используется как контекст, в теле которого приложение работает
            с `AsyncS3Client.get_client()` и/или прямым созданием экземпляров.

        Raises:
            AsyncS3ClientError: при попытке работы с экземплярами без `setup()`.
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
            async with cls._state_lock:
                cls._set_state(endpoint_url=endpoint_url, session=session, config=config)
            yield
        finally:
            async with cls._state_lock:
                cls._teardown_pending = True
                cls._reset_state()

    async def __aenter__(self) -> Self:
        """Открывает низкоуровневый S3-клиент и увеличивает refcount.

        Нюансы:
        Под `_state_lock` выполняется «снимок» `_state` (session/config/endpoint),
        а также инкремент `_active_clients`. Это защищает от гонки с завершающимся
        `setup()` и гарантирует, что конфигурация не изменится между чтением и
        созданием клиента.
        Создание `aioboto3` клиента выполняется **вне** лока, чтобы не
        блокировать другие корутины. В случае ошибки инкремент refcount
        откатывается под локом; если при этом включён `teardown_pending` и
        счётчик стал 0 — вызывается финальный сброс `_state`.

        Returns:
            Self: текущий экземпляр с открытым `self._client`.
        """
        async with self._state_lock:
            state = self._state
            if state is None:
                raise AsyncS3ClientError("AsyncS3Client не инициализирован через setup()")
            type(self)._active_clients += 1
            endpoint_url = state.endpoint_url
            config = state.config
            session = state.session

        try:
            self._client_manager = session.client(
                service_name="s3",
                config=config,
                endpoint_url=endpoint_url,
            )
            self._client = await self._client_manager.__aenter__()
            return self
        except Exception:
            async with self._state_lock:
                type(self)._active_clients -= 1
                if not type(self)._active_clients and type(self)._teardown_pending:
                    type(self)._reset_state()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Закрывает низкоуровневый S3-клиент и уменьшает refcount.

        Нюансы:
        Закрытие клиентского контекста выполняется с защитой в `finally`,
        чтобы гарантировать освобождение ресурсов.
        Декремент `_active_clients` выполняется под `_state_lock`. Если после
        декремента счётчик равен 0 и ранее был выставлен `teardown_pending`,
        выполняется финальный сброс `_state` (гарантируя корректный teardown
        после выхода из `setup()`).

        Args:
            exc_type: Тип исключения, если контекст завершился с ошибкой.
            exc_val: Экземпляр исключения.
            exc_tb: Трассировка стека.
        """
        try:
            if self._client_manager:
                await self._client_manager.__aexit__(exc_type, exc_val, exc_tb)
        finally:
            self._client_manager = None
            self._client = None
            async with self._state_lock:
                type(self)._active_clients -= 1
                if not type(self)._active_clients and type(self)._teardown_pending:
                    type(self)._reset_state()

    @classmethod
    @asynccontextmanager
    async def get_client(cls) -> AsyncGenerator["AsyncS3Client", None]:
        """Удобный фабричный контекст для работы с клиентом.

        Обёртка над `AsyncS3Client()` + `__aenter__/__aexit__`. Рекомендуемый способ
        кратковременного использования клиента в прикладном коде.

        Пример:
            async with AsyncS3Client.get_client() as s3:
                await s3.upload(...)

        Yields:
            AsyncS3Client: Инициализированный экземпляр.

        Raises:
            AsyncS3ClientError: если `setup()` не был вызван ранее.
        """
        async with cls() as client:
            yield client

    # ======================================================================
    # Публичные операции
    # ======================================================================

    @overload
    async def upload(
        self,
        content: InMemoryPayload,
        upload_params: S3UploadParams,
    ) -> PutObjectOutputTypeDef | CompleteMultipartUploadOutputTypeDef:
        ...

    @overload
    async def upload(
        self,
        filepath: Path,
        upload_params: S3UploadParams,
        chunk_size: int = MINIMUM_ALLOWED_OBJECT_SIZE,
        concurrency: int = UPLOAD_CONCURRENCY,
    ) -> PutObjectOutputTypeDef | CompleteMultipartUploadOutputTypeDef:
        ...

    @overload
    async def upload(
        self,
        file_object: BinaryIO,
        upload_params: S3UploadParams,
        chunk_size: int = MINIMUM_ALLOWED_OBJECT_SIZE,
        concurrency: int = UPLOAD_CONCURRENCY,
    ) -> CompleteMultipartUploadOutputTypeDef:
        ...

    @overload
    async def upload(
        self,
        async_stream: AsyncIterator[bytes],
        upload_params: S3UploadParams,
        chunk_size: int = MINIMUM_ALLOWED_OBJECT_SIZE,
        concurrency: int = UPLOAD_CONCURRENCY,
    ) -> PutObjectOutputTypeDef | CompleteMultipartUploadOutputTypeDef:
        ...

    async def upload(
        self,
        content: InMemoryPayload | Path | BinaryIO | AsyncIterator[bytes],
        upload_params: S3UploadParams,
        chunk_size: int = MINIMUM_ALLOWED_OBJECT_SIZE,
        concurrency: int = UPLOAD_CONCURRENCY,
    ) -> PutObjectOutputTypeDef | CompleteMultipartUploadOutputTypeDef:
        """Загружает объект в S3 (in-memory, файл, файловый объект или async-поток).

        Роутинг режимов:
        **Малый объект** (`len(data) <= chunk_size`) → `put_object`.
        **Файл/поток больше `chunk_size`** → multipart upload:
        данные режутся на части `chunk_size`, параллельно отправляются
        `concurrency` воркерами, затем выполняется `complete_multipart_upload`.

        Особенности:
        `chunk_size` нормализуется в пределах
        [`MINIMUM_ALLOWED_OBJECT_SIZE`, `MAX_CHUNK_SIZE`].
        В multipart-конвейере реализованы повторные попытки для `upload_part`
        (`UPLOAD_RETRY_ATTEMPTS`) с экспоненциальной паузой.
        Последняя часть multipart может быть меньше 5 МБ — это валидно по S3.
        Для `BinaryIO` чтение выполняется через `anyio.to_thread.run_sync`
        (без блокировки event loop).
        Для `AsyncIterator[bytes]` данные адаптируются продюсером к размеру
        `chunk_size`.

        Память/потоки:
        In-memory строка/байты не копируются сверх необходимого (используется
        `memoryview`), однако для `put_object` тело будет упаковано в `bytes`.
        Конвейер использует `anyio.create_task_group` и memory-каналы;
        буфер `max_buffer_size=concurrency*2` ограничивает давление на память.

        Args:
            content: Данные для загрузки (строка/байты/путь/файловый объект/async-итератор).
            upload_params: Параметры загрузки (bucket, key, ACL, ContentType и т.д.).
            chunk_size: Целевой размер части для multipart и/или порога между режимами.
            concurrency: Количество параллельных воркеров отправки частей.

        Returns:
            PutObjectOutputTypeDef | CompleteMultipartUploadOutputTypeDef:
            Ответ S3 для соответствующего режима.

        Raises:
            UploadError: Если загрузка завершилась неуспешно (обёртка над исходной ошибкой).
            ValueError: Если формат `content` не поддерживается или нарушены ограничения.
        """
        chunk_size = self._validate_chunk_size(chunk_size)
        if isinstance(content, Path):
            return await self._upload_file(Path(content), upload_params, chunk_size, concurrency)

        if isinstance(content, (str, bytes, bytearray, memoryview)):
            return await self._upload_in_memory(content, upload_params, chunk_size, concurrency)

        if hasattr(content, "read") and hasattr(content, "seek"):
            return await self._upload_file_object(content, upload_params, chunk_size, concurrency)

        if hasattr(content, "__aiter__"):
            return await self._upload_async_stream(content, upload_params, chunk_size, concurrency)

        raise ValueError(f"Неподдерживаемый формат данных: {type(content)}")

    # ======================================================================
    # Внутренняя логика загрузок
    # ======================================================================

    async def _upload_in_memory(
        self,
        content: InMemoryPayload,
        upload_params: S3UploadParams,
        chunk_size: int,
        concurrency: int,
    ) -> PutObjectOutputTypeDef | CompleteMultipartUploadOutputTypeDef:
        if isinstance(content, str):
            buffer = content.encode("utf-8")
            mv = memoryview(buffer)
        elif isinstance(content, (bytes, bytearray)):
            mv = memoryview(content)
        else:
            mv = content

        if len(mv) <= chunk_size:
            upload_params.body = bytes(mv)
            return await self._upload_small_data(upload_params)

        async def _aiter():
            for i in range(0, len(mv), chunk_size):
                yield bytes(mv[i:i + chunk_size])

        return await self._upload_async_stream(_aiter(), upload_params, chunk_size, concurrency)

    async def _upload_file(
        self,
        filepath: Path,
        upload_params: S3UploadParams,
        chunk_size: int,
        concurrency: int,
    ) -> CompleteMultipartUploadOutputTypeDef | PutObjectOutputTypeDef:
        try:
            if not await anyio.Path(filepath).is_file():
                raise FileNotFoundError(f"Файл {filepath} не найден")
            file_size = await self._validate_file_size(filepath, chunk_size)

            async with await anyio.open_file(filepath, "rb") as file_stream:
                if file_size <= chunk_size:
                    upload_params.body = await file_stream.read()
                    return await self._upload_small_data(upload_params)
                return await self._upload_large_file(file_stream, upload_params, chunk_size, concurrency)

        except anyio.get_cancelled_exc_class():
            raise
        except Exception as e:
            raise UploadError(f"Ошибка загрузки файла {filepath}: {str(e)}") from e

    async def _upload_file_object(
        self,
        file_object: BinaryIO,
        upload_params: S3UploadParams,
        chunk_size: int,
        concurrency: int,
    ) -> CompleteMultipartUploadOutputTypeDef:
        async def _aiter():
            while chunk := await run_sync(file_object.read, chunk_size):
                yield chunk

        return await self._upload_async_stream(_aiter(), upload_params, chunk_size, concurrency)

    async def _upload_async_stream(
        self,
        async_stream: AsyncIterator[bytes],
        upload_params: S3UploadParams,
        chunk_size: int,
        concurrency: int,
    ) -> CompleteMultipartUploadOutputTypeDef:
        async with self._multipart_guard(upload_params, failed_msg="Upload async stream failed") as set_upload_id:
            upload_id = await self._init_multipart_upload(upload_params)
            set_upload_id(upload_id)
            completed_parts = await self._upload_parts_pipeline(
                async_stream, self._pipeline_async_stream_producer, upload_params, upload_id, chunk_size, concurrency,
            )
            return await self._complete_multipart_upload(upload_params, upload_id, completed_parts)

    async def _upload_small_data(
        self,
        upload_params: S3UploadParams,
    ) -> PutObjectOutputTypeDef:
        return await self._put_object_safe(upload_params)

    async def _upload_large_file(
        self,
        file_stream: anyio.AsyncFile,
        upload_params: S3UploadParams,
        chunk_size: int,
        concurrency: int,
    ) -> CompleteMultipartUploadOutputTypeDef:
        async with self._multipart_guard(upload_params, failed_msg="Upload large file failed") as set_upload_id:
            upload_id = await self._init_multipart_upload(upload_params)
            set_upload_id(upload_id)
            completed_parts = await self._upload_parts_pipeline(
                file_stream, self._pipeline_file_producer, upload_params, upload_id, chunk_size, concurrency,
            )
            return await self._complete_multipart_upload(upload_params, upload_id, completed_parts)

    async def _upload_parts_pipeline(
        self,
        stream: anyio.AsyncFile | AsyncIterator[bytes],
        producer: ProducerFunc,
        upload_params: S3UploadParams,
        upload_id: str,
        chunk_size: int,
        concurrency: int,
    ) -> list[CompletedPartTypeDef]:
        send_stream, receive_stream = anyio.create_memory_object_stream[ChunkMsg](
            max_buffer_size=concurrency * 2,
        )
        completed_parts: list[CompletedPartTypeDef] = []
        completed_lock = anyio.Lock()

        async with anyio.create_task_group() as tg:
            tg.start_soon(producer, stream, chunk_size, send_stream)
            for _ in range(concurrency):
                tg.start_soon(
                    self._pipeline_upload_worker, upload_params, upload_id, receive_stream, completed_parts,
                    completed_lock,
                )

        return sorted(completed_parts, key=lambda x: x["PartNumber"])

    @staticmethod
    async def _pipeline_file_producer(
        file_stream: anyio.AsyncFile,
        chunk_size: int,
        send_stream: MemoryObjectSendStream[ChunkMsg],
    ) -> None:
        try:
            part_number = 1
            while chunk := await file_stream.read(chunk_size):
                await send_stream.send((part_number, chunk))
                part_number += 1
        finally:
            await send_stream.aclose()

    @staticmethod
    async def _pipeline_async_stream_producer(
        async_stream: AsyncIterator[bytes],
        chunk_size: int,
        send_stream: MemoryObjectSendStream[ChunkMsg],
    ) -> None:
        buffer = bytearray()
        part_number = 1
        try:
            async for chunk in async_stream:
                buffer.extend(chunk)
                while len(buffer) >= chunk_size:
                    part = bytes(buffer[:chunk_size])
                    del buffer[:chunk_size]
                    await send_stream.send((part_number, part))
                    part_number += 1
            if buffer:
                await send_stream.send((part_number, bytes(buffer)))
        finally:
            await send_stream.aclose()

    async def _pipeline_upload_worker(
        self,
        upload_params: S3UploadParams,
        upload_id: str,
        receive_stream: MemoryObjectReceiveStream[ChunkMsg],
        completed_parts: list,
        completed_lock: anyio.Lock,
    ) -> None:
        async for part_number, chunk in receive_stream:
            part: UploadPartOutputTypeDef | None = None
            for attempt in range(1, UPLOAD_RETRY_ATTEMPTS + 1):
                try:
                    part = await self._client.upload_part(
                        Bucket=upload_params.bucket,
                        Key=upload_params.key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=chunk,
                    )
                    break
                except Exception:
                    if attempt == UPLOAD_RETRY_ATTEMPTS:
                        raise
                    await anyio.sleep(0.2 * (2 ** (attempt - 1)))

            async with completed_lock:
                completed_parts.append({"PartNumber": part_number, "ETag": part["ETag"]})

    async def _init_multipart_upload(self, upload_params: S3UploadParams) -> str:
        upload_data = upload_params.to_s3_kwargs()
        create_response = await self._client.create_multipart_upload(**upload_data)
        return create_response["UploadId"]

    async def _complete_multipart_upload(
        self,
        upload_params: S3UploadParams,
        upload_id: str,
        parts: list[CompletedPartTypeDef],
    ) -> CompleteMultipartUploadOutputTypeDef:
        return await self._client.complete_multipart_upload(
            Bucket=upload_params.bucket,
            Key=upload_params.key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

    async def _abort_multipart_upload(
        self,
        upload_params: S3UploadParams,
        upload_id: str,
    ) -> AbortMultipartUploadOutputTypeDef:
        return await self._client.abort_multipart_upload(
            Bucket=upload_params.bucket,
            Key=upload_params.key,
            UploadId=upload_id,
        )

    async def _abort_safely(
        self,
        upload_params: S3UploadParams,
        upload_id: str,
    ) -> AbortMultipartUploadOutputTypeDef | None:
        if upload_id is not None:
            with anyio.CancelScope(shield=True):
                try:
                    return await self._abort_multipart_upload(upload_params, upload_id)
                except Exception:
                    pass
        return None

    async def _put_object_safe(self, upload_params: S3UploadParams) -> PutObjectOutputTypeDef:
        try:
            return await self._client.put_object(**upload_params.to_s3_kwargs())
        except anyio.get_cancelled_exc_class():
            raise
        except Exception as e:
            raise UploadError(f"Ошибка загрузки файла: {str(e)}") from e

    @asynccontextmanager
    async def _multipart_guard(self, upload_params: S3UploadParams, *, failed_msg: str):
        upload_id: str | None = None

        def set_upload_id(value: str) -> None:
            nonlocal upload_id
            upload_id = value

        try:
            yield set_upload_id
        except anyio.get_cancelled_exc_class():
            await self._abort_safely(upload_params, upload_id)
            raise
        except Exception as e:
            await self._abort_safely(upload_params, upload_id)
            raise UploadError(f"{failed_msg}: {e}") from e

    @staticmethod
    def _validate_chunk_size(chunk_size: int) -> int:
        chunk_size = max(chunk_size, MINIMUM_ALLOWED_OBJECT_SIZE)
        return min(chunk_size, MAX_CHUNK_SIZE)

    @staticmethod
    async def _validate_file_size(filepath: Path | anyio.Path, chunk_size: int) -> int:
        file_stat = await anyio.Path(filepath).stat()
        file_size = file_stat.st_size
        if file_size > MAX_OBJECT_SIZE:
            raise ValueError(f"Размер файла превышает допустимый размер в {MAX_OBJECT_SIZE} байт")
        estimated_parts = (file_size + chunk_size - 1) // chunk_size
        if estimated_parts > MAX_PARTS_COUNT:
            raise ValueError(f"Требуется {estimated_parts} частей, что превышает максимум в {MAX_PARTS_COUNT}")
        return file_size

    # ======================================================================
    # Приватные хелперы
    # ======================================================================

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
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": MAX_RETRY_ATTEMPTS, "mode": "adaptive"},
        )

    @classmethod
    def _set_state(cls, *, endpoint_url: str, session: aioboto3.Session, config: AioConfig):
        if cls._state is None:
            cls._state = _InitState(endpoint_url=endpoint_url, session=session, config=config)

    @classmethod
    def _reset_state(cls) -> None:
        if not cls._active_clients:
            cls._state = None
            cls._teardown_pending = False

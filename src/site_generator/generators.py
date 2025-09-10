import os
from pathlib import Path

import aiofiles
import anyio
from html_page_generator import AsyncPageGenerator

from src.config import app_settings
from src.libs.gotenberg_client.client import AsyncGotenbergClient
from src.libs.s3_client import AsyncS3Client, S3UploadParams
from src.libs.s3_client.exceptions import UploadError

__all__ = (
    "stream_and_publish",
    "mock_stream_and_publish",
)

BASE_STORAGE_DIR = Path(os.getcwd())


async def stream_and_publish(user_prompt: str):
    """Асинхронно генерирует HTML-страницу и публикует результаты.

    Генерирует HTML-страницу на основе промпта пользователя, сохраняет её локально,
    создает скриншот с помощью Gotenberg и загружает оба файла в S3 хранилище.

    Args:
        user_prompt: Текст промпта пользователя для генерации страницы.

    Yields:
        str: Чанки сгенерированного HTML-кода в реальном времени.

    Raises:
        HTMLScreenshotError: При ошибке создания скриншота.
        UploadError: При ошибке загрузки файлов в S3.
    """
    debug = app_settings.get().page_generator_debug
    generator = AsyncPageGenerator(debug_mode=debug)

    with anyio.CancelScope(shield=True):
        async for chunk in generator(user_prompt):
            if debug:
                print(chunk, end="", flush=True)
            yield chunk

        raw_html = generator.html_page.html_code
        await _save_generated_html(raw_html)
        image = await AsyncGotenbergClient.create_screenshot_from_html(raw_html)
        await _save_image(image)
        await _upload_html_to_s3(raw_html)
        await _upload_image_to_s3(image)


async def mock_stream_and_publish(chunk_size: int = 1024):
    """Имитирует процесс генерации и публикации для тестирования.

    Читает HTML-файл из локального хранилища чанками, имитируя потоковую
    генерацию, затем создает скриншот и загружает файлы в S3.

    Args:
        chunk_size: Размер чанков для чтения файла (по умолчанию 1024 байта).

    Yields:
        str: Чанки HTML-кода из локального файла.

    Raises:
        HTMLScreenshotError: При ошибке создания скриншота.
        UploadError: При ошибке загрузки файлов в S3.
    """
    html_path = BASE_STORAGE_DIR.joinpath("media", "index.html")
    parts: list[str] = []
    with anyio.CancelScope(shield=True):
        async with aiofiles.open(html_path, encoding="utf-8") as file:
            while chunk := await file.read(chunk_size):
                print(chunk, end="", flush=True)
                yield chunk
                parts.append(chunk)
                await anyio.sleep(0.5)

        raw_html = "".join(parts)
        image = await AsyncGotenbergClient.create_screenshot_from_html(raw_html)
        await _save_image(image)
        await _upload_html_to_s3(raw_html)
        await _upload_image_to_s3(image)


async def _save_generated_html(raw_html: str):
    filepath = BASE_STORAGE_DIR.joinpath("media", "index.html")
    async with aiofiles.open(filepath, "w", encoding="utf-8") as file:
        await file.write(raw_html)


async def _save_image(image: bytes):
    filepath = BASE_STORAGE_DIR.joinpath("media", "index.png")
    async with aiofiles.open(filepath, "wb") as file:
        await file.write(image)


async def _upload_html_to_s3(raw_html: str, bucket_key: str = "index.html"):
    settings = app_settings.get().s3
    upload_params = S3UploadParams(
        bucket=settings.bucket,
        key=bucket_key,
        body=raw_html,
        content_type="text/html",
        content_disposition="inline",
        metadata=None,
    )
    return await _safe_upload(upload_params)


async def _upload_image_to_s3(image: bytes, bucket_key: str = "index.png"):
    settings = app_settings.get().s3
    upload_params = S3UploadParams(
        bucket=settings.bucket,
        key=bucket_key,
        body=image,
        content_type="image/png",
        content_disposition="inline",
        metadata=None,
    )
    return await _safe_upload(upload_params)


async def _safe_upload(upload_params: S3UploadParams):
    try:
        await AsyncS3Client.upload(upload_params)
    except UploadError as e:
        print(f"Не удалось загрузить файл в бакет s3: {str(e)}")

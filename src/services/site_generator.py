from pathlib import Path

import aiofiles
import anyio
from html_page_generator import AsyncPageGenerator

from src.config import app_settings
from src.services.gotenberg import AsyncGotenbergClient
from src.services.s3 import AsyncS3Client
from src.services.s3.schemas import S3UploadParams
from src.services.storage_manager import BASE_STORAGE_DIR, StorageManager

__all__ = (
    "SiteGenerator",
)


class SiteGenerator:
    @staticmethod
    async def mock_generate_from_prompt(chunk_size: int = 1024):
        html_path = BASE_STORAGE_DIR.joinpath("data", "index.html")
        content = ""
        async with aiofiles.open(html_path, encoding="utf-8") as file:
            with anyio.CancelScope(shield=True):
                while chunk := await file.read(chunk_size):
                    print(chunk, end="", flush=True)
                    content += chunk
                    yield chunk
                    await anyio.sleep(0.1)

                await SiteGenerator._save_generated_site(content)
                await SiteGenerator._upload_site(content)
                await SiteGenerator._upload_site_from_file(html_path)
                image = await SiteGenerator._create_screenshot(content)
                await SiteGenerator._save_screenshot(image)
                await SiteGenerator._upload_screenshot(image)

    @staticmethod
    async def generate_from_prompt(user_prompt: str):
        debug_mode = app_settings.get().page_generator_debug
        generator = AsyncPageGenerator(debug_mode=debug_mode)

        with anyio.CancelScope(shield=True):
            async for chunk in generator(user_prompt):
                if debug_mode:
                    print(chunk, end="", flush=True)
                yield chunk

            raw_html = generator.html_page.html_code
            await SiteGenerator._save_generated_site(raw_html)

            image = await SiteGenerator._create_screenshot(raw_html)
            await SiteGenerator._save_screenshot(image)

            await SiteGenerator._upload_site(raw_html)
            await SiteGenerator._upload_screenshot(image)

    @staticmethod
    async def _create_screenshot(raw_html: str) -> bytes:
        return await AsyncGotenbergClient.screenshot_from_html(raw_html)

    @staticmethod
    async def _upload_screenshot(image: bytes, bucket_key: str = "index.png"):
        settings = app_settings.get().s3
        upload_params = S3UploadParams(
            bucket=settings.bucket,
            key=bucket_key,
            body=None,
            content_type="image/png",
            content_disposition="inline",
            metadata=None,
        )
        async with AsyncS3Client.get_client() as client:
            await client.upload(image, upload_params)

    @staticmethod
    async def _save_screenshot(image: bytes, filename: str = "index.png") -> str:
        filepath = await StorageManager.save_generated_screenshot(image, filename)
        return filepath

    @staticmethod
    async def _save_generated_site(html_code: str, filename: str = "index.html") -> str:
        filepath = await StorageManager.save_generated_site(html_code, filename)
        return filepath

    @staticmethod
    async def _upload_site(raw_html: str, bucket_key: str = "index.html"):
        settings = app_settings.get().s3
        upload_params = S3UploadParams(
            bucket=settings.bucket,
            key=bucket_key,
            body=None,
            content_type="text/html",
            content_disposition="inline",
            metadata=None,
        )
        async with AsyncS3Client.get_client() as client:
            await client.upload(raw_html, upload_params)

    @staticmethod
    async def _upload_site_from_file(
        filepath: Path,
        bucket_key: str = "index.html",
        content_type: str = "text/html",
    ):
        settings = app_settings.get().s3
        upload_params = S3UploadParams(
            bucket=settings.bucket,
            key=bucket_key,
            body=None,
            content_type=content_type,
            content_disposition="inline",
            metadata=None,
        )
        async with AsyncS3Client.get_client() as client:
            await client.upload(filepath, upload_params)

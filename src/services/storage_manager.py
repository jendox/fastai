from pathlib import Path

import aiofiles

from src.config import app_settings
from src.services.s3 import AsyncS3Client

__all__ = (
    "BASE_STORAGE_DIR",
    "StorageManager",
)

BASE_STORAGE_DIR = Path(__file__).parent.parent.parent


class StorageManager:
    @staticmethod
    async def save_generated_site(content: str, filename: str = "index.html") -> str:
        filepath = BASE_STORAGE_DIR.joinpath("data", filename)
        async with aiofiles.open(filepath, "w", encoding="utf-8") as file:
            await file.write(content)
        return str(filepath)

    @staticmethod
    async def upload_file_to_s3(filepath: str, key: str, content_type: str):
        settings = app_settings.get()
        async with AsyncS3Client.get_client() as client:
            await client.upload_file(
                bucket=settings.s3.bucket,
                key=key,
                filepath=filepath,
                content_type=content_type,
            )

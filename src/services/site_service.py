import asyncio
from datetime import datetime
from pathlib import Path

import anyio
import openai
from html_page_generator import AsyncPageGenerator

from src.config import app_settings
from src.services.s3 import AsyncS3Client

__all__ = (
    "SiteService",
    "SiteNotFoundError",
)

BASE_DIR = Path(__file__).parent.parent.parent

site_mock_data = {
    "created_at": datetime.fromisoformat("2025-08-20T18:29:56+00:00"),
    "html_code_download_url": "http://127.0.0.1:9000/my-public-bucket/index.html?response-content-disposition=attachment",
    "html_code_url": "http://127.0.0.1:9000/my-public-bucket/index.html",
    "id": 1,
    "prompt": "Сайт любителей рыбалки",
    "screenshot_url": "http://127.0.0.1:9000/my-public-bucket/index.png",
    "title": "Рыболовные приключения",
    "updated_at": datetime.fromisoformat("2025-08-20T18:29:56+00:00"),
}


class SiteNotFoundError(Exception): ...


class SiteService:
    @staticmethod
    async def mock_generate_site(chunk_size: int = 1024):
        settings = app_settings.get()
        html_path = BASE_DIR.joinpath("data", "index.html")
        with open(html_path, encoding="utf-8") as file:
            with anyio.CancelScope(shield=True):
                while data := file.read(chunk_size):
                    print(data, end="", flush=True)
                    yield data
                    await asyncio.sleep(1)

                filepath = str(html_path)
                await SiteService._upload_file(filepath, settings.s3.bucket, "index.html", "text/html")
                filepath = filepath.replace("html", "png")
                await SiteService._upload_file(filepath, settings.s3.bucket, "index.png", "image/png")

    @staticmethod
    def _save_html_file(content: str, filename: str = "index.html") -> str:
        html_path = BASE_DIR.joinpath("data", filename)
        with open(html_path, "w", encoding="utf-8") as file:
            file.write(content)
        return str(html_path)

    @staticmethod
    async def _upload_file(filepath: str, bucket: str, key: str, content_type: str):
        async with AsyncS3Client.get_client() as client:
            await client.upload_file(
                bucket=bucket,
                key=key,
                filepath=filepath,
                content_type=content_type,
            )

    @staticmethod
    async def generate_html(user_prompt: str):
        settings = app_settings.get()
        try:
            generator = AsyncPageGenerator(debug_mode=True)
            with anyio.CancelScope(shield=True):
                async for chunk in generator(user_prompt):
                    print(chunk, end="", flush=True)
                    yield chunk

                filepath = SiteService._save_html_file(generator.html_page.html_code)
                await SiteService._upload_file(filepath, settings.s3.bucket, "index.html", "text/html")
                filepath = filepath.replace("html", "png")
                await SiteService._upload_file(filepath, settings.s3.bucket, "index.png", "image/png")

        except (openai.AuthenticationError, openai.APIStatusError):
            raise
        except Exception:
            raise

    @staticmethod
    def get_my_sites() -> dict:
        return {"sites": [site_mock_data]}

    @staticmethod
    def get_site(site_id: int) -> dict:
        if site_id == site_mock_data["id"]:
            return site_mock_data
        raise SiteNotFoundError(f"Site with ID {site_id} not found")

    @staticmethod
    def create_site() -> dict:
        return site_mock_data

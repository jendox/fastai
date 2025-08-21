import asyncio
from datetime import UTC, datetime
from pathlib import Path

import anyio
import openai
from html_page_generator import AsyncPageGenerator

from src.config import settings

__all__ = ("SiteService",)

BASE_DIR = Path(__file__).parent.parent.parent

site_mock_data = {
    "created_at": datetime.fromisoformat("2025-06-15T18:29:56+00:00"),
    "html_code_download_url": "https://dvmn.org/media/filer_public/d1/4b/d14bb4e8-d8b4-49cb-928d-fd04ecae46da/index.html?response-content-disposition=attachment",
    "html_code_url": "https://dvmn.org/media/filer_public/d1/4b/d14bb4e8-d8b4-49cb-928d-fd04ecae46da/index.html",
    "id": 1,
    "prompt": "Стегозавры величественные гиганты Юрского периода",
    "screenshot_url": "https://images.unsplash.com/photo-1729207512292-da69be60b05a",
    "title": "Стегозавры",
    "updated_at": datetime.fromisoformat("2025-06-15T18:29:56+00:00"),
}


class SiteService:
    @staticmethod
    async def generate_site_mock(chunk_size: int = 1024):
        html_path = BASE_DIR.joinpath("data", "index.html")
        with open(html_path, encoding="utf-8") as file:
            with anyio.CancelScope(shield=True):
                while data := file.read(chunk_size):
                    print(data, end="", flush=True)
                    yield data
                    await asyncio.sleep(1)

    @staticmethod
    def _save_html_file(content: str, filename: str = "index.html") -> None:
        html_path = BASE_DIR.joinpath("data", filename)
        with open(html_path, "w", encoding="utf-8") as file:
            file.write(content)

    @staticmethod
    def _update_site_mock_data(prompt: str, title: str, filename: str = "index.html") -> None:
        site_url = f"http://127.0.0.1:8000/data/{filename}"
        download_url = f"{site_url}?response-content-disposition=attachment"
        created_at = datetime.now(UTC)
        site_mock_data["prompt"] = prompt
        site_mock_data["title"] = title
        site_mock_data["html_code_url"] = site_url
        site_mock_data["html_code_download_url"] = download_url
        site_mock_data["created_at"] = site_mock_data["updated_at"] = created_at

    @staticmethod
    async def generate_html(user_prompt: str):
        try:
            generator = AsyncPageGenerator(debug_mode=settings.debug)
            with anyio.CancelScope(shield=True):
                async for chunk in generator(user_prompt):
                    print(chunk, end="", flush=True)
                    yield chunk

                SiteService._save_html_file(generator.html_page.html_code)
                SiteService._update_site_mock_data(user_prompt, generator.html_page.title)

        except (openai.AuthenticationError, openai.APIStatusError):
            raise
        except Exception:
            raise

    @staticmethod
    def get_my_sites() -> dict:
        return {"sites": [site_mock_data]}

    @staticmethod
    def get_site(site_id: int) -> dict | None:
        return site_mock_data if site_id == site_mock_data["id"] else None

    @staticmethod
    def create_site() -> dict:
        return site_mock_data

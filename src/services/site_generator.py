import aiofiles
import anyio
from html_page_generator import AsyncPageGenerator

from src.services.storage_manager import BASE_STORAGE_DIR, StorageManager

__all__ = (
    "SiteGenerator",
)


class SiteGenerator:
    @staticmethod
    async def mock_generate_from_prompt(chunk_size: int = 1024):
        html_path = BASE_STORAGE_DIR.joinpath("data", "index.html")
        async with aiofiles.open(html_path, encoding="utf-8") as file:
            with anyio.CancelScope(shield=True):
                while data := await file.read(chunk_size):
                    print(data, end="", flush=True)
                    yield data
                    await anyio.sleep(1)

                await SiteGenerator._upload_generated_site(str(html_path))

    @staticmethod
    async def generate_from_prompt(user_prompt: str):
        generator = AsyncPageGenerator(debug_mode=True)

        with anyio.CancelScope(shield=True):
            async for chunk in generator(user_prompt):
                print(chunk, end="", flush=True)
                yield chunk

            filepath = await SiteGenerator._save_generated_site(generator.html_page.html_code)
            await SiteGenerator._upload_generated_site(filepath)

    @staticmethod
    async def _save_generated_site(html_code: str) -> str:
        filepath = await StorageManager.save_generated_site(html_code)
        return filepath

    @staticmethod
    async def _upload_generated_site(filepath: str):
        await StorageManager.upload_file_to_s3(filepath, "index.html", "text/html")
        filepath = filepath.replace(".html", ".png")
        await StorageManager.upload_file_to_s3(filepath, "index.png", "image/png")

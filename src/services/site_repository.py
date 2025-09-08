from datetime import datetime

__all__ = (
    "SiteNotFoundError",
    "SiteRepository",
)

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


class SiteRepository:
    @staticmethod
    def get_by_id(site_id: int):
        if site_id == site_mock_data["id"]:
            return site_mock_data
        raise SiteNotFoundError(f"Site with ID {site_id} not found")

    @staticmethod
    def get_user_sites() -> list:
        return [site_mock_data]

    @staticmethod
    def create() -> dict:
        return site_mock_data

from datetime import datetime

__all__ = (
    "SiteNotFoundError",
    "SiteRepository",
)

from typing import Any

mock_site_data = {
    "created_at": datetime.fromisoformat("2025-08-20T18:29:56+00:00"),
    "html_code_download_url": "http://127.0.0.1:9000/my-public-bucket/index.html?response-content-disposition=attachment",
    "html_code_url": "http://127.0.0.1:9000/my-public-bucket/index.html",
    "id": 1,
    "prompt": "Сайт любителей рыбалки",
    "screenshot_url": "http://127.0.0.1:9000/my-public-bucket/index.png",
    "title": "Рыболовные приключения",
    "updated_at": datetime.fromisoformat("2025-08-20T18:29:56+00:00"),
}


class SiteNotFoundError(Exception):
    """Исключение, возникающее при попытке получить несуществующий сайт."""


class SiteRepository:
    """Mock репозиторий для работы с данными сайтов.

    Имитирует взаимодействие с ORM/базой данных. В реальной реализации
    должен быть заменен на настоящий репозиторий с доступом к БД.
    """

    @staticmethod
    def get_by_id(site_id: int) -> dict[str, Any]:
        if site_id == mock_site_data["id"]:
            return mock_site_data
        raise SiteNotFoundError(f"Site with ID {site_id} not found")

    @staticmethod
    def get_all() -> list[dict[str, Any]]:
        return [mock_site_data]

    @staticmethod
    def create() -> dict[str, Any]:
        return mock_site_data

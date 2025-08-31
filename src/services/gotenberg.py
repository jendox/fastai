from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import ClassVar, Self

import httpx
from gotenberg_api import GotenbergServerError, ScreenshotHTMLRequest
from httpx import Limits, Timeout

from src.config import GotenbergImageFormat

__all__ = (
    "AsyncGotenbergClient",
    "HTMLScreenshotError",
)

MAX_SCREENSHOT_WIDTH = 8192


class GotenbergAsyncClientError(Exception):
    """Базовое исключение для ошибок клиента Gotenberg"""


class HTMLScreenshotError(GotenbergAsyncClientError):
    """Ошибка создания скриншота HTML страницы"""


class AsyncGotenbergClient(httpx.AsyncClient):
    """Асинхронный клиент для взаимодействия с Gotenberg API
    (сервисом рендеринга HTML в изображения).

    Использует глобальный singleton-инстанс, который инициализируется методом `setup`
    и доступен через `get_initialized_instance`.
    """

    _initialized_instance: ClassVar[Self | None] = None

    def __init__(self, width: int, fmt: GotenbergImageFormat, delay: float, *args, **kwargs) -> None:
        self.image_width = width
        self.image_format = fmt
        self.animation_delay = delay
        super().__init__(*args, **kwargs)

    @classmethod
    @asynccontextmanager
    async def setup(
        cls,
        api_url: str,
        max_connections: int,
        screenshot_width: int,
        screenshot_timeout: float,
        screenshot_format: GotenbergImageFormat,
        screenshot_animation_delay: float,
    ) -> AsyncGenerator[None]:
        """
        Инициализация глобального клиента для использования в lifespan приложения

        Args:
            api_url: URL API Gotenberg.
            max_connections: Максимальное количество одновременных соединений.
            screenshot_width: Ширина скриншота по умолчанию.
            screenshot_timeout: Таймаут в секундах (connect/read/write).
            screenshot_format: Формат изображения (PNG/JPEG).
            screenshot_animation_delay: Задержка перед рендером.
        Returns:
            AsyncGenerator
        """
        cls._initialized_instance = cls(
            screenshot_width,
            screenshot_format,
            screenshot_animation_delay,
            base_url=api_url,
            timeout=Timeout(screenshot_timeout),
            limits=Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_connections,
            ),
        )
        async with cls._initialized_instance:
            yield

    @classmethod
    def get_initialized_instance(cls) -> Self:
        """ Получить текущий инициализированный клиент

        Raises:
            GotenbergAsyncClientError: если клиент не был инициализирован через `setup`.
        Returns:
            AsyncGotenbergClient: инициализированный клиент.
        """
        if initialized_instance := cls._initialized_instance:
            return initialized_instance
        raise GotenbergAsyncClientError(
            "Клиент AsyncGotenbergClient не был проинициализирован. "
            "Воспользуйтесь методом setup() для инициализации клиента.",
        )

    @classmethod
    async def screenshot_from_html(
        cls,
        raw_html: str,
        image_width: int | None = None,
        image_format: GotenbergImageFormat | None = None,
    ) -> bytes:
        """Создать скриншот из HTML-кода.

        Args:
            raw_html: HTML-код страницы.
            image_width: Ширина скриншота (если None — используется значение по умолчанию).
            image_format: Формат изображения (если None — используется значение по умолчанию).
        Returns:
            Байты изображения.
        Raises:
            HTMLScreenshotError: если не удалось создать скриншот.
        """
        if not raw_html:
            raise HTMLScreenshotError("HTML пустой")

        client = cls.get_initialized_instance()
        width = cls._normalize_image_width(image_width, client.image_width)
        fmt = image_format if image_format else client.image_format

        try:
            request = ScreenshotHTMLRequest(
                index_html=raw_html,
                width=width,
                format=fmt,
                wait_delay=client.animation_delay,
            )
            return await request.asend(client)

        except GotenbergServerError as e:
            raise HTMLScreenshotError(f"Ошибка создания скриншота: {e}") from e

    @staticmethod
    def _normalize_image_width(width: int | None, fallback: int) -> int:
        if width is None or width <= 0 or width > MAX_SCREENSHOT_WIDTH:
            return fallback
        return width

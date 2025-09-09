class GotenbergAsyncClientError(Exception):
    """Базовое исключение для ошибок клиента Gotenberg"""


class HTMLScreenshotError(GotenbergAsyncClientError):
    """Ошибка создания скриншота HTML страницы"""

"""Исключения для асинхронного S3-клиента."""


class AsyncS3ClientError(RuntimeError):
    """Базовое исключение для ошибок клиента S3.

    Используется при нарушениях жизненного цикла клиента (например, отсутствие
    глобальной инициализации через `setup()`), а также для обобщённых ошибок
    на уровне инфраструктуры.
    """


class UploadError(AsyncS3ClientError):
    """Исключение, выбрасываемое при неудачной загрузке объекта.

    Содержит исходную причину (`__cause__`) для диагностики. Может использоваться
    для маппинга на доменные ошибки уровня приложения.

    Пример:
        try:
            await client.upload(...)
        except UploadError as e:
            # логируем e и e.__cause__
            ...
    """

    def __init__(self, message: str, *, bucket: str | None = None, key: str | None = None):
        details = []
        if bucket:
            details.append(f"bucket={bucket}")
        if key:
            details.append(f"key={key}")
        suffix = f" ({', '.join(details)})" if details else ""
        super().__init__(f"{message}{suffix}")

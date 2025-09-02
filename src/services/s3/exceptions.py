"""Исключения для асинхронного S3-клиента."""


class AsyncS3ClientError(RuntimeError):
    """Базовое исключение для ошибок клиента S3."""


class UploadError(AsyncS3ClientError):
    """Исключение, выбрасываемое при неудачной загрузке объекта."""

    def __init__(self, message: str, *, bucket: str | None = None, key: str | None = None):
        details = []
        if bucket:
            details.append(f"bucket={bucket}")
        if key:
            details.append(f"key={key}")
        suffix = f" ({', '.join(details)})" if details else ""
        super().__init__(f"{message}{suffix}")

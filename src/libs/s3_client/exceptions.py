"""Исключения для асинхронного S3-клиента."""


class AsyncS3ClientError(RuntimeError):
    """Базовое исключение для ошибок клиента S3."""


class UploadError(AsyncS3ClientError):
    """Исключение, выбрасываемое при неудачной загрузке объекта."""

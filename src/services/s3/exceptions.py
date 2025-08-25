"""
Исключения для S3 клиента.
"""


class AsyncS3ClientError(Exception):
    """Базовое исключение для ошибок клиента S3"""


class UploadError(AsyncS3ClientError):
    """Вызывается при неудачной загрузке файла"""

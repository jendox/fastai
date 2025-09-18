from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict
from pydantic.alias_generators import to_pascal

__all__ = (
    "S3UploadParams",
)

s3_upload_params_config = ConfigDict(
    alias_generator=to_pascal,
    serialize_by_alias=True,
    validate_by_name=True,
    json_schema_extra={
        "examples": [
            {
                "Bucket": "my-bucket",
                "Key": "images/photo.png",
                "ContentType": "image/png",
                "ContentDisposition": "inline",
                "Metadata": {"source": "uploader", "project": "fastai"},
            },
        ],
    },
)


def normalize_key(value: str) -> str:
    value = value.strip()
    return value.lstrip("/")


def validate_mime(value: str) -> str:
    if "/" not in value or value.count("/") != 1:
        raise ValueError("Некорректный MIME-тип. Ожидается формат 'type/subtype'")
    return value


def validate_body(value: str | bytes) -> bytes:
    if isinstance(value, str):
        return value.encode(encoding="utf-8")
    return value


BucketKey = Annotated[str, AfterValidator(normalize_key)]
MimeType = Annotated[str, AfterValidator(validate_mime)]
ByteContent = Annotated[bytes, BeforeValidator(validate_body)]
ContentDispositionType = Literal["inline", "attachment"]


class S3UploadParams(BaseModel):
    bucket: str
    """Название бакета S3"""
    key: BucketKey
    """Ключ (путь) объекта внутри бакета"""
    body: ByteContent
    """Содержимое объекта. str автоматически преобразуется в bytes"""
    content_type: MimeType
    """MIME-тип содержимого (например, 'text/plain', 'image/png')"""
    content_disposition: ContentDispositionType
    """Директива Content-Disposition ('inline' или 'attachment')"""
    metadata: dict[str, str] | None = None
    """Пользовательские метаданные в формате key→value (оба значения — строки)"""

    model_config = s3_upload_params_config

    def to_s3_kwargs(self) -> dict:
        """Возвращает словарь параметров для передачи в aioboto3 (PascalCase, без None)."""
        return self.model_dump(exclude_none=True)

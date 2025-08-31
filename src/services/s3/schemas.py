from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_pascal

ContentDispositionType = Literal["inline", "attachment"]


class S3UploadParams(BaseModel):
    bucket: str = Field(..., min_length=1)
    """Название бакета S3"""
    key: str = Field(..., min_length=1)
    """Ключ (путь) объекта внутри бакета"""
    body: str | bytes | None = None
    """Содержимое объекта. Для multipart обычно не используется"""
    content_type: str | None = None
    """MIME-тип содержимого (например, 'text/plain', 'image/png')"""
    content_disposition: ContentDispositionType | None = None
    """Директива Content-Disposition ('inline' или 'attachment')"""
    metadata: dict[str, str] | None = None
    """Пользовательские метаданные в формате key→value (оба значения — строки)"""

    model_config = ConfigDict(
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

    @classmethod
    @field_validator("bucket")
    def _bucket_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Имя бакета не может быть пустым")
        return value

    @classmethod
    @field_validator("key")
    def _normalize_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ключ объекта (key) не может быть пустым")
        if value.startswith("/"):
            value = value.lstrip("/")
        return value

    @classmethod
    @field_validator("content_type")
    def _validate_mime(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "/" not in value or value.count("/") != 1:
            raise ValueError("Некорректный MIME-тип. Ожидается формат 'type/subtype'")
        return value

    @classmethod
    @field_validator("metadata", mode="before")
    def _normalize_metadata(cls, value: dict | None) -> dict[str, str] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("metadata должно быть словарём")
        return {str(k): str(v) for k, v in value.items()}

    def to_s3_kwargs(self) -> dict:
        """Возвращает словарь параметров для передачи в aioboto3 (PascalCase, без None)."""
        return self.model_dump(exclude_none=True)

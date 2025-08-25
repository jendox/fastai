from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_pascal

ContentDispositionType = Literal["inline", "attachment"]


class S3UploadParams(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_pascal,
        serialize_by_alias=True,
        validate_by_name=True,
    )

    bucket: str = Field(..., description="Название S3 bucket")
    key: str = Field(..., description="Ключ (путь) объекта в bucket")
    body: bytes | None = Field(None, description="Содержимое файла")
    content_type: str | None = Field(
        None,
        description="MIME-тип содержимого (например, 'text/plain')",
    )
    content_disposition: ContentDispositionType | None = Field(
        None,
        description="Директива Content-Disposition ('inline' или 'attachment')",
    )
    metadata: dict | None = Field(
        None,
        description="Метаданные объекта в виде key-value пар",
    )

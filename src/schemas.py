from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel

SITE_TITLE_EXAMPLE = "Фан клуб Домино"
SITE_PROMPT_EXAMPLE = "Сайт любителей играть в домино"

user_response_example = {
    "profile_id": 1,
    "email": "example@example.com",
    "username": "user123",
    "registered_at": datetime.fromisoformat("2025-06-15T18:29:56+00:00"),
    "updated_at": datetime.fromisoformat("2025-06-15T18:29:56+00:00"),
    "is_active": True,
}

site_response_example = {
    "created_at": datetime.fromisoformat("2025-06-15T18:29:56+00:00"),
    "html_code_download_url": "http://example.com/media/index.html?response-content-disposition=attachment",
    "html_code_url": "http://example.com/media/index.html",
    "id": 1,
    "prompt": SITE_PROMPT_EXAMPLE,
    "screenshot_url": "http://example.com/media/index.png",
    "title": SITE_TITLE_EXAMPLE,
    "updated_at": datetime.fromisoformat("2025-06-15T18:29:56+00:00"),
}


class UserDetailsResponse(BaseModel):
    profile_id: int
    email: EmailStr
    username: str = Field(..., max_length=254)
    registered_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [user_response_example],
        },
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )


class UserUnauthorizedResponse(BaseModel):
    detail: str = Field("UNAUTHORIZED")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"detail": "UNAUTHORIZED"}],
        },
    )


class CreateSiteRequest(BaseModel):
    title: str | None = Field(None, max_length=128)
    prompt: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "prompt": SITE_PROMPT_EXAMPLE,
                "title": SITE_TITLE_EXAMPLE,
            }],
        },
    )


class SiteGenerationRequest(BaseModel):
    prompt: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "prompt": SITE_PROMPT_EXAMPLE,
            }],
        },
    )


class SiteResponse(BaseModel):
    id: int
    title: str
    html_code_url: str | None
    html_code_download_url: str | None
    screenshot_url: str | None
    prompt: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [site_response_example],
        },
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )


class GeneratedSitesResponse(BaseModel):
    sites: list[SiteResponse]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"sites": [site_response_example]}],
        },
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )


class SiteNotFoundResponse(BaseModel):
    detail: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"detail": "Site with ID 1 not found"}],
        },
    )

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from starlette.responses import HTMLResponse, StreamingResponse

from src.schemas import SiteSchema
from src.services import SiteGenerator, SiteNotFoundError, SiteRepository

router = APIRouter(prefix="/sites")

SITE_TITLE_EXAMPLE = "Фан клуб Домино"
SITE_PROMPT_EXAMPLE = "Сайт любителей играть в домино"

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


# ========================================================
# REQUESTS SCHEMAS
# ========================================================

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


# ========================================================
# RESPONSES SCHEMAS
# ========================================================

class SiteResponse(SiteSchema):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
        json_schema_extra={
            "examples": [site_response_example],
        },
    )


class GeneratedSitesResponse(BaseModel):
    sites: list[SiteSchema]

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
        json_schema_extra={
            "examples": [{"sites": [site_response_example]}],
        },
    )


class SiteNotFoundResponse(BaseModel):
    detail: str

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
        json_schema_extra={
            "examples": [{"detail": "Site with ID 1 not found"}],
        },
    )


# ========================================================
# ROUTES
# ========================================================

@router.get(
    path="/my",
    summary="Получить список сгенерированных сайтов текущего пользователя",
    tags=["Sites"],
    response_model=GeneratedSitesResponse,
    response_model_by_alias=False,
)
async def get_my_sites() -> GeneratedSitesResponse:
    sites = SiteRepository.get_user_sites()
    return GeneratedSitesResponse(**sites)


@router.post(
    path="/create",
    summary="Создать сайт",
    tags=["Sites"],
    response_model=SiteResponse,
    response_model_by_alias=False,
)
async def create_site(
    request: CreateSiteRequest,
) -> SiteResponse:
    new_site = SiteRepository.create()
    return SiteResponse(**new_site)


@router.post(
    path="/{site_id}/generate",
    summary="Сгенерировать HTML код сайта",
    tags=["Sites"],
    response_class=HTMLResponse,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "text/html": {
                    "example": "<html><body>Сгенерированный контент</body></html>",
                },
            },
        },
    },
)
async def generate_site(
    site_id: int,
    request: SiteGenerationRequest,
):
    return StreamingResponse(
        # content=SiteGenerator.generate_from_prompt(request.prompt),
        content=SiteGenerator.mock_generate_from_prompt(),
        media_type="text/html; charset=utf-8",
    )


@router.get(
    path="/{site_id}",
    summary="Получить сайт",
    tags=["Sites"],
    responses={
        200: {
            "description": "Successful Response",
            "model": SiteResponse,
        },
        404: {
            "description": "Error Response",
            "model": SiteNotFoundResponse,
        },
    },
    response_model_by_alias=False,
)
async def get_site(site_id: int) -> SiteResponse:
    try:
        site_data = SiteRepository.get_by_id(site_id)
        return SiteResponse(**site_data)
    except SiteNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Site with ID {site_id} not found",
        )

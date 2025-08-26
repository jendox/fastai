from fastapi import APIRouter
from starlette.responses import HTMLResponse, StreamingResponse

from src.schemas import (
    CreateSiteRequest,
    GeneratedSitesResponse,
    SiteGenerationRequest,
    SiteNotFoundResponse,
    SiteResponse,
)
from src.services import SiteService

router = APIRouter(prefix="/sites")


@router.get(
    path="/my",
    summary="Получить список сгенерированных сайтов текущего пользователя",
    tags=["Sites"],
    response_model=GeneratedSitesResponse,
    response_model_by_alias=False,
)
async def get_my_sites() -> GeneratedSitesResponse:
    return GeneratedSitesResponse(**SiteService.get_my_sites())


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
    return SiteResponse(**SiteService.create_site())


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
        # content=SiteService.generate_html(request.prompt),
        content=SiteService.mock_generate_site(),
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
async def get_site(site_id: int):
    site_data = SiteService.get_site(site_id)
    if site_data:
        return SiteResponse(**site_data)
    return SiteNotFoundResponse(**{"detail": f"Site with ID {site_id} not found"})

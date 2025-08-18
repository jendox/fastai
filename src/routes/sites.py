import asyncio
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from starlette.responses import HTMLResponse, StreamingResponse

from src.schemas import (
    CreateSiteRequest,
    GeneratedSitesResponse,
    SiteGenerationRequest,
    SiteNotFoundResponse,
    SiteResponse,
)

site_mock_data = {
    "created_at": "2025-06-15T18:29:56+00:00",
    "html_code_download_url": "https://dvmn.org/media/filer_public/d1/4b/d14bb4e8-d8b4-49cb-928d-fd04ecae46da/index.html?response-content-disposition=attachment",
    "html_code_url": "https://dvmn.org/media/filer_public/d1/4b/d14bb4e8-d8b4-49cb-928d-fd04ecae46da/index.html",
    "id": 1,
    "prompt": "Стегозавры величественные гиганты Юрского периода",
    "screenshot_url": "https://images.unsplash.com/photo-1729207512292-da69be60b05a",
    "title": "Стегозавры",
    "updated_at": datetime.fromisoformat("2025-06-15T18:29:56+00:00"),
}

router = APIRouter(prefix="/sites")


async def generate_site_mock(chunk_size: int = 1024):
    path = Path(f"{os.getcwd()}/data/index.html")
    with open(path, encoding="utf-8") as file:
        while data := file.read(chunk_size):
            yield data
            await asyncio.sleep(1)


@router.get(
    path="/my",
    summary="Получить список сгенерированных сайтов текущего пользователя",
    tags=["Sites"],
    response_model=GeneratedSitesResponse,
    response_model_by_alias=False,
)
async def get_my_sites() -> GeneratedSitesResponse:
    return GeneratedSitesResponse(**{"sites": [site_mock_data]})


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
    return SiteResponse(**site_mock_data)


@router.post(
    path="/{site_id}/generate",
    summary="Сгенерировать HTML код сайта",
    tags=["Sites"],
    response_class=HTMLResponse,
)
async def generate_site(
    site_id: int,
    request: SiteGenerationRequest,
):
    return StreamingResponse(
        content=generate_site_mock(),
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
    site_data = SiteResponse(**site_mock_data)
    if site_id == site_data.id:
        return site_data
    return SiteNotFoundResponse(**{"detail": f"Site with ID {site_id} not found"})

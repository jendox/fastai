from fastapi import APIRouter

from .sites import router as sites_router
from .users import router as users_router

__all__ = ("frontend_router",)

frontend_router = APIRouter(prefix="/frontend-api")

frontend_router.include_router(users_router)
frontend_router.include_router(sites_router)

from datetime import datetime

from fastapi import APIRouter
from fastapi.exceptions import ResponseValidationError
from pydantic import ValidationError

from src.schemas import UserDetailsResponse, UserUnauthorizedResponse

router = APIRouter(prefix="/users")

mock_user_data = {
    "email": "jendox1985@gmail.com",
    "is_active": True,
    "profile_id": 1,
    "registered_at": datetime.fromisoformat("2025-08-07T18:29:56+00:00"),
    "updated_at": datetime.fromisoformat("2025-08-07T18:29:56+00:00"),
    "username": "jendox",
}


def get_current_user() -> UserDetailsResponse:
    try:
        return UserDetailsResponse(**mock_user_data)
    except ValidationError as e:
        raise ResponseValidationError(errors=e.errors())


@router.get(
    path="/me",
    summary="Получить учетные данные пользователя",
    tags=["Users"],
    responses={
        200: {
            "description": "Successful Response",
            "model": UserDetailsResponse,
        },
        401: {
            "description": "Error Response",
            "model": UserUnauthorizedResponse,
        },
    },
    response_model_by_alias=False,
)
async def get_me() -> UserDetailsResponse:
    return get_current_user()

from datetime import datetime

from fastapi import APIRouter
from fastapi.exceptions import ResponseValidationError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError
from pydantic.alias_generators import to_camel

router = APIRouter(prefix="/users")

mock_user_data = {
    "email": "jendox1985@gmail.com",
    "is_active": True,
    "profile_id": 1,
    "registered_at": datetime.fromisoformat("2025-08-07T18:29:56+00:00"),
    "updated_at": datetime.fromisoformat("2025-08-07T18:29:56+00:00"),
    "username": "jendox",
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
            "examples": [{
                "profile_id": 1,
                "email": "example@example.com",
                "username": "user123",
                "registered_at": datetime.fromisoformat("2025-06-15T18:29:56+00:00"),
                "updated_at": datetime.fromisoformat("2025-06-15T18:29:56+00:00"),
                "is_active": True,
            }],
        },
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )


class UserUnauthorizedResponse(BaseModel):
    detail: str = "UNAUTHORIZED"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"detail": "UNAUTHORIZED"}],
        },
    )


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

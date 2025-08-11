from fastapi import APIRouter

router = APIRouter(prefix="/frontend-api")

mock_user_data = {
    "email": "jendox1985@gmail.com",
    "is_active": True,
    "profile_id": 1,
    "registered_at": "2025-08-07T18:29:56+00:00",
    "updated_at": "2025-08-07T18:29:56+00:00",
    "username": "jendox",
}


@router.get(
    path="/users/me",
    summary="Получить учетные данные пользователя",
    tags=["users"],
)
async def get_me():
    return mock_user_data

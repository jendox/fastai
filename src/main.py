from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from src.constants import APP_DESCRIPTION, APP_TITLE
from src.routes import users_router

app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION)

app.include_router(users_router)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

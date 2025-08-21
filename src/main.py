from contextlib import asynccontextmanager
from textwrap import dedent

from fastapi import FastAPI
from html_page_generator import AsyncDeepseekClient, AsyncUnsplashClient
from starlette.staticfiles import StaticFiles

from src.config import settings
from src.routes import frontend_router


@asynccontextmanager
async def lifespan(fast_api_app: FastAPI):
    async with (
        AsyncDeepseekClient.setup(settings.deepseek.api_key),
        AsyncUnsplashClient.setup(settings.unsplash.api_key, timeout=3),
    ):
        yield


app = FastAPI(
    title="🚀 FastAI Website Generator – AI-Powered Instant Websites",
    description=dedent("""\
        FastAI is a cutting-edge web application built with FastAPI that leverages AI to generate fully \
        functional websites in seconds. Simply provide a brief description of your desired website, and \
        FastAI will create a responsive, customizable template using OpenAI's API. Store your projects in \
        cloud storage, edit them on the fly, and deploy with ease. Perfect for developers, designers, \
        and entrepreneurs who want to automate website creation while mastering FastAPI, AI integration, \
        and cloud services.
        """,
    ),
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(frontend_router)
app.mount("/data", StaticFiles(directory="data", html=True), name="data")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

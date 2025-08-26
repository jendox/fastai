from contextlib import asynccontextmanager
from textwrap import dedent

from fastapi import FastAPI
from html_page_generator import AsyncDeepseekClient, AsyncUnsplashClient
from starlette.staticfiles import StaticFiles

from src.config import settings
from src.routes import frontend_router
from src.services.s3 import AsyncS3Client


@asynccontextmanager
async def lifespan(fast_api_app: FastAPI):
    async with (
        AsyncDeepseekClient.setup(
            deepseek_api_key=settings.deepseek.api_key,
        ),
        AsyncUnsplashClient.setup(
            unsplash_client_id=settings.unsplash.api_key,
            timeout=settings.unsplash.timeout,
        ),
        AsyncS3Client.setup(
            endpoint_url=settings.s3.endpoint_url,
            access_key=settings.s3.access_key,
            secret_key=settings.s3.secret_key,
            max_pool_connections=settings.s3.max_connections,
            connect_timeout=settings.s3.connect_timeout,
            read_timeout=settings.s3.read_timeout,
        ),
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

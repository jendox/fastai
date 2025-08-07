from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

app = FastAPI(
    title="🚀 FastAI Website Generator – AI-Powered Instant Websites",
    description="FastAI is a cutting-edge web application built with FastAPI that leverages AI to generate fully "
                "functional websites in seconds. Simply provide a brief description of your desired website, and "
                "FastAI will create a responsive, customizable template using OpenAI's API. Store your projects in "
                "cloud storage, edit them on the fly, and deploy with ease. Perfect for developers, designers, "
                "and entrepreneurs who want to automate website creation while mastering FastAPI, AI integration, "
                "and cloud services.",
)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

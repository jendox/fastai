from datetime import datetime

from pydantic import BaseModel


class SiteSchema(BaseModel):
    """Общая схема сайта"""
    id: int
    title: str
    html_code_url: str | None
    html_code_download_url: str | None
    screenshot_url: str | None
    prompt: str
    created_at: datetime
    updated_at: datetime

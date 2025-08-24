import os
import pathlib

import aioboto3
import aiofiles
from aiobotocore.config import AioConfig

from src.config import settings


class S3Service:
    def __init__(self):
        self.endpoint_url = settings.s3.endpoint_url
        self.config = AioConfig(
            max_pool_connections=settings.s3.max_connections,
            connect_timeout=settings.s3.connect_timeout,
            read_timeout=settings.s3.read_timeout,
        )
        self.session = aioboto3.Session(
            aws_access_key_id=settings.s3.login.get_secret_value(),
            aws_secret_access_key=settings.s3.password.get_secret_value(),
        )

    async def _upload(self, upload_data: dict) -> bool:
        try:
            async with self.session.client(
                service_name="s3",
                config=self.config,
                endpoint_url=self.endpoint_url,
            ) as s3_client:
                await s3_client.put_object(**upload_data)
                return True

        except Exception as e:
            print(f"Failed to upload {upload_data.get('Key')}: {str(e)}")
            raise

    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_path: str,
        content_type: str | None = None,
        content_disposition: str | None = None,
        metadata: dict | None = None,
    ) -> bool:
        try:
            async with aiofiles.open(file_path, "rb") as file:
                file_content = await file.read()

            upload_data = {
                "Bucket": bucket,
                "Key": key,
                "Body": file_content,
                "ContentType": content_type,
                "ContentDisposition": content_disposition,
            }
            if metadata:
                upload_data["Metadata"] = metadata
            return await self._upload(upload_data)

        except Exception as e:
            print(f"Failed to upload file {file_path}: {str(e)}")
            raise


async def test_s3_service():
    s3_service = S3Service()
    file_path = pathlib.Path(os.getcwd(), "data/index.html")
    try:
        await s3_service.upload_file(
            bucket=settings.s3.bucket,
            key="index.html",
            file_path=str(file_path),
            content_type="text/html",
            content_disposition="inline",
        )
        print("File uploaded successfully")

    except Exception as e:
        print(f"Test failed: {str(e)}")

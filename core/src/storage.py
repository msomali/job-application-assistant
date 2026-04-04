"""MinIO/S3-compatible object storage client for PDFs and screenshots."""

import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class StorageClient:
    """S3-compatible storage client. Works with MinIO locally, AWS S3 in production."""

    def __init__(self) -> None:
        endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        use_ssl = os.environ.get("MINIO_USE_SSL", "false").lower() == "true"
        scheme = "https" if use_ssl else "http"

        self._client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{endpoint}",
            aws_access_key_id=os.environ.get("MINIO_ROOT_USER", "minioadmin"),
            aws_secret_access_key=os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin"),
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._documents_bucket = os.environ.get("MINIO_DOCUMENTS_BUCKET", "jobapp-documents")
        self._screenshots_bucket = os.environ.get("MINIO_SCREENSHOTS_BUCKET", "jobapp-screenshots")

    def upload_document(self, tenant_id: str, filename: str, local_path: str) -> str:
        key = f"{tenant_id}/{filename}"
        self._client.upload_file(local_path, self._documents_bucket, key)
        logger.info("Uploaded document: %s/%s", self._documents_bucket, key)
        return key

    def upload_screenshot(self, tenant_id: str, filename: str, local_path: str) -> str:
        key = f"{tenant_id}/{filename}"
        self._client.upload_file(local_path, self._screenshots_bucket, key)
        return key

    def get_document_url(self, key: str, expires_in: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._documents_bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def get_screenshot_url(self, key: str, expires_in: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._screenshots_bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_document(self, key: str) -> None:
        self._client.delete_object(Bucket=self._documents_bucket, Key=key)
        logger.info("Deleted document: %s/%s", self._documents_bucket, key)

    def delete_screenshot(self, key: str) -> None:
        self._client.delete_object(Bucket=self._screenshots_bucket, Key=key)

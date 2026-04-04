"""Tests for MinIO/S3 storage helper."""

from unittest.mock import MagicMock, patch

import pytest

from src.storage import StorageClient


@pytest.fixture
def mock_boto3():
    with patch("src.storage.boto3") as mock:
        mock_client = MagicMock()
        mock.client.return_value = mock_client
        yield mock_client


def test_upload_file(mock_boto3, tmp_path):
    client = StorageClient.__new__(StorageClient)
    client._client = mock_boto3
    client._documents_bucket = "jobapp-documents"
    client._screenshots_bucket = "jobapp-screenshots"

    test_file = tmp_path / "resume.pdf"
    test_file.write_bytes(b"%PDF-fake-content")

    key = client.upload_document("tenant-123", "resume.pdf", str(test_file))

    mock_boto3.upload_file.assert_called_once_with(
        str(test_file), "jobapp-documents", "tenant-123/resume.pdf"
    )
    assert key == "tenant-123/resume.pdf"


def test_get_presigned_url(mock_boto3):
    client = StorageClient.__new__(StorageClient)
    client._client = mock_boto3
    client._documents_bucket = "jobapp-documents"
    client._screenshots_bucket = "jobapp-screenshots"
    mock_boto3.generate_presigned_url.return_value = "https://minio:9000/signed-url"

    url = client.get_document_url("tenant-123/resume.pdf")

    mock_boto3.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "jobapp-documents", "Key": "tenant-123/resume.pdf"},
        ExpiresIn=3600,
    )
    assert url == "https://minio:9000/signed-url"


def test_delete_document(mock_boto3):
    client = StorageClient.__new__(StorageClient)
    client._client = mock_boto3
    client._documents_bucket = "jobapp-documents"
    client._screenshots_bucket = "jobapp-screenshots"

    client.delete_document("tenant-123/resume.pdf")

    mock_boto3.delete_object.assert_called_once_with(
        Bucket="jobapp-documents", Key="tenant-123/resume.pdf"
    )

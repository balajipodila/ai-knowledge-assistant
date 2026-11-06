from pathlib import Path
from typing import Any

import boto3
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.storage import (
    LocalFileStorage,
    S3FileStorage,
    create_file_storage,
)


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> dict[str, str]:
        self.put_calls.append(kwargs)
        return {}

    def delete_object(self, **kwargs: Any) -> dict[str, str]:
        self.delete_calls.append(kwargs)
        return {}


def test_s3_file_storage_saves_pdf_with_generated_key() -> None:
    client = FakeS3Client()
    storage = S3FileStorage(
        bucket="test-bucket",
        endpoint_url="https://storage.example.invalid",
        region="auto",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
        client=client,
    )

    storage_key = storage.save(b"%PDF-1.7 fake content")

    assert storage_key.endswith(".pdf")
    assert len(storage_key.removesuffix(".pdf")) == 32
    assert client.put_calls == [
        {
            "Bucket": "test-bucket",
            "Key": storage_key,
            "Body": b"%PDF-1.7 fake content",
            "ContentType": "application/pdf",
        }
    ]


def test_s3_file_storage_deletes_object_by_key() -> None:
    client = FakeS3Client()
    storage = S3FileStorage(
        bucket="test-bucket",
        endpoint_url="https://storage.example.invalid",
        region="auto",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
        client=client,
    )

    storage.delete("a" * 32 + ".pdf")

    assert client.delete_calls == [
        {"Bucket": "test-bucket", "Key": "a" * 32 + ".pdf"}
    ]


def test_s3_file_storage_rejects_path_like_delete_key() -> None:
    storage = S3FileStorage(
        bucket="test-bucket",
        endpoint_url="https://storage.example.invalid",
        region="auto",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
        client=FakeS3Client(),
    )

    with pytest.raises(ValueError, match="plain file names"):
        storage.delete("../other.pdf")


def test_storage_factory_keeps_local_storage_as_default(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, upload_directory=tmp_path)

    storage = create_file_storage(settings)

    assert isinstance(storage, LocalFileStorage)


def test_storage_factory_creates_s3_storage_without_cloud_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeS3Client()
    client_arguments: dict[str, Any] = {}

    def fake_boto3_client(service_name: str, **kwargs: Any) -> FakeS3Client:
        client_arguments.update(service_name=service_name, **kwargs)
        return fake_client

    monkeypatch.setattr(boto3, "client", fake_boto3_client)
    settings = Settings(
        _env_file=None,
        FILE_STORAGE_BACKEND="s3",
        S3_ENDPOINT_URL="https://storage.example.invalid",
        S3_BUCKET="test-bucket",
        S3_ACCESS_KEY_ID="test-access-key",
        S3_SECRET_ACCESS_KEY="test-secret-key",
    )

    storage = create_file_storage(settings)

    assert isinstance(storage, S3FileStorage)
    assert client_arguments["service_name"] == "s3"
    assert client_arguments["endpoint_url"] == "https://storage.example.invalid"
    assert client_arguments["region_name"] == "auto"
    assert client_arguments["aws_access_key_id"] == "test-access-key"
    assert client_arguments["aws_secret_access_key"] == "test-secret-key"
    config = client_arguments["config"]
    assert config.request_checksum_calculation == "when_required"
    assert config.response_checksum_validation == "when_required"


def test_s3_storage_requires_complete_configuration() -> None:
    with pytest.raises(ValidationError, match="S3 storage requires"):
        Settings(_env_file=None, FILE_STORAGE_BACKEND="s3")


def test_s3_storage_rejects_invalid_endpoint_without_exposing_credentials() -> None:
    with pytest.raises(ValidationError, match="absolute HTTP"):
        Settings(
            _env_file=None,
            FILE_STORAGE_BACKEND="s3",
            S3_ENDPOINT_URL="not-a-url",
            S3_BUCKET="test-bucket",
            S3_ACCESS_KEY_ID="test-access-key",
            S3_SECRET_ACCESS_KEY="test-secret-key",
        )

    with pytest.raises(ValidationError, match="S3 storage requires"):
        Settings(
            _env_file=None,
            FILE_STORAGE_BACKEND="s3",
            S3_ENDPOINT_URL="https://storage.example.invalid",
            S3_BUCKET="test-bucket",
            S3_ACCESS_KEY_ID=" ",
            S3_SECRET_ACCESS_KEY="test-secret-key",
        )

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import boto3
from botocore.client import Config

from app.core.config import Settings


class FileStorage(ABC):
    @abstractmethod
    def save(self, data: bytes) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, storage_key: str | None) -> None:
        raise NotImplementedError


class NoneFileStorage(FileStorage):
    def save(self, data: bytes) -> str | None:
        return None

    def delete(self, storage_key: str | None) -> None:
        pass


class LocalFileStorage(FileStorage):
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()

    def save(self, data: bytes) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        storage_key = f"{uuid4().hex}.pdf"
        path = self._path_for(storage_key)
        path.write_bytes(data)
        return storage_key

    def delete(self, storage_key: str) -> None:
        path = self._path_for(storage_key)
        if path.exists():
            path.unlink()

    def _path_for(self, storage_key: str) -> Path:
        if Path(storage_key).name != storage_key:
            raise ValueError("Storage keys must be plain file names.")
        candidate = (self.directory / storage_key).resolve()
        if candidate.parent != self.directory:
            raise ValueError("Storage key resolves outside the storage directory.")
        return candidate


class S3Client(Protocol):
    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
    ) -> object: ...

    def delete_object(self, *, Bucket: str, Key: str) -> object: ...


class S3FileStorage(FileStorage):
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        max_attempts: int = 3,
        request_checksum_calculation: str = "when_required",
        response_checksum_validation: str = "when_required",
        client: S3Client | None = None,
    ) -> None:
        self.bucket = bucket
        self.client = (
            client
            if client is not None
            else boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=region or "auto",
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                config=Config(
                    s3={"addressing_style": "path"},
                    signature_version="s3v4",
                    connect_timeout=connect_timeout,
                    read_timeout=read_timeout,
                    retries={"max_attempts": max_attempts, "mode": "standard"},
                    request_checksum_calculation=request_checksum_calculation,
                    response_checksum_validation=response_checksum_validation,
                ),
            )
        )

    def save(self, data: bytes) -> str:
        storage_key = f"{uuid4().hex}.pdf"
        self.client.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=data,
            ContentType="application/pdf",
        )
        return storage_key

    def delete(self, storage_key: str) -> None:
        if not storage_key or Path(storage_key).name != storage_key:
            raise ValueError("Storage keys must be plain file names.")
        self.client.delete_object(Bucket=self.bucket, Key=storage_key)


def create_file_storage(settings: Settings) -> FileStorage:
    if settings.file_storage_backend == "none":
        return NoneFileStorage()
    if settings.file_storage_backend == "local":
        return LocalFileStorage(settings.upload_directory)

    if (
        settings.s3_endpoint_url is None
        or settings.s3_bucket is None
        or settings.s3_access_key_id is None
        or settings.s3_secret_access_key is None
    ):
        raise ValueError("S3 storage configuration is incomplete.")

    return S3FileStorage(
        bucket=settings.s3_bucket,
        endpoint_url=settings.s3_endpoint_url,
        region=settings.s3_region,
        access_key_id=settings.s3_access_key_id.get_secret_value(),
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        connect_timeout=settings.s3_connect_timeout_seconds,
        read_timeout=settings.s3_read_timeout_seconds,
        max_attempts=settings.s3_max_attempts,
        request_checksum_calculation=settings.s3_request_checksum_calculation,
        response_checksum_validation=settings.s3_response_checksum_validation,
    )

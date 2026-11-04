from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import boto3

from app.core.config import Settings


class FileStorage(ABC):
    @abstractmethod
    def save(self, data: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        raise NotImplementedError


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
        client: S3Client | None = None,
    ) -> None:
        self.bucket = bucket
        self.client = (
            client
            if client is not None
            else boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=region,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
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
    )

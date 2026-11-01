from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4


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

"""Object storage adapters.

`local` writes under ./.local-storage (dev + tests, zero external deps);
`s3` talks to any S3-compatible endpoint (RustFS in dev, real S3 in prod).
Selected by OBJECT_STORAGE_PROVIDER — never instantiate boto3 directly
outside this module.
"""

import re
from pathlib import Path
from typing import Protocol

from app.core.config import Settings, get_settings

_SAFE_KEY = re.compile(r"^[A-Za-z0-9._\-/]+$")


class StorageError(Exception):
    pass


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


def validate_key(key: str) -> str:
    """Reject path traversal and weird keys before they touch any backend."""
    if not key or ".." in key or key.startswith("/") or not _SAFE_KEY.match(key):
        raise StorageError(f"Unsafe storage key: {key!r}")
    return key


class LocalObjectStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        validate_key(key)
        p = (self._root / key).resolve()
        # Defense in depth: resolved path must stay under root.
        if self._root.resolve() not in p.parents and p != self._root.resolve():
            raise StorageError(f"Key escapes storage root: {key!r}")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(f"Object not found: {key}") from exc

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        import boto3

        self._bucket = settings.object_storage_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint or None,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            region_name=settings.object_storage_region,
        )

    def put(self, key: str, data: bytes) -> None:
        validate_key(key)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def get(self, key: str) -> bytes:
        validate_key(key)
        try:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except Exception as exc:
            raise StorageError(f"Object not found: {key}") from exc

    def delete(self, key: str) -> None:
        validate_key(key)
        self._client.delete_object(Bucket=self._bucket, Key=key)


def get_storage(settings: Settings | None = None) -> ObjectStorage:
    settings = settings or get_settings()
    if settings.object_storage_provider == "local":
        return LocalObjectStorage(settings.local_storage_dir)
    return S3ObjectStorage(settings)

"""Storage backend implementations."""

from benchmark.storage.base import StorageBackend
from benchmark.storage.local import LocalStorage
from benchmark.storage.s3 import S3RequestsStorage

__all__ = ["StorageBackend", "LocalStorage", "S3RequestsStorage"]

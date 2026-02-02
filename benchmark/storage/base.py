"""Storage backend protocol definition."""

from typing import Iterator, Protocol


class StorageBackend(Protocol):
    """Protocol for storage backends (local filesystem or S3-compatible)."""

    name: str

    def save(self, key: str, content: bytes) -> None:
        """Save content to storage at the given key."""
        ...

    def load(self, key: str) -> bytes | None:
        """Load content from storage. Returns None if not found."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
        ...

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        """List all keys with the given prefix."""
        ...

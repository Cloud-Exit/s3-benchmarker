"""Local filesystem storage backend."""

from pathlib import Path
from typing import Iterator


class LocalStorage:
    """Storage backend using local filesystem."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.name = f"local filesystem ({self.base_path.absolute()})"

    def _resolve(self, key: str) -> Path:
        """Resolve a key to a full path."""
        return self.base_path / key

    def save(self, key: str, content: bytes) -> None:
        """Save content to a file."""
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def load(self, key: str) -> bytes | None:
        """Load content from a file. Returns None if not found."""
        path = self._resolve(key)
        if not path.exists():
            return None
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        """Check if a file exists."""
        return self._resolve(key).exists()

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        """List all files with the given prefix."""
        search_path = self._resolve(prefix) if prefix else self.base_path

        if search_path.is_file():
            yield prefix
            return

        if not search_path.exists():
            return

        for path in search_path.rglob("*"):
            if path.is_file():
                yield str(path.relative_to(self.base_path))

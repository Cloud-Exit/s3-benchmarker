"""Base benchmark class."""

import time
from dataclasses import dataclass
from typing import Protocol


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""

    operation: str
    file_size: int
    file_count: int
    total_bytes: int
    duration: float
    throughput_mbps: float
    ops_per_sec: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    variance_pct: float = 0.0  # Variance in throughput (for multiple runs)
    runs: int = 1  # Number of times this test was run

    def __str__(self) -> str:
        """Format result as string."""
        size_str = self._format_size(self.file_size)
        variance_str = f"±{self.variance_pct:.1f}%" if self.variance_pct > 0 else "N/A"

        return (
            f"{self.operation:8s} | "
            f"Size: {size_str:8s} | "
            f"Count: {self.file_count:5d} | "
            f"Throughput: {self.throughput_mbps:7.2f} MB/s | "
            f"IOPS: {self.ops_per_sec:7.2f} | "
            f"Latency: {self.avg_latency_ms:6.2f}ms | "
            f"Variance: {variance_str:>8s}"
        )

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.0f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.0f}MB"


class StorageProtocol(Protocol):
    """Protocol for storage backends."""

    name: str

    def save(self, key: str, content: bytes) -> None:
        ...

    def load(self, key: str) -> bytes | None:
        ...

    def exists(self, key: str) -> bool:
        ...


class BaseBenchmark:
    """Base class for benchmarks."""

    def __init__(self, storage: StorageProtocol, prefix: str = "benchmark-test"):
        self.storage = storage
        self.prefix = prefix

    def _generate_data(self, size: int) -> bytes:
        """Generate test data of specified size."""
        # Use a pattern that compresses poorly to simulate real data
        pattern = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        repeats = (size + len(pattern) - 1) // len(pattern)
        return (pattern * repeats)[:size]

    def _get_test_key(self, index: int, size: int) -> str:
        """Generate a test key."""
        return f"{self.prefix}/{size}bytes/file_{index:05d}.dat"

    def _cleanup_files(self, keys: list[str]) -> None:
        """Clean up test files."""
        # Note: In production, you might want to implement batch deletion
        # For now, we'll leave cleanup as optional
        pass

"""Read benchmark implementation."""

import concurrent.futures
import time

from benchmark.benchmarks.base import BaseBenchmark, BenchmarkResult


class ReadBenchmark(BaseBenchmark):
    """Benchmark for read operations."""

    def run_sequential(self, file_size: int, file_count: int) -> BenchmarkResult:
        """Run sequential read benchmark."""
        latencies = []

        start_time = time.time()
        for i in range(file_count):
            key = self._get_test_key(i, file_size)
            op_start = time.time()
            data = self.storage.load(key)
            latencies.append((time.time() - op_start) * 1000)  # ms

            if data is None:
                raise ValueError(f"File not found: {key}")

        duration = time.time() - start_time
        total_bytes = file_size * file_count

        return BenchmarkResult(
            operation="READ",
            file_size=file_size,
            file_count=file_count,
            total_bytes=total_bytes,
            duration=duration,
            throughput_mbps=(total_bytes / (1024 * 1024)) / duration,
            ops_per_sec=file_count / duration,
            avg_latency_ms=sum(latencies) / len(latencies),
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
        )

    def run_parallel(
        self, file_size: int, file_count: int, max_workers: int = 10
    ) -> BenchmarkResult:
        """Run parallel read benchmark."""
        latencies = []

        def read_file(index: int) -> float:
            """Read a single file and return latency."""
            key = self._get_test_key(index, file_size)
            op_start = time.time()
            data = self.storage.load(key)
            if data is None:
                raise ValueError(f"File not found: {key}")
            return (time.time() - op_start) * 1000  # ms

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            latencies = list(executor.map(read_file, range(file_count)))

        duration = time.time() - start_time
        total_bytes = file_size * file_count

        return BenchmarkResult(
            operation="READ-P",
            file_size=file_size,
            file_count=file_count,
            total_bytes=total_bytes,
            duration=duration,
            throughput_mbps=(total_bytes / (1024 * 1024)) / duration,
            ops_per_sec=file_count / duration,
            avg_latency_ms=sum(latencies) / len(latencies),
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
        )

"""SQLite database for storing benchmark results."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmark.benchmarks.base import BenchmarkResult


class BenchmarkDatabase:
    """Database for storing and querying benchmark results."""

    def __init__(self, db_path: str | Path = "benchmark_results.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()

        # Benchmark runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                run_name TEXT,
                test_profile TEXT,
                workers INTEGER,
                notes TEXT
            )
        """)

        # Check if we need to migrate existing tables
        self._migrate_tables()

        # Results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                provider_name TEXT NOT NULL,
                provider_type TEXT NOT NULL,
                operation TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_count INTEGER NOT NULL,
                total_bytes INTEGER NOT NULL,
                duration REAL NOT NULL,
                throughput_mbps REAL NOT NULL,
                ops_per_sec REAL NOT NULL,
                avg_latency_ms REAL NOT NULL,
                min_latency_ms REAL NOT NULL,
                max_latency_ms REAL NOT NULL,
                variance_pct REAL DEFAULT 0.0,
                runs INTEGER DEFAULT 1,
                FOREIGN KEY (run_id) REFERENCES benchmark_runs (id)
            )
        """)

        # Create indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_results_run_id ON results (run_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_results_provider ON results (provider_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON benchmark_runs (timestamp)"
        )

        self.conn.commit()

    def _migrate_tables(self) -> None:
        """Migrate existing tables to add new columns."""
        cursor = self.conn.cursor()

        # Check if variance_pct column exists
        cursor.execute("PRAGMA table_info(results)")
        columns = [row[1] for row in cursor.fetchall()]

        if "variance_pct" not in columns:
            print("  [DB] Migrating database: adding variance_pct column...")
            cursor.execute("ALTER TABLE results ADD COLUMN variance_pct REAL DEFAULT 0.0")
            self.conn.commit()

        if "runs" not in columns:
            print("  [DB] Migrating database: adding runs column...")
            cursor.execute("ALTER TABLE results ADD COLUMN runs INTEGER DEFAULT 1")
            self.conn.commit()

    def create_run(
        self,
        run_name: str | None = None,
        test_profile: str = "default",
        workers: int = 10,
        notes: str | None = None,
    ) -> int:
        """Create a new benchmark run and return its ID."""
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT INTO benchmark_runs (timestamp, run_name, test_profile, workers, notes)
            VALUES (?, ?, ?, ?, ?)
        """,
            (timestamp, run_name, test_profile, workers, notes),
        )

        self.conn.commit()
        return cursor.lastrowid

    def add_result(
        self, run_id: int, provider_name: str, provider_type: str, result: BenchmarkResult
    ) -> None:
        """Add a benchmark result to the database."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO results (
                run_id, provider_name, provider_type, operation,
                file_size, file_count, total_bytes, duration,
                throughput_mbps, ops_per_sec,
                avg_latency_ms, min_latency_ms, max_latency_ms,
                variance_pct, runs
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                run_id,
                provider_name,
                provider_type,
                result.operation,
                result.file_size,
                result.file_count,
                result.total_bytes,
                result.duration,
                result.throughput_mbps,
                result.ops_per_sec,
                result.avg_latency_ms,
                result.min_latency_ms,
                result.max_latency_ms,
                result.variance_pct,
                result.runs,
            ),
        )

        self.conn.commit()

    def get_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent benchmark runs."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, run_name, test_profile, workers, notes
            FROM benchmark_runs
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_run_results(self, run_id: int) -> list[dict[str, Any]]:
        """Get all results for a specific run."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM results
            WHERE run_id = ?
            ORDER BY provider_name, operation, file_size
        """,
            (run_id,),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_provider_comparison(
        self, provider_names: list[str] | None = None, operation: str | None = None
    ) -> list[dict[str, Any]]:
        """Get comparison data for providers."""
        cursor = self.conn.cursor()

        query = """
            SELECT
                provider_name,
                operation,
                file_size,
                AVG(throughput_mbps) as avg_throughput,
                AVG(ops_per_sec) as avg_iops,
                AVG(avg_latency_ms) as avg_latency,
                COUNT(*) as sample_count
            FROM results
            WHERE 1=1
        """
        params = []

        if provider_names:
            placeholders = ",".join("?" * len(provider_names))
            query += f" AND provider_name IN ({placeholders})"
            params.extend(provider_names)

        if operation:
            query += " AND operation = ?"
            params.append(operation)

        query += """
            GROUP BY provider_name, operation, file_size
            ORDER BY operation, file_size, avg_throughput DESC
        """

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_provider_stats(self, provider_name: str | None = None) -> list[dict[str, Any]]:
        """Get statistics for a provider or all providers."""
        cursor = self.conn.cursor()

        query = """
            SELECT
                provider_name,
                COUNT(DISTINCT run_id) as run_count,
                COUNT(*) as test_count,
                AVG(throughput_mbps) as avg_throughput,
                MAX(throughput_mbps) as max_throughput,
                AVG(ops_per_sec) as avg_iops,
                AVG(avg_latency_ms) as avg_latency,
                MIN(avg_latency_ms) as min_latency
            FROM results
        """
        params = []

        if provider_name:
            query += " WHERE provider_name = ?"
            params.append(provider_name)

        query += " GROUP BY provider_name ORDER BY avg_throughput DESC"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

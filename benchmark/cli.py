"""Command-line interface for benchmarking."""

import argparse
import sys
from datetime import datetime
from typing import List

from benchmark.benchmarks import ReadBenchmark, WriteBenchmark
from benchmark.comparison import BenchmarkComparison, ProviderResults
from benchmark.config import Config, ProviderConfig
from benchmark.database import BenchmarkDatabase
from benchmark.storage import LocalStorage, S3RequestsStorage


def get_storage(provider: ProviderConfig, config):
    """Get storage backend based on provider configuration."""
    if provider.type == "s3":
        return S3RequestsStorage(
            endpoint=provider.endpoint,
            access_key=provider.access_key,
            secret_key=provider.secret_key,
            bucket=provider.bucket,
            region=provider.region,
            verbose=True,
            max_retries=config.benchmark.max_retries,
            timeout=config.benchmark.timeout_seconds,
        )
    else:
        return LocalStorage(base_path=provider.base_path)


def run_benchmark_suite(
    storage,
    provider_name: str,
    prefix: str,
    test_sizes: List[tuple[int, int]],
    parallel_workers: int = 10,
    runs_per_test: int = 3,
    db: BenchmarkDatabase | None = None,
    run_id: int | None = None,
    provider_type: str = "s3",
):
    """Run complete benchmark suite for a single provider."""
    print(f"\n{'=' * 160}")
    print(f"BENCHMARKING: {provider_name}")
    print(f"Storage: {storage.name}")
    print(f"Running each test {runs_per_test} time(s) for accuracy")
    print("=" * 160)
    print(
        f"{'Operation':<10} | {'Size':>8} | {'Count':>6} | {'Throughput':>12} | "
        f"{'IOPS':>10} | {'Avg Latency':>12} | {'Variance':>12}"
    )
    print("=" * 160)

    write_bench = WriteBenchmark(storage, prefix)
    read_bench = ReadBenchmark(storage, prefix)
    results = []

    for file_size, file_count in test_sizes:
        # Sequential write (run multiple times)
        result = run_test_multiple_times(
            lambda: write_bench.run_sequential(file_size, file_count),
            runs_per_test,
            "WRITE",
        )
        print(result)
        results.append(result)
        if db and run_id:
            db.add_result(run_id, provider_name, provider_type, result)

        # Parallel write
        result = run_test_multiple_times(
            lambda: write_bench.run_parallel(file_size, file_count, parallel_workers),
            runs_per_test,
            "WRITE-P",
        )
        print(result)
        results.append(result)
        if db and run_id:
            db.add_result(run_id, provider_name, provider_type, result)

        # Sequential read
        result = run_test_multiple_times(
            lambda: read_bench.run_sequential(file_size, file_count),
            runs_per_test,
            "READ",
        )
        print(result)
        results.append(result)
        if db and run_id:
            db.add_result(run_id, provider_name, provider_type, result)

        # Parallel read
        result = run_test_multiple_times(
            lambda: read_bench.run_parallel(file_size, file_count, parallel_workers),
            runs_per_test,
            "READ-P",
        )
        print(result)
        results.append(result)
        if db and run_id:
            db.add_result(run_id, provider_name, provider_type, result)

    print("=" * 160)

    # Clean up test files
    if hasattr(storage, 'delete_prefix'):
        print(f"\nCleaning up test files with prefix: {prefix}/")
        deleted = storage.delete_prefix(f"{prefix}/")
        if deleted > 0:
            print(f"Deleted {deleted} test files")

    return results


def run_test_multiple_times(test_func, runs: int, operation_name: str):
    """Run a test multiple times and return averaged results."""
    from benchmark.benchmarks.base import BenchmarkResult

    if runs <= 0:
        runs = 1

    all_results = []
    for i in range(runs):
        if runs > 1:
            print(f"  [{operation_name} run {i+1}/{runs}]", end=" ", flush=True)
        result = test_func()
        all_results.append(result)
        if runs > 1:
            print(f"OK - {result.throughput_mbps:.2f} MB/s")

    # Calculate averages
    avg_throughput = sum(r.throughput_mbps for r in all_results) / len(all_results)
    avg_iops = sum(r.ops_per_sec for r in all_results) / len(all_results)
    avg_latency = sum(r.avg_latency_ms for r in all_results) / len(all_results)
    min_latency = min(r.min_latency_ms for r in all_results)
    max_latency = max(r.max_latency_ms for r in all_results)

    # Calculate variance (standard deviation of throughput as percentage)
    if len(all_results) > 1:
        throughputs = [r.throughput_mbps for r in all_results]
        mean = sum(throughputs) / len(throughputs)
        variance = sum((x - mean) ** 2 for x in throughputs) / len(throughputs)
        std_dev = variance ** 0.5
        variance_pct = (std_dev / mean * 100) if mean > 0 else 0
    else:
        variance_pct = 0

    # Use the first result as template and override with averages
    template = all_results[0]
    return BenchmarkResult(
        operation=template.operation,
        file_size=template.file_size,
        file_count=template.file_count,
        total_bytes=template.total_bytes,
        duration=sum(r.duration for r in all_results) / len(all_results),
        throughput_mbps=avg_throughput,
        ops_per_sec=avg_iops,
        avg_latency_ms=avg_latency,
        min_latency_ms=min_latency,
        max_latency_ms=max_latency,
        variance_pct=variance_pct,
        runs=runs,
    )


def cmd_run(args, config: Config):
    """Run benchmarks."""
    # Determine which providers to test
    if args.provider:
        providers = []
        for name in args.provider:
            provider = config.get_provider(name)
            if not provider:
                print(f"Error: Provider '{name}' not found in config", file=sys.stderr)
                sys.exit(1)
            providers.append(provider)
    else:
        providers = config.get_enabled_providers()

    if not providers:
        print("Error: No providers enabled", file=sys.stderr)
        sys.exit(1)

    # Validate providers
    for provider in providers:
        try:
            provider.validate()
        except ValueError as e:
            print(f"Configuration error for provider '{provider.name}': {e}", file=sys.stderr)
            sys.exit(1)

    # Define test sizes
    if args.quick:
        test_sizes = [
            (1024, 100),
            (10 * 1024, 50),
            (100 * 1024, 20),
        ]
        profile = "quick"
    elif args.full:
        test_sizes = [
            (1024, 100),
            (10 * 1024, 50),
            (100 * 1024, 20),
            (1024 * 1024, 10),
            (10 * 1024 * 1024, 5),
            (100 * 1024 * 1024, 2),
        ]
        profile = "full"
    else:
        test_sizes = [
            (1024, 100),
            (10 * 1024, 50),
            (100 * 1024, 20),
            (1024 * 1024, 10),
        ]
        profile = "default"

    workers = args.workers if args.workers else config.benchmark.default_workers
    prefix = args.prefix if args.prefix else config.benchmark.test_prefix
    runs_per_test = args.runs if hasattr(args, 'runs') and args.runs else config.benchmark.runs_per_test

    # Create database run
    db = BenchmarkDatabase()
    run_id = db.create_run(
        run_name=args.name,
        test_profile=profile,
        workers=workers,
        notes=args.notes,
    )

    print("\n" + "=" * 160)
    print("STORAGE BENCHMARK")
    print(f"Run ID: {run_id}")
    if args.name:
        print(f"Run Name: {args.name}")
    print(f"Profile: {profile}")
    print(f"Workers: {workers}")
    print(f"Runs per test: {runs_per_test} (results will be averaged)")
    print(f"Providers: {', '.join(p.name for p in providers)}")
    print("=" * 160)

    # Run benchmarks for each provider
    all_results = []
    for provider in providers:
        try:
            storage = get_storage(provider, config)
            results = run_benchmark_suite(
                storage,
                provider.name,
                prefix,
                test_sizes,
                workers,
                runs_per_test,
                db,
                run_id,
                provider.type,
            )
            all_results.append(ProviderResults(provider.name, results))
        except Exception as e:
            print(f"\nError benchmarking {provider.name}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    db.close()

    # Show comparison if multiple providers
    if len(all_results) > 1 and args.compare:
        comparison = BenchmarkComparison(all_results)
        comparison.print_summary()
        comparison.print_detailed_comparison()

    print(f"\nResults saved to database (run_id: {run_id})")


def cmd_list(args, config: Config):
    """List benchmark runs."""
    db = BenchmarkDatabase()
    runs = db.get_runs(limit=args.limit)
    db.close()

    if not runs:
        print("No benchmark runs found")
        return

    print("\n" + "=" * 120)
    print("BENCHMARK RUNS")
    print("=" * 120)
    print(
        f"{'ID':<6} | {'Timestamp':<20} | {'Name':<20} | {'Profile':<10} | "
        f"{'Workers':<8} | {'Notes':<30}"
    )
    print("=" * 120)

    for run in runs:
        run_name = run["run_name"] or "-"
        notes = run["notes"] or "-"
        print(
            f"{run['id']:<6} | {run['timestamp']:<20} | {run_name:<20} | "
            f"{run['test_profile']:<10} | {run['workers']:<8} | {notes:<30}"
        )

    print("=" * 120)


def cmd_show(args, config: Config):
    """Show results for a specific run."""
    db = BenchmarkDatabase()
    results = db.get_run_results(args.run_id)
    db.close()

    if not results:
        print(f"No results found for run {args.run_id}")
        return

    print("\n" + "=" * 160)
    print(f"BENCHMARK RESULTS - Run #{args.run_id}")
    print("=" * 160)
    print(
        f"{'Provider':<15} | {'Operation':<10} | {'Size':>8} | {'Count':>6} | "
        f"{'Throughput':>12} | {'IOPS':>10} | {'Avg Latency':>12}"
    )
    print("=" * 160)

    for result in results:
        size_str = format_size(result["file_size"])
        print(
            f"{result['provider_name']:<15} | {result['operation']:<10} | "
            f"{size_str:>8} | {result['file_count']:>6} | "
            f"{result['throughput_mbps']:>10.2f} MB/s | {result['ops_per_sec']:>10.2f} | "
            f"{result['avg_latency_ms']:>10.2f} ms"
        )

    print("=" * 160)


def cmd_compare(args, config: Config):
    """Compare providers or runs."""
    db = BenchmarkDatabase()

    # Get provider names to compare
    if args.providers:
        provider_names = args.providers
    else:
        # Get all providers that have results
        stats = db.get_provider_stats()
        provider_names = [s["provider_name"] for s in stats]

    if not provider_names:
        print("No data available for comparison")
        db.close()
        return

    # Get all results for these providers (from most recent runs)
    all_provider_results = []
    for provider_name in provider_names:
        # Get recent results for this provider
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM results
            WHERE provider_name = ?
            ORDER BY run_id DESC
            LIMIT 50
        """,
            (provider_name,),
        )
        results_data = cursor.fetchall()

        if results_data:
            # Convert to BenchmarkResult objects
            from benchmark.benchmarks.base import BenchmarkResult

            results = []
            for row in results_data:
                # Handle both old and new database schemas
                row_dict = dict(row)
                result = BenchmarkResult(
                    operation=row_dict["operation"],
                    file_size=row_dict["file_size"],
                    file_count=row_dict["file_count"],
                    total_bytes=row_dict["total_bytes"],
                    duration=row_dict["duration"],
                    throughput_mbps=row_dict["throughput_mbps"],
                    ops_per_sec=row_dict["ops_per_sec"],
                    avg_latency_ms=row_dict["avg_latency_ms"],
                    min_latency_ms=row_dict["min_latency_ms"],
                    max_latency_ms=row_dict["max_latency_ms"],
                    variance_pct=row_dict.get("variance_pct", 0.0),
                    runs=row_dict.get("runs", 1),
                )
                results.append(result)

            all_provider_results.append(ProviderResults(provider_name, results))

    db.close()

    if not all_provider_results:
        print("No results found for comparison")
        return

    # Use BenchmarkComparison for formatted output
    comparison = BenchmarkComparison(all_provider_results)
    comparison.print_summary()


def cmd_stats(args, config: Config):
    """Show statistics."""
    db = BenchmarkDatabase()
    stats = db.get_provider_stats(args.provider)
    db.close()

    if not stats:
        print("No statistics available")
        return

    print("\n" + "=" * 140)
    print("PROVIDER STATISTICS")
    print("=" * 140)
    print(
        f"{'Provider':<15} | {'Runs':>6} | {'Tests':>6} | {'Avg Throughput':>15} | "
        f"{'Max Throughput':>15} | {'Avg IOPS':>12} | {'Avg Latency':>12}"
    )
    print("=" * 140)

    for row in stats:
        print(
            f"{row['provider_name']:<15} | {row['run_count']:>6} | {row['test_count']:>6} | "
            f"{row['avg_throughput']:>13.2f} MB/s | {row['max_throughput']:>13.2f} MB/s | "
            f"{row['avg_iops']:>12.2f} | {row['avg_latency']:>10.2f} ms"
        )

    print("=" * 140)


def cmd_clean(args, config: Config):
    """Clean up test files."""
    # Determine which providers to clean
    if args.provider:
        provider = config.get_provider(args.provider)
        if not provider:
            print(f"Error: Provider '{args.provider}' not found in config", file=sys.stderr)
            sys.exit(1)
        providers = [provider]
    else:
        providers = config.get_enabled_providers()

    if not providers:
        print("Error: No providers enabled", file=sys.stderr)
        sys.exit(1)

    prefix = args.prefix if args.prefix else config.benchmark.test_prefix

    # Confirm before deleting unless --all flag is used
    if not args.all:
        provider_names = ', '.join(p.name for p in providers)
        response = input(
            f"\nClean test files with prefix '{prefix}/' from providers: {provider_names}?\n"
            f"This will permanently delete all matching files. Continue? [y/N]: "
        )
        if response.lower() not in ('y', 'yes'):
            print("Cancelled")
            return

    print("\n" + "=" * 80)
    print("CLEANING TEST FILES")
    print("=" * 80)

    total_deleted = 0
    for provider in providers:
        try:
            storage = get_storage(provider, config)
            if not hasattr(storage, 'delete_prefix'):
                print(f"{provider.name}: Cleanup not supported for this storage type")
                continue

            print(f"\n{provider.name}: Deleting files with prefix: {prefix}/")
            deleted = storage.delete_prefix(f"{prefix}/")
            print(f"{provider.name}: Deleted {deleted} test files")
            total_deleted += deleted
        except Exception as e:
            print(f"{provider.name}: Error during cleanup: {e}", file=sys.stderr)

    print("\n" + "=" * 80)
    print(f"Total files deleted: {total_deleted}")
    print("=" * 80)


def format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.0f}MB"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Benchmark S3-compatible storage performance across multiple providers"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run benchmarks
    run_parser = subparsers.add_parser("run", help="Run benchmarks")
    run_parser.add_argument(
        "--provider",
        "-p",
        action="append",
        help="Provider(s) to benchmark (default: all enabled)",
    )
    run_parser.add_argument("--name", "-n", help="Name for this benchmark run")
    run_parser.add_argument("--notes", help="Notes about this run")
    run_parser.add_argument("--prefix", help="Prefix for test files")
    run_parser.add_argument("--workers", "-w", type=int, help="Number of parallel workers")
    run_parser.add_argument(
        "--runs", "-r", type=int, help="Number of times to run each test (default: 3)"
    )
    run_parser.add_argument("--quick", action="store_true", help="Quick benchmark")
    run_parser.add_argument("--full", action="store_true", help="Full benchmark")
    run_parser.add_argument(
        "--compare",
        "-c",
        action="store_true",
        default=True,
        help="Show comparison after benchmarking multiple providers",
    )
    run_parser.add_argument(
        "--no-compare",
        dest="compare",
        action="store_false",
        help="Don't show comparison",
    )

    # List runs
    list_parser = subparsers.add_parser("list", help="List benchmark runs")
    list_parser.add_argument("--limit", "-l", type=int, default=20, help="Number of runs to show")

    # Show run results
    show_parser = subparsers.add_parser("show", help="Show results for a specific run")
    show_parser.add_argument("run_id", type=int, help="Run ID to show")

    # Compare providers
    compare_parser = subparsers.add_parser("compare", help="Compare provider performance")
    compare_parser.add_argument(
        "--providers", "-p", nargs="+", help="Providers to compare (default: all)"
    )

    # Show statistics
    stats_parser = subparsers.add_parser("stats", help="Show provider statistics")
    stats_parser.add_argument("--provider", "-p", help="Provider to show stats for (default: all)")

    # Clean up test files
    clean_parser = subparsers.add_parser("clean", help="Clean up benchmark test files")
    clean_parser.add_argument(
        "--provider", "-p", help="Provider to clean (default: all enabled)"
    )
    clean_parser.add_argument(
        "--prefix", help="Prefix of test files to clean (default: from config)"
    )
    clean_parser.add_argument(
        "--all", "-a", action="store_true", help="Clean all test files without confirmation"
    )

    args = parser.parse_args()

    # Default to run command if no command specified
    if not args.command:
        args.command = "run"
        args.provider = None
        args.name = None
        args.notes = None
        args.prefix = None
        args.workers = None
        args.quick = False
        args.full = False
        args.compare = True

    # Load configuration
    try:
        config = Config.from_file()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)

    # Execute command
    try:
        if args.command == "run":
            cmd_run(args, config)
        elif args.command == "list":
            cmd_list(args, config)
        elif args.command == "show":
            cmd_show(args, config)
        elif args.command == "compare":
            cmd_compare(args, config)
        elif args.command == "stats":
            cmd_stats(args, config)
        elif args.command == "clean":
            cmd_clean(args, config)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

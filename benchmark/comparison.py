"""Comparison and reporting for benchmark results."""

from dataclasses import dataclass
from typing import Sequence

from benchmark.benchmarks.base import BenchmarkResult
from benchmark.utils import get_missing_tests


@dataclass
class ProviderResults:
    """Results for a single provider."""

    provider_name: str
    results: list[BenchmarkResult]


class BenchmarkComparison:
    """Compare benchmark results across providers."""

    def __init__(self, provider_results: list[ProviderResults]):
        self.provider_results = provider_results

    def print_summary(self) -> None:
        """Print a summary comparison of all providers."""
        if not self.provider_results:
            return

        print("\n" + "=" * 160)
        print("PROVIDER PERFORMANCE COMPARISON")
        print("=" * 160)

        # Check for missing tests and warn user
        missing_tests = get_missing_tests(self.provider_results)
        if missing_tests:
            print("\nNOTE: Some providers are missing test results:")
            for (op_type, file_size), missing_providers in sorted(missing_tests.items()):
                size_str = self._format_size(file_size)
                providers_str = ", ".join(missing_providers)
                print(f"   * {op_type} @ {size_str}: {providers_str} not tested")
            print("\n   Run benchmarks on all providers to get complete comparison data.")
            print("=" * 160)

        # Group results by operation type and file size
        grouped: dict[tuple[str, int], dict[str, BenchmarkResult]] = {}

        for provider_result in self.provider_results:
            for result in provider_result.results:
                key = (result.operation, result.file_size)
                if key not in grouped:
                    grouped[key] = {}
                grouped[key][provider_result.provider_name] = result

        # Sort by operation type and file size
        sorted_keys = sorted(grouped.keys(), key=lambda x: (self._op_order(x[0]), x[1]))

        # Print each operation type with file sizes
        current_op = None
        for op_type, file_size in sorted_keys:
            # Get providers for this test
            providers = grouped[(op_type, file_size)]

            # Skip if only one provider has data (nothing to compare)
            if len(providers) < 2:
                continue

            # Print operation header when it changes
            if op_type != current_op:
                current_op = op_type
                print(f"\n{self._op_name(op_type)}")
                print("-" * 160)

            # Print file size subheader
            size_str = self._format_size(file_size)
            print(f"\n  File Size: {size_str}")
            print(
                f"  {'Provider':<13} | {'Throughput':>15} | {'IOPS':>12} | "
                f"{'Min/Max IOPS':>18} | {'Latency':>12} | {'vs Best':>12} | {'Winner':>6}"
            )
            print("  " + "-" * 152)

            # Sort by throughput
            sorted_providers = sorted(
                providers.items(), key=lambda x: x[1].throughput_mbps, reverse=True
            )
            best_throughput = sorted_providers[0][1].throughput_mbps

            for provider_name, result in sorted_providers:
                diff_pct = (
                    ((result.throughput_mbps - best_throughput) / best_throughput * 100)
                    if best_throughput > 0
                    else 0
                )
                winner_mark = "BEST" if diff_pct == 0 else ""

                if diff_pct == 0:
                    diff_str = "baseline"
                else:
                    diff_str = f"{diff_pct:+.1f}%"

                iops_range = f"{result.ops_per_sec:.0f}"

                print(
                    f"  {provider_name:<13} | {result.throughput_mbps:>13.2f} MB/s | "
                    f"{result.ops_per_sec:>12.2f} | {iops_range:>18} | "
                    f"{result.avg_latency_ms:>10.2f} ms | {diff_str:>12} | {winner_mark:>6}"
                )

        # Print overall summary
        print("\n" + "=" * 160)
        self._print_overall_summary(grouped)
        print("=" * 160)

    def _print_overall_summary(self, grouped: dict) -> None:
        """Print overall performance summary."""
        # Calculate aggregate stats per provider per operation type
        provider_stats = {}

        for provider_result in self.provider_results:
            stats = {}
            for op_type in ["WRITE", "WRITE-P", "READ", "READ-P"]:
                op_results = [r for r in provider_result.results if r.operation == op_type]
                if op_results:
                    throughput = [r.throughput_mbps for r in op_results]
                    iops = [r.ops_per_sec for r in op_results]

                    stats[op_type] = {
                        "throughput_avg": sum(throughput) / len(throughput),
                        "iops_avg": sum(iops) / len(iops),
                        "count": len(op_results),
                    }

            provider_stats[provider_result.provider_name] = stats

        print("\nOVERALL PERFORMANCE SUMMARY")
        print("-" * 160)
        print(
            f"{'Provider':<15} | {'Seq Write':>15} | {'Par Write':>15} | "
            f"{'Seq Read':>15} | {'Par Read':>15} | {'Score':>10} | {'Winner':>6}"
        )
        print("-" * 160)

        # Calculate overall scores
        overall_scores = {}
        best_values = {}

        # Find best values for normalization
        for op_type in ["WRITE", "WRITE-P", "READ", "READ-P"]:
            best_throughput = 0
            for stats in provider_stats.values():
                if op_type in stats:
                    best_throughput = max(best_throughput, stats[op_type]["throughput_avg"])
            if best_throughput > 0:
                best_values[op_type] = best_throughput

        # Calculate scores
        for provider_name, stats in provider_stats.items():
            score = 0
            op_count = 0

            for op_type in ["WRITE", "WRITE-P", "READ", "READ-P"]:
                if op_type in stats and op_type in best_values:
                    score += (stats[op_type]["throughput_avg"] / best_values[op_type]) * 25
                    op_count += 1

            overall_scores[provider_name] = score if op_count > 0 else 0

        # Print sorted by score
        sorted_overall = sorted(overall_scores.items(), key=lambda x: x[1], reverse=True)
        best_score = sorted_overall[0][1] if sorted_overall else 0

        for provider_name, score in sorted_overall:
            stats = provider_stats[provider_name]
            winner_mark = "BEST" if score == best_score else ""

            seq_write = f"{stats['WRITE']['throughput_avg']:.1f}" if "WRITE" in stats else "N/A"
            par_write = f"{stats['WRITE-P']['throughput_avg']:.1f}" if "WRITE-P" in stats else "N/A"
            seq_read = f"{stats['READ']['throughput_avg']:.1f}" if "READ" in stats else "N/A"
            par_read = f"{stats['READ-P']['throughput_avg']:.1f}" if "READ-P" in stats else "N/A"

            print(
                f"{provider_name:<15} | {seq_write:>13} MB/s | {par_write:>13} MB/s | "
                f"{seq_read:>13} MB/s | {par_read:>13} MB/s | {score:>9.1f}/100 | {winner_mark:>6}"
            )

        if sorted_overall:
            winner = sorted_overall[0]
            print(f"\nOVERALL WINNER: {winner[0].upper()} (Score: {winner[1]:.1f}/100)")

            # Print insights
            print("\nPERFORMANCE INSIGHTS:")
            self._print_insights(provider_stats, sorted_overall)

    def _print_insights(self, provider_stats: dict, sorted_overall: list) -> None:
        """Print performance insights."""
        if len(sorted_overall) < 2:
            return

        # Find where each provider excels
        for provider_name, stats in provider_stats.items():
            best_ops = []
            for op_type in ["WRITE", "WRITE-P", "READ", "READ-P"]:
                if op_type in stats:
                    throughput = stats[op_type]["throughput_avg"]
                    # Check if best for this operation
                    is_best = True
                    for other_name, other_stats in provider_stats.items():
                        if other_name != provider_name and op_type in other_stats:
                            if other_stats[op_type]["throughput_avg"] > throughput:
                                is_best = False
                                break
                    if is_best:
                        best_ops.append(self._op_name(op_type))

            if best_ops:
                ops_str = ", ".join(best_ops)
                print(f"   * {provider_name} excels at: {ops_str}")

    def print_detailed_comparison(self) -> None:
        """Print detailed comparison - just calls print_summary since we now show all details."""
        self.print_summary()

    @staticmethod
    def _op_order(op_type: str) -> int:
        """Get sort order for operation type."""
        order = {"WRITE": 0, "WRITE-P": 1, "READ": 2, "READ-P": 3}
        return order.get(op_type, 99)

    @staticmethod
    def _op_name(op_type: str) -> str:
        """Get display name for operation type."""
        names = {
            "WRITE": "SEQUENTIAL WRITE",
            "WRITE-P": "PARALLEL WRITE",
            "READ": "SEQUENTIAL READ",
            "READ-P": "PARALLEL READ",
        }
        return names.get(op_type, op_type)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.0f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.0f}MB"

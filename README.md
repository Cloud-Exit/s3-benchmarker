# S3 Benchmarker

A comprehensive benchmarking tool for testing and comparing read/write performance across multiple S3-compatible storage providers (Storadera, Wasabi, MinIO, Cloudflare R2, AWS S3, etc.) and local filesystems. Results are stored in a SQLite database for analysis and comparison.

## Features

- **Multiple provider support**: Benchmark multiple S3-compatible providers simultaneously
- **Configuration-based**: Easy TOML configuration for managing providers
- **Sequential and parallel I/O testing**: Test both sequential and concurrent operations
- **Multiple file sizes**: Test with various file sizes from 1KB to 100MB
- **Comprehensive metrics**:
  - Throughput (MB/s)
  - IOPS (operations per second)
  - Latency (average, min, max)
- **SQLite database**: Store all results for historical analysis
- **Comparison tools**: Compare performance across providers and runs
- **Clean architecture**: Proper class structure with protocols and abstractions

## Installation

1. Clone or extract the benchmark tool
2. Install (creates virtual environment automatically):

```bash
make install
```

3. Setup configuration:

```bash
make setup
# or manually:
cp config.toml.example config.toml
```

4. Edit `config.toml` with your provider credentials:

```toml
[benchmark]
test_prefix = "benchmark-test"
default_workers = 10

[[providers]]
name = "storadera"
type = "s3"
enabled = true
endpoint = "https://s3.eu-central-1.storadera.com"
access_key = "your_access_key"
secret_key = "your_secret_key"
bucket = "your_bucket"
region = "eu-central-1"

[[providers]]
name = "local"
type = "local"
enabled = true
base_path = "./benchmark_data/local"
```

## Quick Start

```bash
# Install
make install

# Setup config
make setup
# Edit config.toml with your credentials

# Run benchmarks
make run              # Default benchmark on all enabled providers
make run-quick        # Quick test (small files only)
make run-full         # Full test (including large files)
```

## Usage

### Running Benchmarks

```bash
# Run on all enabled providers
make run

# Run on specific provider(s)
python main.py run --provider storadera
python main.py run --provider storadera --provider local

# Run with options
python main.py run --quick                    # Quick test
python main.py run --full                     # Full test
python main.py run --name "My Test" --notes "Testing after upgrade"
python main.py run --workers 20               # Use 20 parallel workers
```

### Viewing Results

```bash
# List recent runs
make list
# or: python main.py list

# Show specific run
make show RUN=1
# or: python main.py show 1

# Compare providers (shows all file sizes with winners and percentages)
make compare
# or: python main.py compare
# or: python main.py compare --providers storadera wasabi

# Show statistics
make stats
# or: python main.py stats
# or: python main.py stats --provider storadera
```

### Advanced Usage

With venv activated:

```bash
source venv/bin/activate

# Run with custom settings
python main.py run \
  --provider storadera \
  --name "Production Test" \
  --notes "Testing new server" \
  --workers 50 \
  --full

# Compare specific providers
python main.py compare --providers storadera cloudflare-r2 aws-s3

# Show stats for specific provider
python main.py stats --provider storadera
```

## Configuration

The `config.toml` file supports multiple providers:

```toml
[benchmark]
test_prefix = "benchmark-test"
default_workers = 10
cleanup_after = true

# Storadera
[[providers]]
name = "storadera"
type = "s3"
enabled = true
endpoint = "https://s3.eu-central-1.storadera.com"
access_key = "..."
secret_key = "..."
bucket = "benchmark"
region = "eu-central-1"

# Local filesystem
[[providers]]
name = "local"
type = "local"
enabled = true
base_path = "./benchmark_data/local"

# MinIO
[[providers]]
name = "minio"
type = "s3"
enabled = false
endpoint = "http://localhost:9000"
access_key = "minioadmin"
secret_key = "minioadmin"
bucket = "benchmark"
region = "us-east-1"

# Cloudflare R2
[[providers]]
name = "cloudflare-r2"
type = "s3"
enabled = false
endpoint = "https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com"
access_key = "..."
secret_key = "..."
bucket = "benchmark"
region = "auto"
```

## Project Structure

```
.
├── README.md                  # This file
├── Makefile                   # Build and run commands
├── pyproject.toml            # Python package configuration
├── config.toml               # Configuration (gitignored)
├── config.toml.example       # Example configuration
├── main.py                   # Entry point
├── venv/                     # Virtual environment
├── benchmark_results.db      # SQLite database (gitignored)
└── benchmark/
    ├── __init__.py
    ├── config.py             # Configuration management
    ├── cli.py                # Command-line interface
    ├── database.py           # SQLite database management
    ├── comparison.py         # Comparison and reporting
    ├── storage/              # Storage backend implementations
    │   ├── __init__.py
    │   ├── base.py          # Storage protocol definition
    │   ├── s3.py            # S3 implementation (uses requests)
    │   └── local.py         # Local filesystem implementation
    └── benchmarks/           # Benchmark implementations
        ├── __init__.py
        ├── base.py          # Base benchmark class
        ├── write_benchmark.py
        └── read_benchmark.py
```

## Commands

### Benchmark Commands

| Command | Description |
|---------|-------------|
| `make run` | Run default benchmark on all enabled providers |
| `make run-quick` | Quick benchmark (1KB-100KB files) |
| `make run-full` | Full benchmark (1KB-100MB files) |
| `python main.py run -p <name>` | Run on specific provider |
| `python main.py run --name "Test" --notes "..."` | Run with metadata |

### View Commands

| Command | Description |
|---------|-------------|
| `make list` | List recent benchmark runs |
| `make show RUN=<id>` | Show results for specific run |
| `make compare` | Compare all providers |
| `make stats` | Show provider statistics |

### Maintenance Commands

| Command | Description |
|---------|-------------|
| `make clean` | Clean benchmark data and cache |
| `make clean-all` | Clean everything including venv and database |

## Example Output

### Running Benchmark

```
================================================================================
STORAGE BENCHMARK
Run ID: 1
Profile: default
Workers: 10
Providers: storadera, local
================================================================================

================================================================================
BENCHMARKING: storadera
Storage: S3 bucket 'benchmark' at https://s3.eu-central-1.storadera.com
================================================================================
Operation  |     Size | Count |   Throughput |       IOPS | Avg Latency |
================================================================================
WRITE      |     1KB  |   100 |     2.45 MB/s |      25.12 |    39.82 ms |
WRITE-P    |     1KB  |   100 |    15.67 MB/s |     160.45 |    62.31 ms |
READ       |     1KB  |   100 |     3.21 MB/s |      32.87 |    30.42 ms |
READ-P     |     1KB  |   100 |    21.34 MB/s |     218.56 |    45.78 ms |
```

### Comparison

```
================================================================================================
PROVIDER PERFORMANCE COMPARISON
================================================================================================

📝 SEQUENTIAL WRITE
------------------------------------------------------------------------------------------------

  📁 File Size: 1KB
  Provider      |      Throughput |         IOPS |         Min/Max IOPS | Latency      |      vs Best |
  ----------------------------------------------------------------------------------------
  wasabi        |       2.45 MB/s |        25.12 |                   25 |    39.82 ms  |     baseline | 🏆
  storadera     |       2.15 MB/s |        22.03 |                   22 |    45.41 ms  |       -12.2% |

  📁 File Size: 10KB
  Provider      |      Throughput |         IOPS |         Min/Max IOPS | Latency      |      vs Best |
  ----------------------------------------------------------------------------------------
  wasabi        |       8.92 MB/s |        91.34 |                   91 |    43.67 ms  |     baseline | 🏆
  storadera     |       7.56 MB/s |        77.45 |                   77 |    51.52 ms  |       -15.2% |

  📁 File Size: 100KB
  Provider      |      Throughput |         IOPS |         Min/Max IOPS | Latency      |      vs Best |
  ----------------------------------------------------------------------------------------
  storadera     |      34.21 MB/s |       350.31 |                  350 |    28.55 ms  |     baseline | 🏆
  wasabi        |      31.45 MB/s |       322.05 |                  322 |    31.06 ms  |        -8.1% |

⚡ PARALLEL WRITE
------------------------------------------------------------------------------------------------

  📁 File Size: 1KB
  Provider      |      Throughput |         IOPS |         Min/Max IOPS | Latency      |      vs Best |
  ----------------------------------------------------------------------------------------
  wasabi        |      15.67 MB/s |       160.45 |                  160 |    62.31 ms  |     baseline | 🏆
  storadera     |      14.23 MB/s |       145.67 |                  145 |    68.72 ms  |        -9.2% |

  ... (more file sizes)

================================================================================================
📊 OVERALL PERFORMANCE SUMMARY
------------------------------------------------------------------------------------------------
Provider        |      Seq Write |      Par Write |       Seq Read |       Par Read |      Score |
------------------------------------------------------------------------------------------------
wasabi          |       15.7 MB/s |       42.2 MB/s |       18.9 MB/s |       48.2 MB/s |   92.3/100 | 🏆
storadera       |       12.5 MB/s |       45.2 MB/s |       16.3 MB/s |       52.7 MB/s |   89.7/100 |

🏆 OVERALL WINNER: WASABI (Score: 92.3/100)

💡 PERFORMANCE INSIGHTS:
   • wasabi excels at: Sequential Write, Sequential Read
   • storadera excels at: Parallel Write, Parallel Read
```

## Benchmark Profiles

### Quick (`--quick`)
- 1KB x 100 files
- 10KB x 50 files
- 100KB x 20 files

### Default (no flag)
- 1KB x 100 files
- 10KB x 50 files
- 100KB x 20 files
- 1MB x 10 files

### Full (`--full`)
- 1KB x 100 files
- 10KB x 50 files
- 100KB x 20 files
- 1MB x 10 files
- 10MB x 5 files
- 100MB x 2 files

## Database

All benchmark results are stored in `benchmark_results.db` (SQLite). The database contains:

- **benchmark_runs**: Metadata about each benchmark run
- **results**: Individual test results with all metrics

You can query the database directly or use the built-in commands:

```bash
# View with sqlite3
sqlite3 benchmark_results.db "SELECT * FROM benchmark_runs ORDER BY timestamp DESC LIMIT 5"

# Or use the CLI
python main.py list
python main.py show 1
python main.py compare
python main.py stats
```

## Compatibility

- **Python**: 3.10+
- **Storage**: Any S3-compatible service
  - Storadera
  - AWS S3
  - MinIO
  - Cloudflare R2
  - Backblaze B2
  - Any other S3-compatible service
  - Local filesystem

## Implementation Notes

### S3 Storage

The S3 implementation uses `requests` with `AWS4Auth` instead of `boto3` for better compatibility with various S3-compatible providers like Storadera. This approach:

- Works reliably with Storadera and other S3-compatible services
- Avoids checksum calculation issues in newer boto3 versions
- Uses path-style addressing (required by most S3-compatible services)
- Handles redirects properly
- Provides clear error messages

### Test Data

Test data is generated using a repeating pattern that compresses poorly, simulating real-world data. This ensures benchmarks reflect actual performance rather than optimized compression scenarios.

### Database Schema

```sql
-- Benchmark runs
CREATE TABLE benchmark_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    run_name TEXT,
    test_profile TEXT,
    workers INTEGER,
    notes TEXT
);

-- Results
CREATE TABLE results (
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
    FOREIGN KEY (run_id) REFERENCES benchmark_runs (id)
);
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions welcome! Please ensure code follows the existing structure and includes proper type hints.

# S3 Benchmarker

S3 Benchmarker compares read/write performance across S3-compatible providers and local filesystem backends. It runs sequential and parallel workloads, stores results in SQLite, and includes built-in reporting for comparisons and trends.

## Current State

- Provider backends: `s3` and `local`
- Operations: `WRITE`, `WRITE-P`, `READ`, `READ-P`
- Benchmark profiles: `quick`, `default`, `full`
- Each test is repeated (`runs_per_test`, default `3`) and averaged; variance is recorded
- Results are persisted in `benchmark_results.db` with automatic schema migration
- Test files are cleaned up by prefix after benchmark runs, with a dedicated `clean` command
- No automated test suite yet (`make test` currently prints a placeholder)

## Requirements

- Python `3.10+`
- Access to one or more S3-compatible buckets (or local filesystem paths)

## Install

```bash
make install
make setup
# edit config.toml
```

This creates `venv/`, installs the package in editable mode, and copies `config.toml` from `config.toml.example` (if missing).

## Configuration

Example `config.toml`:

```toml
[benchmark]
test_prefix = "benchmark-test"
default_workers = 10
cleanup_after = true
runs_per_test = 3
max_retries = 5
timeout_seconds = 300

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

## Usage

### Run benchmarks

```bash
# all enabled providers
make run

# single provider
make run PROVIDER=storadera
python main.py run --provider storadera

# profiles
make run-quick
make run-full

# custom options
python main.py run --workers 20 --runs 5 --name "baseline" --notes "after changes"
python main.py run --no-compare
```

### Inspect results

```bash
make list
make show RUN=1
make compare
make stats

# direct CLI equivalents
python main.py list
python main.py show 1
python main.py compare --providers storadera local
python main.py stats --provider storadera
```

### Cleanup

```bash
# remove benchmark objects/files for all enabled providers
make clean-data

# CLI (interactive confirm unless --all)
python main.py clean --all
python main.py clean --provider storadera --prefix benchmark-test --all
```

## Benchmark Profiles

- `quick`: `1KB x 100`, `10KB x 50`, `100KB x 20`
- `default`: quick + `1MB x 10`
- `full`: default + `10MB x 5`, `100MB x 2`

## Database

Results are stored in `benchmark_results.db`:

- `benchmark_runs`: run metadata (`timestamp`, profile, workers, notes)
- `results`: per-test metrics (throughput, IOPS, latency, variance, runs)

Quick query example:

```bash
sqlite3 benchmark_results.db "SELECT id, timestamp, run_name, test_profile FROM benchmark_runs ORDER BY id DESC LIMIT 10;"
```

## Notes

- S3 backend uses `requests` + `requests-aws4auth` (not `boto3`) for broad S3-compatible support.
- Installed entrypoints: `s3-benchmark` and `s3-benchmarker`.

## License

MIT — see `LICENSE`.

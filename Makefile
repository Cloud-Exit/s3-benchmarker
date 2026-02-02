.PHONY: help venv install install-dev setup test clean clean-data clean-all
.PHONY: run run-quick run-full list show compare stats

VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

# Default target
help:
	@echo "S3 Benchmarker"
	@echo ""
	@echo "Setup:"
	@echo "  make venv            - Create virtual environment"
	@echo "  make install         - Create venv and install package"
	@echo "  make install-dev     - Install with dev dependencies"
	@echo "  make setup           - Setup config.toml from example"
	@echo ""
	@echo "Running Benchmarks:"
	@echo "  make run             - Run default benchmark on all enabled providers"
	@echo "  make run-quick       - Run quick benchmark (small files)"
	@echo "  make run-full        - Run full benchmark (including large files)"
	@echo ""
	@echo "Viewing Results:"
	@echo "  make list            - List recent benchmark runs"
	@echo "  make show RUN=<id>   - Show results for a specific run"
	@echo "  make compare         - Compare providers (all file sizes, clear winners)"
	@echo "  make stats           - Show provider statistics"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean-data      - Clean up test files from storage providers"
	@echo "  make clean           - Clean up local cache and __pycache__"
	@echo "  make clean-all       - Clean everything including venv and database"
	@echo "  make test            - Run tests (if available)"

# Create virtual environment
venv:
	python -m venv $(VENV)
	@echo ""
	@echo "Virtual environment created at: $(VENV)/"
	@echo "Activate with: source $(VENV)/bin/activate"

# Install dependencies
install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -e .
	@echo ""
	@echo "Installation complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy config.toml.example to config.toml"
	@echo "  2. Edit config.toml with your provider credentials"
	@echo "  3. Run: make run"

# Install with dev dependencies
install-dev: venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

# Setup environment
setup:
	@if [ ! -f config.toml ]; then \
		cp config.toml.example config.toml; \
		echo "Created config.toml. Please edit it with your credentials."; \
	else \
		echo "config.toml already exists."; \
	fi

# Run default benchmark
run: venv
	@if [ ! -f $(PYTHON) ]; then \
		echo "Error: Virtual environment not found. Run 'make install' first."; \
		exit 1; \
	fi
	$(PYTHON) main.py run

# Run quick benchmark
run-quick: venv
	@if [ ! -f $(PYTHON) ]; then \
		echo "Error: Virtual environment not found. Run 'make install' first."; \
		exit 1; \
	fi
	$(PYTHON) main.py run --quick

# Run full benchmark
run-full: venv
	@if [ ! -f $(PYTHON) ]; then \
		echo "Error: Virtual environment not found. Run 'make install' first."; \
		exit 1; \
	fi
	$(PYTHON) main.py run --full

# List benchmark runs
list: venv
	$(PYTHON) main.py list

# Show specific run (usage: make show RUN=1)
show: venv
	@if [ -z "$(RUN)" ]; then \
		echo "Error: Please specify RUN=<id>"; \
		echo "Example: make show RUN=1"; \
		exit 1; \
	fi
	$(PYTHON) main.py show $(RUN)

# Compare providers (shows all file sizes tested)
compare: venv
	$(PYTHON) main.py compare

# Show statistics
stats: venv
	$(PYTHON) main.py stats

# Clean up test files from storage providers
clean-data: venv
	$(PYTHON) main.py clean --all

# Clean up local cache
clean:
	rm -rf benchmark_data/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Clean everything including venv and database
clean-all: clean
	rm -rf $(VENV)
	rm -rf *.egg-info
	rm -f benchmark_results.db
	rm -f benchmark_results.db-journal

# Run tests (placeholder for future implementation)
test:
	@echo "No tests configured yet"

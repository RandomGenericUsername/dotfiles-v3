.PHONY: test test-all lint format format-check check build clean capture-fixtures

test:
	@uv run pytest tests/ -v

test-all: test
	@echo "All tests complete."

check: lint format-check test

format-check:
	@uv run ruff format --check src/

lint:
	@uv run ruff check src/

format:
	@uv run ruff format src/

capture-fixtures:
	@uv run python tests/conformance/capture.py

build:
	@uv build

clean:
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist/ build/ *.whl 2>/dev/null || true

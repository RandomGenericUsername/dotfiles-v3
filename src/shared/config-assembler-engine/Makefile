.PHONY: test lint format check build clean

test:
	@uv run pytest tests/ -v

lint:
	@uv run ruff check src/

format:
	@uv run ruff format src/

check: lint

build:
	@uv build

clean:
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist/ build/ *.whl 2>/dev/null || true

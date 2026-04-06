.PHONY: dev api ui build test lint clean install

# ── Development ──────────────────────────────────────────────────────────────

dev: ## Start backend + frontend in parallel
	@echo "Starting API server and UI dev server..."
	@trap 'kill 0' EXIT; \
		uv run tesla serve --port 8080 --no-open & \
		npm --prefix ui run dev & \
		wait

api: ## Start backend API only
	uv run tesla serve --port 8080

ui: ## Start frontend dev server only (with proxy to backend)
	npm --prefix ui run dev

# ── Build ────────────────────────────────────────────────────────────────────

build: ## Build UI into the Python package (src/tesla_cli/api/ui_dist/)
	npm --prefix ui run build

install: ## Install all dependencies (Python + Node)
	uv sync
	npm --prefix ui install

# ── Quality ──────────────────────────────────────────────────────────────────

test: ## Run Python test suite
	uv run pytest tests/ -m "not integration" -q

test-all: ## Run all tests including integration
	uv run pytest tests/ -q

lint: ## Lint Python code
	uv run ruff check src/ tests/

lint-fix: ## Auto-fix lint issues
	uv run ruff check --fix src/ tests/

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts
	rm -rf src/tesla_cli/api/ui_dist/*
	rm -rf ui/node_modules/.vite

# ── Docker ───────────────────────────────────────────────────────────────────

docker-build: ## Build Docker images
	docker compose build

docker-up: ## Start containers in background
	docker compose up -d

docker-down: ## Stop and remove containers
	docker compose down

docker-full: ## Start full stack (with extras)
	docker compose -f docker-compose.full.yml up -d

# ── Coverage ─────────────────────────────────────────────────────────────────

coverage: ## Run tests with HTML coverage report
	uv run pytest --cov=tesla_cli --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# ── Production ───────────────────────────────────────────────────────────────

serve: build ## Build UI and start production server
	uv run tesla serve --port 8080

# ── Help ─────────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help

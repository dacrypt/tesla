# Stage 1: Build UI
FROM node:20-alpine AS ui-build
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# Stage 2: Python app
FROM python:3.12-slim
WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install with serve extra
RUN uv sync --extra serve --extra fleet --extra teslaMate --extra pdf --no-dev

# Copy built UI into the location the API serves from
COPY --from=ui-build /app/ui/dist src/tesla_cli/api/ui_dist/

# Expose API port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import httpx; httpx.get('http://localhost:8080/api/health').raise_for_status()"

# Run the API server (serve_ui flag picks up ui_dist/ automatically)
CMD ["uv", "run", "tesla", "serve", "--host", "0.0.0.0", "--port", "8080", "--no-open", "--serve-ui"]

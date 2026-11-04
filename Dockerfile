# Stage 1: Build UI
FROM node:20-alpine AS ui-build
WORKDIR /app/ui
COPY ui/package*.json ./
# Cypress (e2e only) is not needed to build the bundle
RUN CYPRESS_INSTALL_BINARY=0 npm ci
COPY ui/ ./
# vite.config.ts writes to ../src/tesla_cli/api/ui_dist
RUN npm run build

# Stage 2: Python app
FROM python:3.12-slim

# Pinned uv (never :latest — reproducible builds)
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

# Unprivileged runtime user; config + keys live in its home directory
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin tesla
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

# Install with serve extra
RUN uv sync --frozen --extra serve --extra fleet --extra teslaMate --extra pdf --no-dev

# Copy freshly built UI into the location the API serves from
COPY --from=ui-build /app/src/tesla_cli/api/ui_dist src/tesla_cli/api/ui_dist/

RUN mkdir -p /home/tesla/.tesla-cli && chown -R tesla:tesla /home/tesla/.tesla-cli
# No system keyring in a container: OAuth tokens go to an AES-256-GCM encrypted
# file in the config volume. Mount a Docker secret and point
# TESLA_CLI_MASTER_KEY_FILE at it to keep the key out of that volume.
ENV PATH="/app/.venv/bin:${PATH}" \
    HOME=/home/tesla \
    PYTHONUNBUFFERED=1 \
    TESLA_CLI_TOKEN_STORE=file
USER tesla

EXPOSE 8080

# /api/health is the only unauthenticated /api endpoint
HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import httpx; httpx.get('http://127.0.0.1:8080/api/health').raise_for_status()"

# Binding 0.0.0.0 inside the container: `tesla serve` auto-generates an API key
# on first start (printed in the logs; show again with `tesla serve api-key`).
CMD ["tesla", "serve", "--host", "0.0.0.0", "--port", "8080", "--no-open", "--serve-ui"]

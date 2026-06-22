FROM python:3.12-slim

# Grab the uv/uvx binaries from Astral's official image instead of installing via pip/curl
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Pre-compile .pyc files for faster startup; copy instead of hardlink since
# uv's cache hardlinks don't survive across Docker layers
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies before copying source so this layer is cached
# as long as pyproject.toml/uv.lock don't change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now install the project itself on top of the cached dependency layer
COPY src ./src
RUN uv sync --frozen --no-dev

# Put the venv's console scripts (e.g. bundesrag) on PATH
ENV PATH="/app/.venv/bin:$PATH"

# PDFs and the Chroma store live here; back it with a host volume to persist data
VOLUME ["/app/data"]

# Run the CLI directly; arguments to `docker run <image> ...` are forwarded to it
ENTRYPOINT ["bundesrag"]
CMD ["--help"]

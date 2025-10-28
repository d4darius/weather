FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH"

# Set the working directory
WORKDIR /app

# Install system deps and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential && rm -rf /var/lib/apt/lists/*

# Install uv CLI
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy project into image
COPY . /app

# Remove any virtualenv that may have been copied from the host
# Create a reproducible virtualenv, ensure pip exists, then install runtime deps.
# This guarantees the image contains pip and required packages even if the host
# later bind-mounts /app (or when running in CI).
RUN rm -rf .venv && \
    python3 -m venv .venv && \
    /app/.venv/bin/python -m ensurepip --upgrade || true && \
    /app/.venv/bin/python -m pip install --upgrade pip setuptools wheel && \
    /app/.venv/bin/python -m pip install "mcp[cli]" httpx

# Expose the port the app runs on
EXPOSE 10000

# Command to run the server using uv
CMD ["uv", "run", "src/weather.py"]


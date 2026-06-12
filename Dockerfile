FROM python:3.12-slim

# System dependencies + ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy project metadata and install dependencies first (layer cache)
COPY pyproject.toml README.md ./
COPY src/ src/
COPY frontend/ frontend/
COPY data/ data/
COPY scripts/ scripts/

RUN uv pip install --system --no-cache -e .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "scoutfootball.api_server:app", "--host", "0.0.0.0", "--port", "8000"]

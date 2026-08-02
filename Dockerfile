ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}
ARG INSTALL_SYSTEM_PACKAGES=1

USER root

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    SCOUTFOOTBALL_DATA_ROOT=/app/data \
    SCOUTFOOTBALL_CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

# Runtime dependencies. ffmpeg enables optional tactical-board MP4 export.
RUN if [ "$INSTALL_SYSTEM_PACKAGES" = "1" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends ffmpeg ca-certificates && \
        rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app

# Keep dependency installation independent from application source changes so
# a normal code fix does not redownload the complete Python stack.
COPY pyproject.toml README.md ./

RUN python -m pip install --no-cache-dir --retries 10 --timeout 120 --upgrade pip && \
    python -c "import subprocess,sys,tomllib; deps=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; subprocess.check_call([sys.executable,'-m','pip','install','--no-cache-dir','--retries','10','--timeout','120','setuptools>=80.0',*deps])"

COPY src/ src/

RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation -e .

# Copy runtime assets after dependencies so data/frontend changes do not
# invalidate the Python dependency layer.
COPY frontend/ frontend/
COPY data/ data/

RUN \
    mkdir -p /app/data/reports/tactical_exports /app/data/logs && \
    groupadd --system scoutfootball && \
    useradd --system --gid scoutfootball --home /app --shell /usr/sbin/nologin scoutfootball && \
    chown -R scoutfootball:scoutfootball /app

USER scoutfootball

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

CMD ["python", "-m", "scoutfootball", "serve", "--host", "0.0.0.0", "--port", "8000"]

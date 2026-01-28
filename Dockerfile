# Sentinel - Portfolio Management System
# Optimized for ARM64 (Arduino UNO Q / Raspberry Pi)

FROM python:3.13-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY pyproject.toml .

# Install Python dependencies
# Install in stages to manage memory on constrained devices
RUN pip install --no-cache-dir \
    numpy>=2.0.0 \
    pandas>=2.2.0 \
    scipy>=1.14.0

RUN pip install --no-cache-dir \
    scikit-learn>=1.3.0 \
    xgboost>=2.0.0

RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    uvicorn>=0.32.0 \
    aiosqlite>=0.20.0 \
    python-dotenv>=1.0.0 \
    PyWavelets>=1.7.0 \
    hmmlearn>=0.3.0 \
    ta>=0.11.0

RUN pip install --no-cache-dir \
    tradernet-sdk>=2.0.0 \
    skfolio>=0.1.0

# Copy application code
COPY sentinel/ ./sentinel/
COPY web/ ./web/

# Create data directories
RUN mkdir -p data/ml_models

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "sentinel.app:app", "--host", "0.0.0.0", "--port", "8000"]

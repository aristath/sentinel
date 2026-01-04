FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

# Non-root user for security
RUN useradd -m -u 1000 serviceuser && chown -R serviceuser:serviceuser /app
USER serviceuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import requests; requests.get('http://localhost:${PORT:-9001}/health').raise_for_status()"

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9001"]

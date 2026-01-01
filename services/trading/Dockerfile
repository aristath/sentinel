# utrading Service Dockerfile

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/trading/requirements.txt /app/services/trading/
COPY contracts /app/contracts/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/services/trading/requirements.txt
RUN pip install --no-cache-dir -e /app/contracts/

# Copy application code
COPY app /app/app/
COPY services/trading /app/services/trading/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose HTTP port
EXPOSE 8003

# Run the service
CMD ["python", "-m", "services.trading.main"]

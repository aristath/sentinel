# uscoring Service Dockerfile

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/scoring/requirements.txt /app/services/scoring/
COPY contracts /app/contracts/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/services/scoring/requirements.txt
RUN pip install --no-cache-dir -e /app/contracts/

# Copy application code
COPY app /app/app/
COPY services/scoring /app/services/scoring/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose HTTP port
EXPOSE 8004

# Run the service
CMD ["python", "-m", "services.scoring.main"]

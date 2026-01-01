# uuniverse Service Dockerfile

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/universe/requirements.txt /app/services/universe/
COPY contracts /app/contracts/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/services/universe/requirements.txt
RUN pip install --no-cache-dir -e /app/contracts/

# Copy application code
COPY app /app/app/
COPY services/universe /app/services/universe/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose gRPC port
EXPOSE 5005X

# Run the service
CMD ["python", "-m", "services.universe.main"]

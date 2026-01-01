# Planning Service Dockerfile

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/planning/requirements.txt /app/services/planning/
COPY contracts /app/contracts/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/services/planning/requirements.txt
RUN pip install --no-cache-dir -e /app/contracts/

# Copy application code
COPY app /app/app/
COPY services/planning /app/services/planning/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose gRPC port (default: 50051)
EXPOSE 50051

# Run the service
CMD ["python", "-m", "services.planning.main"]

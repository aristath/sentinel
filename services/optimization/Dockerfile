# uoptimization Service Dockerfile

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/optimization/requirements.txt /app/services/optimization/
COPY contracts /app/contracts/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/services/optimization/requirements.txt
RUN pip install --no-cache-dir -e /app/contracts/

# Copy application code
COPY app /app/app/
COPY services/optimization /app/services/optimization/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose HTTP port
EXPOSE 8005

# Run the service
CMD ["python", "-m", "services.optimization.main"]

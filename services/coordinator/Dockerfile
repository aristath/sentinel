FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY services/coordinator/requirements.txt /app/services/coordinator/
RUN pip install --no-cache-dir -r /app/services/coordinator/requirements.txt

# Copy application code
COPY app /app/app/
COPY services/coordinator /app/services/coordinator/
COPY services/opportunity /app/services/opportunity/
COPY services/generator /app/services/generator/
COPY services/evaluator /app/services/evaluator/

# Set environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8011

# Run service
CMD ["python", "-m", "services.coordinator.main"]

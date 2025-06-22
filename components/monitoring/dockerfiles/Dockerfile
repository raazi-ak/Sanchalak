FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ .

# Create logs directory
RUN mkdir -p logs

# Expose port for the health dashboard
EXPOSE 8080

# Run the health dashboard
CMD ["python3", "health_dashboard.py"] 
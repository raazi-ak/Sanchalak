FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY ../src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --shell /bin/bash appuser

# Copy source code
COPY ../src/ .

# Create necessary directories and set permissions
RUN mkdir -p logs uploads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import psutil; exit(0 if any('bot.py' in ' '.join(p.cmdline()) for p in psutil.process_iter()) else 1)" || exit 1

# Expose port for health checks
EXPOSE 8080

# Default command
CMD ["python3", "main.py"] 
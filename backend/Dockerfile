FROM python:3.12-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies
# - curl: for health checks
# - postgresql-client: for pg_isready
# - redis-tools: for redis-cli
# - ffmpeg: for video processing (watermarking)
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client \
    redis-tools \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create static directories for generated content
RUN mkdir -p /app/static/generated /app/static/materials

# Make entrypoint script executable
RUN chmod +x /app/scripts/docker_entrypoint.sh

# Expose port
EXPOSE 8000

# Environment variables for pre-generation control
# SKIP_PREGENERATION=true - Skip AI API calls (use existing materials)
# PREGENERATION_LIMIT=10  - Number of materials to generate per tool
# SKIP_AVATAR=true        - Skip avatar generation (saves A2E API costs)
# SKIP_VIDEO=true         - Skip video generation (saves Pollo API costs)
# ALLOW_EMPTY_MATERIALS=true - Allow service to start without materials (dev mode)
# MIN_TEMPLATES=1         - Minimum templates required per group
# STARTUP_TIMEOUT=300     - Timeout for startup validation in seconds

# Use entrypoint script for startup validation
# IMPORTANT: Service will NOT start if demo materials are not ready
ENTRYPOINT ["/app/scripts/docker_entrypoint.sh"]

# Default command (passed to entrypoint)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

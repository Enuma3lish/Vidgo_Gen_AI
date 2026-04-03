FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ── System dependencies + Node.js (for MCP servers) ──
RUN apt-get update && apt-get install -y \
    curl postgresql-client redis-tools ffmpeg dos2unix gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Verify Node.js
RUN node --version && npm --version

# ── 1. Install Pollo MCP server (npm global) ──
RUN npm install -g pollo-mcp && \
    echo "✅ pollo-mcp installed"

# ── 2. Build PiAPI MCP server (from source) ──
# Build context is project root (.), so mcp-servers/ is at the top level
COPY mcp-servers/piapi-mcp-server /app/mcp-servers/piapi-mcp-server
RUN cd /app/mcp-servers/piapi-mcp-server && \
    npm install && \
    npm run build && \
    echo "✅ piapi-mcp-server built: $(ls dist/index.js)"

# ── 3. Python dependencies ──
# Build context is project root; requirements.txt is in backend/
COPY backend/requirements.txt .

RUN pip install --upgrade pip && \
    pip uninstall -y \
    google-genai \
    google-generativeai \
    google-ai-generativelanguage \
    google-api-core \
    protobuf \
    || true

RUN pip install --no-cache-dir -r requirements.txt

# Check packages
RUN python -c "from google import genai; print('✅ google-genai OK')"
RUN python -c "import mcp; print('✅ mcp SDK OK')"
RUN python -c "from google.cloud import storage; print('✅ google-cloud-storage OK')"

# ── 4. Copy application code ──
# Build context is project root; copy backend/ contents into /app
COPY backend/ .

# Static directories
RUN mkdir -p /app/static/generated /app/static/materials /app/static/tryon_garments

# Convert entrypoint script CRLF → LF
RUN dos2unix /app/scripts/docker_entrypoint.sh && \
    chmod +x /app/scripts/docker_entrypoint.sh && \
    echo "=== Verifying script (first 5 lines) ===" && \
    head -5 /app/scripts/docker_entrypoint.sh && \
    echo "=== Verifying no CRLF ===" && \
    od -c /app/scripts/docker_entrypoint.sh | head -3

# Final verification
RUN python -c "from google import genai; print('✅ Final: google-genai import OK with project files')"

# ── MCP server path environment ──
ENV PIAPI_MCP_PATH=/app/mcp-servers/piapi-mcp-server/dist/index.js

EXPOSE 8000
ENTRYPOINT ["/bin/bash", "/app/scripts/docker_entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ── System dependencies + Node.js (for MCP servers) ──
# fonts-noto-cjk: needed by the deterministic image-translator renderer
# so PIL can draw real Traditional Chinese / Japanese / Korean glyphs
# at the OCR bounding boxes Gemini returns. Without it PIL falls back
# to its built-in Latin font and CJK characters render as tofu (□).
RUN apt-get update && apt-get install -y \
    curl postgresql-client redis-tools ffmpeg dos2unix gnupg \
    fonts-noto-cjk fonts-noto-cjk-extra \
    && rm -rf /var/lib/apt/lists/*

# Node.js + MCP server build removed 2026-05-26 — both MCP providers
# (Pollo MCP + PiAPI MCP) deleted in favor of their REST equivalents.
# This trims the image by ~150-200 MB (Node 20 + npm + the
# piapi-mcp-server build artifacts) and shaves ~30-60s off every build.
# Re-introducing MCP would require restoring this block + apt installing
# nodejs from deb.nodesource.com.

# ── Python dependencies ──
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
RUN python -c "import google.auth; print('✅ google-auth OK')"
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
RUN python -c "from app.config.example_presets import EXAMPLE_PRESETS; print(f'✅ Example presets: {sum(len(v) for v in EXAMPLE_PRESETS.values())} presets across {len(EXAMPLE_PRESETS)} tools')"

# ── MCP server path environment ──
ENV PIAPI_MCP_PATH=/app/mcp-servers/piapi-mcp-server/dist/index.js

EXPOSE 8000
ENTRYPOINT ["/bin/bash", "/app/scripts/docker_entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
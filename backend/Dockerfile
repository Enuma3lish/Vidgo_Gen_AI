FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 系統依賴
RUN apt-get update && apt-get install -y \
    curl postgresql-client redis-tools ffmpeg dos2unix \
    && rm -rf /var/lib/apt/lists/*

# 1. 先複製 requirements
COPY requirements.txt .

# 2. 核彈級清理 (Nuclear Cleanup)
RUN pip install --upgrade pip && \
    pip uninstall -y \
    google-genai \
    google-generativeai \
    google-ai-generativelanguage \
    google-api-core \
    protobuf \
    || true

# 3. 安裝所有依賴 (包含 requirements.txt 裡的 google-genai)
# 因為你的 requirements.txt 已經包含 google-genai>=0.2.0，這裡直接跑這行即可
RUN pip install --no-cache-dir -r requirements.txt

# 4. 第一次檢查 (確認套件安裝成功)
RUN python -c "from google import genai; print('✅ Check 1: Packages installed successfully')"

# =========================================================
# 5. 關鍵修改：先 COPY 程式碼，再做最後檢查！
# =========================================================
COPY . .

# 建立靜態目錄 (tryon_garments for cached Virtual Try-On garment images)
RUN mkdir -p /app/static/generated /app/static/materials /app/static/tryon_garments

# Convert entrypoint script from Windows CRLF to Unix LF
# The script was already copied via "COPY . ." above
# dos2unix is installed in the apt-get step at the top
RUN dos2unix /app/scripts/docker_entrypoint.sh && \
    chmod +x /app/scripts/docker_entrypoint.sh && \
    echo "=== Verifying script (first 5 lines) ===" && \
    head -5 /app/scripts/docker_entrypoint.sh && \
    echo "=== Verifying no CRLF (should show \\n only, not \\r) ===" && \
    od -c /app/scripts/docker_entrypoint.sh | head -3

# 6. 最終檢查 (Final Verification)
# 如果這裡失敗，代表你 COPY 進來的檔案裡有 "google" 資料夾或 "google.py" 蓋掉了套件
RUN python -c "from google import genai; print('✅ Final Check: Import works with project files!')"

EXPOSE 8000
ENTRYPOINT ["/bin/bash", "/app/scripts/docker_entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
# ---------- base ----------
FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps (Pillow, ultralytics cần libjpeg/zlib, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libjpeg62-turbo libpng16-16 libxml2 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------- deps ----------
# Nếu có requirements.txt thì COPY vào trước để cache layer
# (Nếu chưa có, bạn có thể dán danh sách pip install ở đây)
COPY requirements.txt ./

# Torch CPU (khuyên dùng cho image nhỏ hơn)
RUN pip install --upgrade pip && \
    pip install --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install -r requirements.txt

# ---------- app ----------
COPY app/ ./app/
# models và .env mount từ host qua volume khi chạy (không copy cứng)
RUN mkdir -p /app/results

# Env mặc định an toàn khi test
ENV HOST=0.0.0.0 \
    PORT=5002 \
    PROM_PORT=8097 \
    TRACING=off \
    MODEL_PATH=/app/models/best.pt

EXPOSE 5002
EXPOSE 8097

# Healthcheck đơn giản
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5002/healthz').read()" || exit 1

# Chạy app
CMD ["python", "app/main.py"]

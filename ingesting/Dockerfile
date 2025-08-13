# ---------- Base ----------
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Lib runtime cho Pillow (đọc/validate ảnh)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libpng16-16 zlib1g libglib2.0-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------- Deps (cacheable) ----------
# requirements.txt nằm trong thư mục ingesting/
COPY ingesting/requirements.txt ./requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libjpeg-dev zlib1g-dev && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*

# ---------- App code ----------
# Copy toàn bộ mã nguồn ingesting/ vào image
COPY ingesting ./ingesting

EXPOSE 5001

# ---------- Runtime ----------
# Uvicorn chạy service ingesting
CMD ["uvicorn", "ingesting.main:app", "--host", "0.0.0.0", "--port", "5001"]

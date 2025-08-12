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
COPY app/requirements.txt .

# Torch CPU (khuyên dùng cho image nhỏ hơn)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libjpeg-dev zlib1g-dev && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*

# ---------- app ----------
COPY app/app ./app
# models và .env mount từ host qua volume khi chạy (không copy cứng)
RUN mkdir -p /app/results

EXPOSE 5000

# Chạy app
CMD ["uvicorn", "retriever.main:app", "--host", "0.0.0.0", "--port", "5000"]

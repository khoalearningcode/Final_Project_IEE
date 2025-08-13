# ---------- base ----------
FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Lib runtime cần cho Pillow, Ultralytics, v.v.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libjpeg62-turbo libpng16-16 libxml2 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------- deps ----------
# Copy file requirements từ thư mục app vào container
COPY app/requirements.txt ./requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libjpeg-dev zlib1g-dev && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*

# ---------- app ----------
# Copy toàn bộ mã nguồn trong app/
COPY app ./app

EXPOSE 5000

# Chạy app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]

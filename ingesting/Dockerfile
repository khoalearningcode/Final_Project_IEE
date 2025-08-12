FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Cài dependencies hệ thống (Pillow cần libjpeg + zlib)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libjpeg-dev zlib1g-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Cài Python deps (cache layer tốt)
COPY ingesting/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source
COPY ./ingesting /app/ingesting

# Expose app
EXPOSE 5001

# HEALTHCHECK: tuỳ route healthz của bạn
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5001/healthz || exit 1

# Chạy uvicorn (có thể tăng workers ở prod)
CMD ["python","-m","uvicorn","ingesting.main:app","--host","0.0.0.0","--port","5001","--proxy-headers"]

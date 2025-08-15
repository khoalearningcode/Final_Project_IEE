FROM python:3.10-slim

WORKDIR /app

# Copy file requirements và cài đặt dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code cần test
COPY app/ app/
COPY ingesting/ ingesting/
COPY tests/ tests/
COPY .env .env

# Lệnh mặc định khi chạy container
CMD ["pytest", "tests/", "--maxfail=1", "--disable-warnings", "-q"]

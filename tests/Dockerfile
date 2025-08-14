FROM python:3.10-slim

WORKDIR /app

# Copy file requirements và cài đặt dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install pytest pytest-cov

# Copy source code cần test
COPY app/ app/
COPY ingesting/ ingesting/
COPY tests/ tests/
COPY .env.test .env.test

# Lệnh mặc định khi chạy container
CMD ["pytest", "tests/", "--maxfail=1", "--disable-warnings", "-q"]

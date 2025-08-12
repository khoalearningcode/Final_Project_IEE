# Ingesting Service - Tài Liệu Mô Tả

## 1. Tổng Quan
Dịch vụ này là **API tiếp nhận ảnh raw** được xây dựng bằng **FastAPI** với các chức năng:
- Nhận ảnh qua API.
- Kiểm tra và đọc ảnh.
- Tải ảnh lên **Google Cloud Storage (GCS)** và sinh **signed URL** (fallback nếu không có private key).
- Ghi lại **trace** (Jaeger) và **metrics** (OpenTelemetry + Prometheus).
- Trả JSON gồm:
  - `file_id`
  - `gcs_path`
  - `gs_uri`
  - `signed_url`

---

## 2. Tính Năng

### Các Endpoint API
1. `GET /` — Endpoint chào mừng.
2. `GET /healthz` — Kiểm tra tình trạng dịch vụ.
3. `POST /push_image` — Nhận ảnh, validate, upload lên GCS, sinh signed URL.

### Giám Sát & Quan Sát
- **Tracing** với OpenTelemetry + Jaeger (theo dõi validate, upload, generate signed URL).
- **Metrics** với OpenTelemetry và Prometheus:
  - `ingesting_push_image_counter`
  - `ingesting_push_image_response_time_seconds`
  - `ingesting_response_time_summary_seconds` (Prometheus Summary).

---

## 3. Công Nghệ Sử Dụng

| Công nghệ / Thư viện     | Mục đích |
|--------------------------|---------|
| **FastAPI**              | Xây dựng API |
| **Uvicorn**              | Chạy FastAPI |
| **PIL (Pillow)**         | Kiểm tra định dạng ảnh |
| **Loguru**               | Ghi log |
| **OpenTelemetry**        | Thu thập trace & metrics |
| **Jaeger**               | Phân tích luồng xử lý |
| **Prometheus**           | Giám sát hiệu suất |
| **Prometheus Client**    | Ghi metrics |
| **Google Cloud Storage** | Lưu trữ ảnh |

---

## 4. Biến Môi Trường

| Biến            | Mô tả | Mặc định |
|-----------------|-------|----------|
| `ENABLE_TRACING` | Bật/tắt Jaeger tracing | `true` |
| `DISABLE_METRICS`| Tắt metrics | `false` |
| `METRICS_PORT`  | Cổng Prometheus | `8098` |
| `JAEGER_AGENT_HOST` | Host Jaeger Agent | `jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local` |
| `JAEGER_AGENT_PORT` | Port Jaeger Agent | `6831` |
| `GCS_BUCKET_NAME` | Tên bucket GCS | — |

---

## 5. Chạy Dịch Vụ

```bash
# Cài đặt dependencies
pip install -r requirements.txt

# Chạy dịch vụ
python ingesting/main.py
```

Dịch vụ sẽ sẵn sàng tại:  
`http://localhost:5001/ingesting/docs` (Swagger UI)

Prometheus metrics:  
`http://localhost:8098/metrics`

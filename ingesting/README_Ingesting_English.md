# Ingesting Service — Documentation

## 1. Overview
This service is a **raw image ingestion API** built with **FastAPI** that:
- Accepts raw images via API.
- Validates and reads the image.
- Uploads images to **Google Cloud Storage (GCS)** and generates **signed URLs** (fallback if no private key).
- Records **traces** (Jaeger) and **metrics** (OpenTelemetry + Prometheus).
- Returns a JSON payload containing:
  - `file_id`
  - `gcs_path`
  - `gs_uri`
  - `signed_url`

---

## 2. Features

### API Endpoints
1. `GET /` — Root endpoint with a welcome message.
2. `GET /healthz` — Health check endpoint.
3. `POST /push_image` — Accepts an image, validates it, uploads to GCS, generates a signed URL.

### Observability
- **Tracing** with OpenTelemetry + Jaeger (detailed spans for validation, upload, and signed URL generation).
- **Metrics** with OpenTelemetry and Prometheus:
  - `ingesting_push_image_counter`
  - `ingesting_push_image_response_time_seconds`
  - `ingesting_response_time_summary_seconds` (Prometheus Summary).

---

## 3. Technologies Used

| Technology              | Purpose |
|-------------------------|---------|
| **FastAPI**             | Web API framework |
| **Uvicorn**             | ASGI server to run FastAPI |
| **PIL (Pillow)**        | Image validation and conversion |
| **Loguru**              | Structured logging |
| **OpenTelemetry**       | Distributed tracing & metrics |
| **Jaeger**              | Trace visualization & analysis |
| **Prometheus**          | Metrics collection & monitoring |
| **Prometheus Client**   | Native metrics instrumentation |
| **Google Cloud Storage**| Image storage backend |

---

## 4. Environment Variables

| Variable       | Description | Default |
|----------------|-------------|---------|
| `ENABLE_TRACING` | Enable or disable Jaeger tracing | `true` (change when dev test) |
| `DISABLE_METRICS`| Disable metrics collection | `false` (change when dev test) |
| `METRICS_PORT` | Port for Prometheus metrics server | `8098` |
| `JAEGER_AGENT_HOST` | Hostname of Jaeger Agent | `jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local` |
| `JAEGER_AGENT_PORT` | Port for Jaeger Agent | `6831` |
| `GCS_BUCKET_NAME` | Target GCS bucket name | — |

---

## 5. Running the Service

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python ingesting/main.py
```

The service will be available at:  
`http://0.0.0.0:5001/ingesting/docs` (Swagger UI)

Prometheus metrics will be available at:  
`http://0.0.0.0:8098/metrics`

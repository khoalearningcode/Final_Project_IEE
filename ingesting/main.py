# =========================
# Ingesting Service (raw image ingest)
# =========================
# Chức năng:
# - Nhận ảnh qua API
# - Validate & đọc ảnh
# - Upload ảnh lên GCS, sinh signed URL (fallback nếu không có private key)
# - Ghi trace (Jaeger) + metrics (OTel + Prometheus)
# - Trả JSON: file_id, gcs_path, gs_uri, signed_url
# =========================

import os
import atexit
import datetime
import uuid
from io import BytesIO
from time import time
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv() or "../.env")  # chỉnh path nếu .env ở root

# ---------- FastAPI & serving ----------
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

# ---------- Logging ----------
from loguru import logger

# ---------- Observability: OpenTelemetry ----------
from opentelemetry import metrics
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader

from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Link, get_tracer_provider, set_tracer_provider

# Jaeger (có thể tắt qua ENV để tránh lỗi khi chạy local)
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

# ---------- Prometheus client (HTTP /metrics) ----------
from prometheus_client import Summary, start_http_server

# ---------- Image & errors ----------
from PIL import Image, UnidentifiedImageError

# ---------- Project modules ----------
from ingesting.config import Config
from ingesting.utils import get_storage_client

# ---------- Google auth (để log cảnh báo creds) ----------
from google.auth import default as gauth_default

# ============== Feature flags qua ENV ==============
ENABLE_TRACING = os.getenv("ENABLE_TRACING", "true").lower() == "true"
DISABLE_METRICS = os.getenv("DISABLE_METRICS", "false").lower() == "true" 
METRICS_PORT = int(os.getenv("METRICS_PORT", "8098"))
JAEGER_HOST = os.getenv(
    "JAEGER_AGENT_HOST",
    "jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local",
)
JAEGER_PORT = int(os.getenv("JAEGER_AGENT_PORT", "6831"))

# =========================
# 1) Tracing (Jaeger) - optional
# =========================
if ENABLE_TRACING:
    set_tracer_provider(
        TracerProvider(resource=Resource.create({SERVICE_NAME: "ingesting-service"}))
    )
    tracer = get_tracer_provider().get_tracer("ingesting", "0.1.1")

    # NOTE: Jaeger Thrift đã deprecated; vẫn dùng tạm. Có thể chuyển OTLP sau.
    jaeger_exporter = JaegerExporter(
        agent_host_name=JAEGER_HOST,
        agent_port=JAEGER_PORT,
    )
    span_processor = BatchSpanProcessor(jaeger_exporter)
    get_tracer_provider().add_span_processor(span_processor)
    atexit.register(span_processor.shutdown)
else:
    # tracer dummy
    set_tracer_provider(TracerProvider(resource=Resource.create({SERVICE_NAME: "ingesting-service"})))
    tracer = get_tracer_provider().get_tracer("ingesting", "0.1.1")
    logger.warning("Tracing is disabled (ENABLE_TRACING=false).")

# =========================
# 2) Kết nối GCS
# =========================
GCS_BUCKET_NAME = Config.GCS_BUCKET_NAME
try:
    storage_client = get_storage_client()  # bạn đã có util này
    bucket = storage_client.get_bucket(GCS_BUCKET_NAME)
    if not bucket.exists():
        logger.error(f"Bucket {GCS_BUCKET_NAME} not found in Google Cloud Storage.")
        raise HTTPException(
            status_code=404, detail=f"Bucket {GCS_BUCKET_NAME} not found."
        )
    logger.info(f"Connected to GCS bucket '{GCS_BUCKET_NAME}' successfully")
except Exception as e:
    logger.error(f"Error accessing GCS bucket '{GCS_BUCKET_NAME}': {e}")
    raise HTTPException(status_code=500, detail=str(e))

# Gợi ý log loại credentials đang dùng (để debug signed URL)
try:
    creds, proj = gauth_default()
    logger.info(f"GAuth project: {proj}; creds class: {creds.__class__.__name__}")
except Exception as _:
    pass

# =========================
# 3) Metrics (OTel + Prometheus)
# =========================
class _NoopMetric:
    def add(self, *_, **__): pass
    def record(self, *_, **__): pass
    def observe(self, *_, **__): pass
# OTel Metrics Provider + Reader
if not DISABLE_METRICS:
    resource = Resource(attributes={SERVICE_NAME: "ingesting-service"})
    reader = PrometheusMetricReader()
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    set_meter_provider(provider)
    meter = metrics.get_meter("ingesting", "0.1.1")

    # OTel metrics
    ingesting_counter = meter.create_counter(
        name="ingesting_push_image_counter",
        description="Number of /push_image requests",
    )
    ingesting_histogram = meter.create_histogram(
        name="ingesting_push_image_response_time_seconds",
        description="Response time for /push_image",
        unit="s",
    )

    # Prometheus client metrics (tóm tắt latency)
    response_time_summary = Summary(
        "ingesting_response_time_summary_seconds",
        "Summary of response time for /push_image",
    )
else:
    logger.warning("Metrics are disabled (DISABLE_METRICS=true).")
    ingesting_counter = _NoopMetric()
    ingesting_histogram = _NoopMetric()
    response_time_summary = _NoopMetric()

# =========================
# 4) FastAPI Application
# =========================
app = FastAPI(
    title="Ingesting Service",
    docs_url="/ingesting/docs",
    openapi_url="/ingesting/openapi.json",
)

@app.get("/")
def read_root():
    """Endpoint chào mừng / hướng dẫn mở docs."""
    return {"message": "Welcome to the Image Ingestion API. Visit ingesting/docs to test."}

@app.get("/healthz")
def health_check():
    """Health check cho liveness/readiness probe."""
    return {"status": "healthy"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = "static/favicon.ico"
    if os.path.exists(path):
        return FileResponse(path)
    return Response(status_code=204)  # không 404 nữa nếu chưa có file

# =========================
# 5) API: /push_image
# =========================
@app.post("/push_image")
async def push_image(file: UploadFile = File(...)):
    """
    Nhận file ảnh:
    - Validate định dạng
    - Upload ảnh lên GCS & (cố gắng) sinh signed URL
    - Ghi metrics + trace
    """
    start_time = time()
    ingesting_counter.add(1, {"api": "/push_image"})

    with tracer.start_as_current_span("push_image") as push_span:

        # --- Validate ảnh ---
        with tracer.start_as_current_span(
            "validate-image", links=[Link(push_span.get_span_context())]
        ):
            image_bytes = await file.read()
            ext = (file.filename or "").split(".")[-1].lower()
            if ext not in {"jpg", "jpeg", "png"}:
                raise HTTPException(
                    status_code=400,
                    detail="Only .jpg/.jpeg/.png allowed",
                )
            try:
                Image.open(BytesIO(image_bytes)).convert("RGB")
            except UnidentifiedImageError:
                raise HTTPException(status_code=400, detail="Invalid image file")

        # Tạo ID và đường dẫn object trên GCS
        file_id = str(uuid.uuid4())
        gcs_path = f"images/{file_id}.{ext}"
        gs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_path}"

        # --- Upload ảnh lên GCS ---
        with tracer.start_as_current_span(
            "upload-to-gcs", links=[Link(push_span.get_span_context())]
        ):
            blob = bucket.blob(gcs_path)
            if not blob.exists():
                try:
                    blob.upload_from_string(image_bytes, content_type=file.content_type)
                    logger.info(f"Uploaded to GCS: {gcs_path}")
                except Exception as e:
                    logger.error(f"GCS upload failed: {e}")
                    raise HTTPException(status_code=500, detail="GCS upload failed")

        # --- Sinh signed URL truy cập ảnh (fallback nếu không có private key) ---
        signed_url = None
        with tracer.start_as_current_span(
            "generate-signed-url", links=[Link(push_span.get_span_context())]
        ):
            try:
                response_disposition = f"attachment; filename={file.filename}"
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(hours=1),
                    method="GET",
                    response_disposition=response_disposition,
                )
            except AttributeError as e:
                # Trường hợp dùng user token (không có private key) => không ký được URL
                logger.warning(f"Skip signed URL (no private key in creds): {e}")
                signed_url = None
            except Exception as e:
                logger.warning(f"Signed URL generation failed: {e}")
                signed_url = None

        # Ghi thời gian xử lý
        elapsed = time() - start_time
        ingesting_histogram.record(elapsed, {"api": "/push_image"})
        response_time_summary.observe(elapsed)

        # --- Phản hồi ---
        return {
            "message": "Successfully!",
            "file_id": file_id,
            "gcs_path": gcs_path,
            "gs_uri": gs_uri,          # luôn có
            "signed_url": signed_url,  # có nếu SA key / private key sẵn sàng
        }

# =========================
# 6) Entrypoint (dev run)
# =========================
if __name__ == "__main__":
    if not DISABLE_METRICS:
        start_http_server(port=METRICS_PORT, addr="0.0.0.0")
    uvicorn.run(app, host="0.0.0.0", port=5001)

# docker push godminhkhoa/ingesting-service:latest

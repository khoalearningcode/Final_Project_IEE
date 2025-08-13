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

import atexit
import datetime
import os
import uuid
from io import BytesIO
from time import time
from typing import List, Optional

import requests
from dotenv import find_dotenv, load_dotenv
# ============== Env bootstrapping ==============
load_dotenv(find_dotenv() or "../.env")  # chỉnh path nếu .env ở root
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from google.auth import default as gauth_default
from loguru import logger
from PIL import Image, ImageFile, UnidentifiedImageError
from pydantic import BaseModel
from prometheus_client import Summary, start_http_server

from opentelemetry import metrics
from opentelemetry.metrics import set_meter_provider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Link, get_tracer_provider, set_tracer_provider
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

import uvicorn

# ---------- Project modules ----------
from ingesting.utils import get_storage_client



# ---------- PIL config ----------
ImageFile.LOAD_TRUNCATED_IMAGES = True

# ============== Feature flags qua ENV ==============
ENABLE_TRACING: bool = os.getenv("ENABLE_TRACING", "true").lower() == "true"
DISABLE_METRICS: bool = os.getenv("DISABLE_METRICS", "false").lower() == "true"
METRICS_PORT: int = int(os.getenv("METRICS_PORT", "8098"))
JAEGER_HOST: str = os.getenv(
    "JAEGER_AGENT_HOST",
    "jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local",
)
JAEGER_PORT: int = int(os.getenv("JAEGER_AGENT_PORT", "6831"))

ALLOWED_IMAGE_EXIST = {"jpg", "jpeg", "png"}
ALLOWED_VIDEO_EXIST = {"mp4", "mov", "avi", "mkv", "webm"}  # hiện chưa dùng
IMAGES_API_PREFIX = "images/api"
IMAGES_URL_PREFIX = "images/url"
VIDEOS_API_PREFIX = "videos/api"  # hiện chưa dùng

# =========================
# 1) Tracing (Jaeger) - optional
# =========================
if ENABLE_TRACING:
    set_tracer_provider(
        TracerProvider(resource=Resource.create({SERVICE_NAME: "ingesting-service"}))
    )
    tracer = get_tracer_provider().get_tracer("ingesting", "0.1.1")

    # NOTE: Jaeger Thrift đã deprecated; vẫn dùng tạm. Có thể chuyển OTLP sau.
    jaeger_exporter = JaegerExporter(agent_host_name=JAEGER_HOST, agent_port=JAEGER_PORT)
    span_processor = BatchSpanProcessor(jaeger_exporter)
    get_tracer_provider().add_span_processor(span_processor)
    atexit.register(span_processor.shutdown)
else:
    set_tracer_provider(
        TracerProvider(resource=Resource.create({SERVICE_NAME: "ingesting-service"}))
    )
    tracer = get_tracer_provider().get_tracer("ingesting", "0.1.1")
    logger.warning("Tracing is disabled (ENABLE_TRACING=false).")

# =========================
# 2) Kết nối GCS
# =========================
GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "")

try:
    storage_client = get_storage_client()  # util do bạn cung cấp
    bucket = storage_client.get_bucket(GCS_BUCKET_NAME)
    if not bucket.exists():
        logger.error(f"Bucket {GCS_BUCKET_NAME} not found in Google Cloud Storage.")
        raise HTTPException(status_code=404, detail=f"Bucket {GCS_BUCKET_NAME} not found.")
    logger.info(f"Connected to GCS bucket '{GCS_BUCKET_NAME}' successfully.")
except Exception as e:
    logger.error(f"Error accessing GCS bucket '{GCS_BUCKET_NAME}': {e}")
    raise HTTPException(status_code=500, detail=str(e))

# Gợi ý log loại credentials đang dùng (để debug signed URL)
try:
    creds, proj = gauth_default()
    logger.info(f"GAuth project: {proj}; creds class: {creds.__class__.__name__}")
except Exception:
    pass

# =========================
# 3) Metrics (OTel + Prometheus)
# =========================
class _NoopMetric:
    def add(self, *_, **__): ...
    def record(self, *_, **__): ...
    def observe(self, *_, **__): ...

if not DISABLE_METRICS:
    resource = Resource(attributes={SERVICE_NAME: "ingesting-service"})
    reader = PrometheusMetricReader()
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    set_meter_provider(provider)
    meter = metrics.get_meter("ingesting", "0.1.1")

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


async def _handle_single_image_upload(
    filename: str,
    content_type: Optional[str],
    image_bytes: bytes,
    source: str = "api",
) -> dict:
    """
    Validate & upload 1 ảnh lên GCS, trả về metadata + signed_url nếu tạo được.
    """
    start_time = time()
    ingesting_counter.add(1, {"api": "/push_image"})

    with tracer.start_as_current_span("push_image") as push_span:
        # Validate ảnh
        with tracer.start_as_current_span(
            "validate-image", links=[Link(push_span.get_span_context())]
        ):
            ext = (filename or "").split(".")[-1].lower()
            if ext not in ALLOWED_IMAGE_EXIST:
                raise HTTPException(status_code=400, detail="Only .jpg/.jpeg/.png allowed")
            try:
                Image.open(BytesIO(image_bytes)).convert("RGB")
            except UnidentifiedImageError:
                raise HTTPException(status_code=400, detail="Invalid image file")

        # Tạo ID & path
        prefix = IMAGES_API_PREFIX if source == "api" else IMAGES_URL_PREFIX
        file_id = str(uuid.uuid4())
        gcs_path = f"{prefix}/{file_id}.{ext}"
        gs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_path}"

        # Upload GCS
        with tracer.start_as_current_span(
            "upload-to-gcs", links=[Link(push_span.get_span_context())]
        ):
            blob = bucket.blob(gcs_path)
            try:
                blob.upload_from_string(image_bytes, content_type=content_type or f"image/{ext}")
                logger.info(f"Uploaded image to GCS: {gcs_path}")
            except Exception as e:
                logger.error(f"GCS upload failed: {e}")
                raise HTTPException(status_code=500, detail="GCS upload failed")

        # Signed URL (v4)
        signed_url: Optional[str] = None
        with tracer.start_as_current_span(
            "generate-signed-url", links=[Link(push_span.get_span_context())]
        ):
            try:
                response_disposition = f"attachment; filename={filename}"
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(hours=1),
                    method="GET",
                    response_disposition=response_disposition,
                )
            except Exception as e:
                logger.warning(f"Signed URL generation failed (image): {e}")
                signed_url = None

        # Metrics
        elapsed = time() - start_time
        ingesting_histogram.record(elapsed, {"api": "/push_image"})
        response_time_summary.observe(elapsed)

        return {
            "message": "Successfully!",
            "file_id": file_id,
            "gcs_path": gcs_path,
            "gs_uri": gs_uri,
            "signed_url": signed_url,
        }


# ---------- Health & root ----------
@app.get("/")
def read_root() -> dict:
    """Endpoint chào mừng / hướng dẫn mở docs."""
    return {"message": "Welcome to the Image Ingestion API. Visit ingesting/docs to test."}


@app.get("/healthz")
def health_check() -> dict:
    """Health check cho liveness/readiness probe."""
    return {"status": "healthy"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = "static/favicon.ico"
    if os.path.exists(path):
        return FileResponse(path)
    return Response(status_code=204)  # không 404 nếu chưa có file


# =========================
# 5) API: /push_image & /push_images
# =========================
@app.post("/push_image")
async def push_image(file: UploadFile = File(...)) -> dict:
    image_bytes = await file.read()
    return await _handle_single_image_upload(
        filename=file.filename,
        content_type=file.content_type,
        image_bytes=image_bytes,
        source="api",
    )


@app.post("/push_images")
async def push_images(files: List[UploadFile] = File(...)) -> dict:
    """
    Nhận nhiều ảnh cùng lúc:
      curl -F "files=@a.jpg" -F "files=@b.png" http://host/push_images
    """
    results = []
    for f in files:
        try:
            b = await f.read()
            res = await _handle_single_image_upload(
                filename=f.filename,
                content_type=f.content_type,
                image_bytes=b,
                source="api",
            )
            results.append({"filename": f.filename, **res})
        except HTTPException as he:
            results.append({"filename": f.filename, "error": he.detail})
        except Exception as e:
            results.append({"filename": f.filename, "error": str(e)})
    return {"count": len(results), "results": results}


# ---------- Push from URL ----------
class UrlIn(BaseModel):
    url: str


@app.post("/push_image_url")
async def push_image_url(payload: UrlIn) -> dict:
    """
    Tải ảnh từ URL công khai rồi upload lên GCS.
    Body JSON: {"url": "https://.../abc.jpg"}
    """
    ingesting_counter.add(1, {"api": "/push_image_url"})

    with tracer.start_as_current_span("push_image_url") as span:
        try:
            with tracer.start_as_current_span(
                "download-image", links=[Link(span.get_span_context())]
            ):
                r = requests.get(payload.url, timeout=20)
                if r.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Download failed: HTTP {r.status_code}")
                image_bytes = r.content
                content_type = r.headers.get("Content-Type")
                guessed_name = payload.url.split("?")[0].split("/")[-1] or "remote.jpg"
                if "." not in guessed_name:
                    # cố gắng đoán ext từ header
                    import mimetypes

                    ext = (mimetypes.guess_extension(content_type or "") or ".jpg").lstrip(".")
                    guessed_name = f"remote.{ext}"
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Gọi helper đúng kiểu async và set source="url" để path = images/url/<uuid>.<ext>
    return await _handle_single_image_upload(
        filename=guessed_name,
        content_type=content_type,
        image_bytes=image_bytes,
        source="url",
    )


# =========================
# 6) Entrypoint (dev run)
# =========================
if __name__ == "__main__":
    if not DISABLE_METRICS:
        start_http_server(port=METRICS_PORT, addr="0.0.0.0")
    uvicorn.run(app, host="0.0.0.0", port=5001)

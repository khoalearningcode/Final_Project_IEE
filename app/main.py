# =========================
# YOLO Inference Service (based on Retriever template)
# =========================
# Chức năng:
# - Nhận ảnh qua API
# - Chạy YOLO (Ultralytics) để detect
# - Trả JSON (bbox/cls/conf) hoặc ảnh annotated PNG
# - Ghi trace (Jaeger) & metrics (OTel + Prometheus)
# - Idempotent init cho Tracer/Meter, lazy-load model
#
# ENV gợi ý:
# MODEL_PATH=./models/best.pt
# CONF=0.25
# IOU=0.45
# IMG_SIZE=640
# PROM_PORT=8097
# JAEGER_HOST=jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local
# JAEGER_PORT=6831
# TRACING=auto|on|off

# ---------- Standard ----------
import atexit
import os
import socket
from io import BytesIO
from time import time
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv() or "../.env")  # chỉnh path nếu .env ở root

# ---------- FastAPI ----------
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

# ---------- Logging ----------
from loguru import logger

# ---------- Observability: OpenTelemetry ----------
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider as SDKMeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader

from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.trace import Link

# ---------- Observability: Prometheus client ----------
from prometheus_client import Gauge, Summary, start_http_server

# ---------- Image / ML ----------
from PIL import Image, UnidentifiedImageError
import torch
import numpy as np
from ultralytics import YOLO


# =========================
# 0) Config
# =========================
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = (BASE_DIR / "models" / "best.pt").resolve()
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(DEFAULT_MODEL)))
if not MODEL_PATH.is_absolute():
    MODEL_PATH = (BASE_DIR / MODEL_PATH).resolve()

CONF = float(os.getenv("CONF", "0.25"))
IOU = float(os.getenv("IOU", "0.45"))
IMG_SIZE = int(os.getenv("IMG_SIZE", "640"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

JAEGER_HOST = os.getenv("JAEGER_HOST", "jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local")
JAEGER_PORT = int(os.getenv("JAEGER_PORT", "6831"))
PROM_PORT = int(os.getenv("PROM_PORT", "8097"))
TRACING_MODE = os.getenv("TRACING", "auto").lower()  # auto | on | off

SERVICE = "yolo-inference-service"

# Thư mục lưu ảnh kết quả annotated
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# =========================
# 1) Tracing (Jaeger) - idempotent + auto-disable nếu không resolve
# =========================
resource = Resource.create({SERVICE_NAME: SERVICE})

current_provider = trace.get_tracer_provider()
if not isinstance(current_provider, SDKTracerProvider):
    provider = SDKTracerProvider(resource=resource)
    try:
        trace.set_tracer_provider(provider)
    except Exception:
        provider = trace.get_tracer_provider()
else:
    provider = current_provider

tracer = trace.get_tracer_provider().get_tracer("yolo", "0.1.0")

def _should_enable_tracing() -> bool:
    if TRACING_MODE == "off":
        return False
    if TRACING_MODE == "on":
        return True
    # auto: chỉ bật nếu resolve được host
    try:
        socket.getaddrinfo(JAEGER_HOST, JAEGER_PORT)
        return True
    except socket.gaierror:
        return False

if _should_enable_tracing():
    try:
        jaeger_exporter = JaegerExporter(
            agent_host_name=JAEGER_HOST,
            agent_port=JAEGER_PORT,
        )
        span_processor = BatchSpanProcessor(jaeger_exporter)
        try:
            provider.add_span_processor(span_processor)
        except Exception:
            pass
        atexit.register(span_processor.shutdown)
        logger.info(f"Tracing enabled → Jaeger @ {JAEGER_HOST}:{JAEGER_PORT}")
    except Exception as e:
        logger.warning(f"Jaeger exporter init failed, tracing disabled: {e}")
else:
    logger.info("Tracing disabled (TRACING=off or host not resolvable).")


# =========================
# 2) Metrics (OTel + Prometheus)
# =========================
otel_resource = Resource(attributes={SERVICE_NAME: SERVICE})
reader = PrometheusMetricReader()

current_mp = metrics.get_meter_provider()
if not isinstance(current_mp, SDKMeterProvider):
    provider_metrics = SDKMeterProvider(resource=otel_resource, metric_readers=[reader])
    set_meter_provider(provider_metrics)
else:
    provider_metrics = current_mp

meter = metrics.get_meter("yolo_inference", "0.1.0")

# OTel metrics
inference_counter = meter.create_counter(
    name="yolo_inference_requests_total",
    description="Number of inference requests (/predict and /predict/annotated)",
)
inference_histogram = meter.create_histogram(
    name="yolo_inference_latency_seconds",
    description="Latency for YOLO inference",
    unit="s",
)

# Prometheus client metrics (init trong __main__ để tránh duplicated timeseries)
yolo_num_detections_gauge: Optional[Gauge] = None
yolo_response_time_summary: Optional[Summary] = None


# =========================
# 3) FastAPI Application & Helpers
# =========================
app = FastAPI(
    title="YOLO Inference Service",
    docs_url="/yolo/docs",
    openapi_url="/yolo/openapi.json",
)

_yolo_model: Optional[YOLO] = None
_yolo_names: List[str] = []


def ensure_model_loaded():
    """Lazy-load YOLO model khi lần đầu infer."""
    global _yolo_model, _yolo_names
    if _yolo_model is not None:
        return

    with tracer.start_as_current_span("load-model"):
        if not MODEL_PATH.exists():
            logger.error(f"Model not found at {MODEL_PATH}")
            raise RuntimeError(f"Model not found at {MODEL_PATH}")
        logger.info(f"Loading YOLO model: {MODEL_PATH} (device={DEVICE})")
        _yolo_model = YOLO(str(MODEL_PATH))
        try:
            _yolo_model.to(DEVICE)
        except Exception as e:
            logger.warning(f"Could not move model to device {DEVICE}: {e}")
        try:
            _yolo_names = _yolo_model.names if hasattr(_yolo_model, "names") else []
        except Exception:
            _yolo_names = []
        logger.info(f"Model loaded. Classes: {_yolo_names if _yolo_names else 'unknown'}")


def _parse_result(result) -> List[dict]:
    """Parse Ultralytics result to a list of detections."""
    dets = []
    if result.boxes is None:
        return dets
    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    clss = result.boxes.cls.cpu().numpy()
    for i in range(len(confs)):
        cls_id = int(clss[i])
        dets.append(
            {
                "class_id": cls_id,
                "class_name": _yolo_names[cls_id] if _yolo_names and 0 <= cls_id < len(_yolo_names) else str(cls_id),
                "confidence": float(confs[i]),
                "bbox_xyxy": [float(x) for x in boxes_xyxy[i].tolist()],  # [x1,y1,x2,y2]
            }
        )
    return dets


def _annotate_image(result) -> bytes:
    """Render predictions to an image and return PNG bytes (RGB)."""
    im_bgr = result.plot()  # numpy array (BGR)
    rgb = np.ascontiguousarray(im_bgr[:, :, ::-1])
    pil_im = Image.fromarray(rgb)
    buf = BytesIO()
    pil_im.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# =========================
# 4) Endpoints
# =========================
@app.get("/")
def read_root():
    return {"message": "Welcome to YOLO Inference API. Visit /yolo/docs to test."}

@app.get("/healthz")
def health_check():
    ok = bool(_yolo_model is not None)
    return {"status": "healthy" if ok else "not_ready", "model_loaded": ok}

@app.get("/model/info")
def model_info():
    return {
        "model_path": str(MODEL_PATH),
        "device": DEVICE,
        "conf": CONF,
        "iou": IOU,
        "img_size": IMG_SIZE,
        "class_names": _yolo_names,
    }

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    ensure_model_loaded()
    with tracer.start_as_current_span("predict") as main_span:

        # Validate image
        with tracer.start_as_current_span("validate-image", links=[Link(main_span.get_span_context())]):
            image_bytes = await file.read()
            try:
                pil_img = Image.open(BytesIO(image_bytes)).convert("RGB")
            except UnidentifiedImageError:
                raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

        # Inference
        with tracer.start_as_current_span("yolo-infer", links=[Link(main_span.get_span_context())]):
            start = time()
            try:
                results = _yolo_model.predict(
                    pil_img,
                    imgsz=IMG_SIZE,
                    conf=CONF,
                    iou=IOU,
                    device=DEVICE if DEVICE == "cuda" else None,
                    verbose=False,
                )
            except Exception as e:
                logger.exception("YOLO inference failed")
                raise HTTPException(status_code=500, detail=f"Inference error: {e}")
            elapsed = time() - start

        # Postprocess
        with tracer.start_as_current_span("postprocess", links=[Link(main_span.get_span_context())]):
            result = results[0]
            width, height = result.orig_shape[1], result.orig_shape[0]
            detections = _parse_result(result)

        # Metrics
        labels = {"api": "/predict"}
        inference_counter.add(1, labels)
        inference_histogram.record(elapsed, labels)
        if yolo_response_time_summary is not None:
            yolo_response_time_summary.observe(elapsed)
        if yolo_num_detections_gauge is not None:
            yolo_num_detections_gauge.set(len(detections))

        logger.info(f"Inference completed in {elapsed:.4f}s with {len(detections)} detections")

        return {
            "model": {"path": str(MODEL_PATH), "device": DEVICE},
            "image": {"width": width, "height": height},
            "inference": {"time_seconds": elapsed, "detections": len(detections)},
            "detections": detections,
        }

@app.post("/predict/annotated")
async def predict_annotated(file: UploadFile = File(...)):
    """
    Trả ảnh PNG đã vẽ bbox và **đồng thời lưu** ảnh kết quả vào thư mục ./results.
    Header 'X-Saved-Path' cho biết đường dẫn tuyệt đối của file đã lưu.
    """
    ensure_model_loaded()
    with tracer.start_as_current_span("predict-annotated") as main_span:

        # Validate image
        with tracer.start_as_current_span("validate-image", links=[Link(main_span.get_span_context())]):
            image_bytes = await file.read()
            try:
                pil_img = Image.open(BytesIO(image_bytes)).convert("RGB")
            except UnidentifiedImageError:
                raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

        # Inference
        with tracer.start_as_current_span("yolo-infer", links=[Link(main_span.get_span_context())]):
            start = time()
            try:
                results = _yolo_model.predict(
                    pil_img,
                    imgsz=IMG_SIZE,
                    conf=CONF,
                    iou=IOU,
                    device=DEVICE if DEVICE == "cuda" else None,
                    verbose=False,
                )
            except Exception as e:
                logger.exception("YOLO inference failed")
                raise HTTPException(status_code=500, detail=f"Inference error: {e}")
            elapsed = time() - start

        # Render annotated PNG
        with tracer.start_as_current_span("render", links=[Link(main_span.get_span_context())]):
            annotated_png = _annotate_image(results[0])

        # Save annotated image to ./results
        ts = int(time() * 1000)
        stem = Path(file.filename).stem if file.filename else "image"
        save_name = f"{stem}_{ts}.png"
        save_path = (RESULTS_DIR / save_name).resolve()
        try:
            with open(save_path, "wb") as f:
                f.write(annotated_png)
            logger.info(f"Saved annotated image to {save_path}")
        except Exception as e:
            logger.warning(f"Failed to save annotated image: {e}")

        # Metrics
        labels = {"api": "/predict/annotated"}
        inference_counter.add(1, labels)
        inference_histogram.record(elapsed, labels)
        if yolo_response_time_summary is not None:
            yolo_response_time_summary.observe(elapsed)
        if yolo_num_detections_gauge is not None:
            yolo_num_detections_gauge.set(int(results[0].boxes.shape[0]) if results[0].boxes is not None else 0)

        return StreamingResponse(BytesIO(annotated_png), media_type="image/png",
                                 headers={"X-Saved-Path": str(save_path)})


# =========================
# 5) Entrypoint (dev run)
# =========================
if __name__ == "__main__":
    # Mở HTTP server cho Prometheus – bọc try để tránh crash nếu port bận
    try:
        start_http_server(port=PROM_PORT, addr="0.0.0.0")
        logger.info(f"Prometheus metrics server started on :{PROM_PORT}")
    except OSError as e:
        logger.warning(f"Prometheus port busy, skip starting metrics server: {e}")

    # Khởi tạo Prometheus client metrics đúng 1 lần
    yolo_num_detections_gauge = Gauge(
        "yolo_num_detections",
        "Number of detections produced by YOLO for the last request",
    )
    yolo_response_time_summary = Summary(
        "yolo_response_time_summary_seconds",
        "Summary of YOLO inference response time",
    )

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))

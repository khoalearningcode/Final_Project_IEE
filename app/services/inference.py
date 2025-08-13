from __future__ import annotations

from io import BytesIO
from pathlib import Path
from time import time
from typing import List, Optional

import numpy as np
from fastapi import HTTPException, Request
from loguru import logger
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO

from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider as SDKMeterProvider
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

from app.config import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL_NAME,
    CONF,
    IOU,
    IMG_SIZE,
    DEVICE,
    SERVICE_NAME_STR,
)
from app.services.storage import save_result_bytes, make_item_dir

# ===== Runtime model state =====
_loaded_model: Optional[YOLO] = None
_loaded_model_name: Optional[str] = None
_class_names: List[str] = []

# ===== Tracing =====
from app.services.tracing import setup_tracing
tracer = setup_tracing()

# ===== Metrics (OTel) =====
otel_resource = Resource(attributes={SERVICE_NAME: SERVICE_NAME_STR})
reader = PrometheusMetricReader()
current_mp = metrics.get_meter_provider()
if not isinstance(current_mp, SDKMeterProvider):
    provider_metrics = SDKMeterProvider(resource=otel_resource, metric_readers=[reader])
    set_meter_provider(provider_metrics)

meter = metrics.get_meter("inference", "0.1.0")
inference_counter = meter.create_counter(
    name="inference_requests_total",
    description="Number of inference requests",
)
inference_hist = meter.create_histogram(
    name="inference_latency_seconds",
    description="Latency for inference",
    unit="s",
)

# ===== Optional Prometheus client metrics (plain) =====
_det_gauge = None
_resp_summary = None


def set_prom_client(det_gauge, resp_summary) -> None:
    """Cho phép main.py gắn Gauge/Summary nếu muốn."""
    global _det_gauge, _resp_summary
    _det_gauge = det_gauge
    _resp_summary = resp_summary


def resolve_requested_model(request: Optional[Request]) -> Optional[str]:
    """Ưu tiên: ?model=<name> > Header X-Model-Name."""
    if not request:
        return None
    q = request.query_params.get("model")
    if q:
        return q
    h = request.headers.get("X-Model-Name")
    if h:
        return h
    return None


def load_model(name: Optional[str] = None) -> None:
    """Lazy-load/hot-swap YOLO model."""
    global _loaded_model, _loaded_model_name, _class_names

    req_name = name or _loaded_model_name or DEFAULT_MODEL_NAME
    if req_name not in AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{req_name}'. Available: {list(AVAILABLE_MODELS.keys())}",
        )

    if _loaded_model is not None and _loaded_model_name == req_name:
        return

    model_path = AVAILABLE_MODELS[req_name]
    if not model_path.exists():
        raise RuntimeError(f"Model file not found at {model_path}")

    logger.info(f"Loading model: {model_path} (device={DEVICE})")
    model = YOLO(str(model_path))
    try:
        model.to(DEVICE)
    except Exception as e:
        logger.warning(f"Could not move model to device {DEVICE}: {e}")

    _loaded_model = model
    _loaded_model_name = req_name
    _class_names = getattr(model, "names", [])
    logger.info(f"Model loaded: '{req_name}' → {model_path}. Classes: {_class_names or 'unknown'}")


def current_model_path() -> Path:
    name = _loaded_model_name or DEFAULT_MODEL_NAME
    return AVAILABLE_MODELS[name]


def parse_result(result) -> List[dict]:
    """Ultralytics result -> list[dict]."""
    dets: List[dict] = []
    if getattr(result, "boxes", None) is None:
        return dets

    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    clss = result.boxes.cls.cpu().numpy()

    for i in range(len(confs)):
        cls_id = int(clss[i])
        dets.append(
            {
                "class_id": cls_id,
                "class_name": (
                    _class_names[cls_id]
                    if _class_names and 0 <= cls_id < len(_class_names)
                    else str(cls_id)
                ),
                "confidence": float(confs[i]),
                "bbox_xyxy": [float(x) for x in boxes_xyxy[i].tolist()],
            }
        )
    return dets


def annotate_image(result) -> bytes:
    """Render predictions -> PNG bytes (RGB)."""
    im_bgr = result.plot()
    rgb = np.ascontiguousarray(im_bgr[:, :, ::-1])
    img = Image.fromarray(rgb)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def infer_pil(pil_img: Image.Image):
    """Infer 1 ảnh PIL, trả (w, h, elapsed, dets, res0)."""
    with tracer.start_as_current_span("infer_image"):
        start = time()
        results = _loaded_model.predict(
            pil_img,
            imgsz=IMG_SIZE,
            conf=CONF,
            iou=IOU,
            device=DEVICE if DEVICE == "cuda" else None,
            verbose=False,
        )
        elapsed = time() - start
        res0 = results[0]
        w, h = res0.orig_shape[1], res0.orig_shape[0]
        dets = parse_result(res0)
        return w, h, elapsed, dets, res0


def record_metrics(api_label: str, elapsed: float, det_count: int) -> None:
    labels = {"api": api_label, "model": _loaded_model_name or ""}
    inference_counter.add(1, labels)
    inference_hist.record(elapsed, labels)
    if _resp_summary:
        _resp_summary.observe(elapsed)
    if _det_gauge is not None:
        _det_gauge.set(det_count)


def save_prediction_payload(
    stem: str,
    ts_ms: int,
    payload: dict,
    annotated_png: bytes | None,
):
    base_dir = make_item_dir(_loaded_model_name, stem, ts_ms)

    # JSON
    json_bytes = (__import__("json")).dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    json_meta = save_result_bytes(f"{base_dir}/result.json", json_bytes, "application/json")

    png_meta = None
    if annotated_png is not None:
        png_meta = save_result_bytes(f"{base_dir}/annotated.png", annotated_png, "image/png")

    return json_meta, png_meta, base_dir

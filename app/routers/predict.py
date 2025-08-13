from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from time import time
from typing import List

import requests
from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from PIL import Image, UnidentifiedImageError

from app.schemas.predict import (
    UrlPredictIn,
    GCSPredictIn,
    PredictOut,
    ImageInfo,
    InferenceInfo,
    Detection,
)
from app.services.inference import (
    resolve_requested_model,
    load_model,
    current_model_path,
    infer_pil,
    annotate_image,
    parse_result,
    record_metrics,
    save_prediction_payload,
)
from app.config import CONF, IOU, IMG_SIZE
from app.utils import parse_gcs_input, download_bytes  # giữ utils của bạn

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("/image", response_model=PredictOut)
async def predict_image(
    request: Request,
    file: UploadFile = File(...),
    annotated: bool = True,
):
    req_model = resolve_requested_model(request)
    load_model(req_model)

    data = await file.read()
    try:
        pil = Image.open(BytesIO(data)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

    w, h, elapsed, dets, res0 = infer_pil(pil)
    record_metrics("/predict/image", elapsed, len(dets))

    ts = int(time() * 1000)
    stem = Path(file.filename).stem if file.filename else "image"

    resp = {
        "model": {
            "name": req_model,
            "path": str(current_model_path()),
            "device": "cuda" if req_model else "cpu",
            "params": {"imgsz": IMG_SIZE, "conf": CONF, "iou": IOU},
        },
        "image": {"width": w, "height": h},
        "inference": {"time_seconds": elapsed, "detections": len(dets)},
        "detections": dets,
        "web_path": None,
        "gcs": None,
    }

    png_bytes = annotate_image(res0) if annotated else None
    json_meta, png_meta, _ = save_prediction_payload(stem, ts, resp, png_bytes)

    out = resp.copy()
    out["result_json"] = json_meta
    if png_meta:
        out["web_path"] = png_meta.get("web_path")
        out["gcs"] = png_meta.get("gcs")
    return out


@router.post("/images")
async def predict_images(
    request: Request,
    files: List[UploadFile] = File(...),
    annotated: bool = True,
):
    req_model = resolve_requested_model(request)
    load_model(req_model)

    results = []
    for f in files:
        try:
            b = await f.read()
            pil = Image.open(BytesIO(b)).convert("RGB")
            w, h, elapsed, dets, res0 = infer_pil(pil)
            record_metrics("/predict/images", elapsed, len(dets))

            ts = int(time() * 1000)
            stem = Path(f.filename).stem if f.filename else "image"
            item = {
                "filename": f.filename,
                "ok": True,
                "image": {"width": w, "height": h},
                "inference": {"time_seconds": elapsed, "detections": len(dets)},
                "detections": dets,
                "web_path": None,
                "gcs": None,
            }

            png_bytes = annotate_image(res0) if annotated else None
            json_meta, png_meta, _ = save_prediction_payload(stem, ts, item, png_bytes)
            item["result_json"] = json_meta
            if png_meta:
                item["web_path"] = png_meta.get("web_path")
                item["gcs"] = png_meta.get("gcs")

            results.append(item)
        except UnidentifiedImageError:
            results.append({"filename": f.filename, "ok": False, "error": "Invalid image file"})
        except Exception as e:
            results.append({"filename": f.filename, "ok": False, "error": str(e)})

    return {"count": len(results), "results": results}


@router.post("/url", response_model=PredictOut)
def predict_url(
    request: Request,
    body: UrlPredictIn,
):
    req_model = resolve_requested_model(request)
    load_model(req_model)

    r = requests.get(body.url, timeout=20)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Download failed: HTTP {r.status_code}")

    try:
        pil = Image.open(BytesIO(r.content)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Downloaded file is not a valid image.")

    w, h, elapsed, dets, res0 = infer_pil(pil)
    record_metrics("/predict/url", elapsed, len(dets))

    ts = int(time() * 1000)
    stem = Path(body.url).stem or "image"

    resp = {
        "source": body.url,
        "image": {"width": w, "height": h},
        "inference": {"time_seconds": elapsed, "detections": len(dets)},
        "detections": dets,
        "web_path": None,
        "gcs": None,
    }

    png_bytes = annotate_image(res0) if body.annotated else None
    json_meta, png_meta, _ = save_prediction_payload(stem, ts, resp, png_bytes)

    out = resp.copy()
    out["result_json"] = json_meta
    if png_meta:
        out["web_path"] = png_meta.get("web_path")
        out["gcs"] = png_meta.get("gcs")
    return out


@router.post("/gcs")
def predict_gcs(
    request: Request,
    body: GCSPredictIn,
):
    req_model = resolve_requested_model(request)
    load_model(req_model)

    bucket, obj_path = parse_gcs_input(body.source)
    try:
        image_bytes = download_bytes(bucket, obj_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot read from GCS: {e}")

    try:
        pil = Image.open(BytesIO(image_bytes)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Object is not a valid image.")

    w, h, elapsed, dets, res0 = infer_pil(pil)
    record_metrics("/predict/gcs", elapsed, len(dets))

    ts = int(time() * 1000)
    stem = Path(obj_path).stem or "image"

    resp = {
        "source": {"bucket": bucket, "path": obj_path},
        "model": {
            "name": req_model,
            "path": str(current_model_path()),
            "device": "cuda" if req_model else "cpu",
            "params": {"imgsz": IMG_SIZE, "conf": CONF, "iou": IOU},
        },
        "image": {"width": w, "height": h},
        "inference": {"time_seconds": elapsed, "detections": len(dets)},
        "detections": dets,
    }

    png_bytes = annotate_image(res0) if body.annotated else None
    json_meta, png_meta, _ = save_prediction_payload(stem, ts, resp, png_bytes)

    return {
        "ok": True,
        "from": {"bucket": bucket, "path": obj_path},
        "json_result": json_meta,
        "annotated_result": png_meta,
    }

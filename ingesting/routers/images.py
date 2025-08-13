from __future__ import annotations
from io import BytesIO
from typing import List

import requests
from fastapi import APIRouter, File, HTTPException, UploadFile, Form
import mimetypes
from PIL import Image, UnidentifiedImageError

from ingesting.schemas.image import UrlIn, PushImageOut, PushImagesOut
from ingesting.services.uploader import upload_single_image
from ingesting.services.tracing import trace

router = APIRouter(tags=["ingest"])

@router.post("/push_image", response_model=PushImageOut)
async def push_image(file: UploadFile = File(...)) -> dict:
    image_bytes = await file.read()
    return upload_single_image(
        tracer=trace.get_tracer_provider().get_tracer("ingesting", "0.1.1"),
        filename=file.filename,
        content_type=file.content_type,
        image_bytes=image_bytes,
        source="api",
    )

@router.post("/push_images", response_model=PushImagesOut)
async def push_images(files: List[UploadFile] = File(...)) -> dict:
    results = []
    tracer = trace.get_tracer_provider().get_tracer("ingesting", "0.1.1")
    for f in files:
        try:
            b = await f.read()
            res = upload_single_image(
                tracer=tracer,
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

@router.post("/push_image_url", response_model=PushImageOut)
async def push_image_url_form(
    url: str = Form(..., description="Public image URL"),
) -> dict:
    """
    Gửi form-data với field 'url' (giống style của /push_images):
      - Content-Type: multipart/form-data
      - field name: url
    """
    tracer = trace.get_tracer_provider().get_tracer("ingesting", "0.1.1")

    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Download failed: HTTP {r.status_code}")
    image_bytes = r.content
    content_type = r.headers.get("Content-Type")

    guessed_name = url.split("?")[0].split("/")[-1] or "remote.jpg"
    if "." not in guessed_name:
        ext = (mimetypes.guess_extension(content_type or "") or ".jpg").lstrip(".")
        guessed_name = f"remote.{ext}"

    return upload_single_image(
        tracer=tracer,
        filename=guessed_name,
        content_type=content_type,
        image_bytes=image_bytes,
        source="url",
    )
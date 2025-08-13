from __future__ import annotations
import datetime
import uuid
from io import BytesIO
from time import time
from typing import Optional, Tuple

from fastapi import HTTPException
from loguru import logger
from PIL import Image, UnidentifiedImageError
from opentelemetry import trace
from opentelemetry.trace import Link

from ingesting.config import (
    GCS_BUCKET_NAME,
    ALLOWED_IMAGE_EXT,
    IMAGES_API_PREFIX,
    IMAGES_URL_PREFIX,
)
from ingesting.utils import get_storage_client  # giữ util của bạn

# GCS bucket (init 1 lần)
_storage_client = get_storage_client()
_bucket = _storage_client.get_bucket(GCS_BUCKET_NAME)

def _validate_image(filename: str, image_bytes: bytes) -> Tuple[str, None]:
    ext = (filename or "").split(".")[-1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="Only .jpg/.jpeg/.png allowed")
    try:
        Image.open(BytesIO(image_bytes)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Invalid image file")
    return ext, None

def upload_single_image(
    tracer: trace.Tracer,
    filename: str,
    content_type: Optional[str],
    image_bytes: bytes,
    source: str = "api",
):
    """
    Validate & upload 1 ảnh lên GCS, trả metadata + signed_url nếu tạo được.
    """
    start_time = time()
    with tracer.start_as_current_span("push_image") as push_span:

        with tracer.start_as_current_span("validate-image", links=[Link(push_span.get_span_context())]):
            ext, _ = _validate_image(filename, image_bytes)

        prefix = IMAGES_API_PREFIX if source == "api" else IMAGES_URL_PREFIX
        file_id = str(uuid.uuid4())
        gcs_path = f"{prefix}/{file_id}.{ext}"
        gs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_path}"

        with tracer.start_as_current_span("upload-to-gcs", links=[Link(push_span.get_span_context())]):
            blob = _bucket.blob(gcs_path)
            try:
                blob.upload_from_string(image_bytes, content_type=content_type or f"image/{ext}")
                logger.info(f"Uploaded image to GCS: {gcs_path}")
            except Exception as e:
                logger.error(f"GCS upload failed: {e}")
                raise HTTPException(status_code=500, detail="GCS upload failed")

        signed_url: Optional[str] = None
        with tracer.start_as_current_span("generate-signed-url", links=[Link(push_span.get_span_context())]):
            try:
                response_disposition = f"attachment; filename={filename}"
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(hours=1),
                    method="GET",
                    response_disposition=response_disposition,
                )
            except Exception as e:
                # fallback: None nếu không có quyền ký
                signed_url = None
                logger.warning(f"Signed URL generation failed (image): {e}")

    elapsed = time() - start_time
    return {
        "message": "Successfully!",
        "file_id": file_id,
        "gcs_path": gcs_path,
        "gs_uri": gs_uri,
        "signed_url": signed_url,
        "elapsed_seconds": elapsed,
    }

# gcs_utils.py
import datetime
import mimetypes
import os
from typing import Optional, Tuple

from google.cloud import storage
from google.auth import default as gauth_default

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")

def get_storage_client() -> storage.Client:
    # Dùng ADC (Application Default Credentials)
    # Cần mount service account key qua GOOGLE_APPLICATION_CREDENTIALS khi chạy k8s/docker (nếu bucket private)
    return storage.Client()

def parse_gcs_input(s: str) -> Tuple[str, str]:
    """
    Hỗ trợ:
      - gs://bucket/path/to/file.jpg  -> (bucket, path)
      - https://storage.googleapis.com/bucket/path/to/file.jpg -> (bucket, path)
      - https://console.cloud.google.com/storage/browser/_details/bucket/path/file.jpg (khử prefix UI) -> (bucket, path)
    """
    s = s.strip()
    if s.startswith("gs://"):
        # gs://bucket/objpath
        rest = s[5:]
        bucket, path = rest.split("/", 1)
        return bucket, path
    if "storage.googleapis.com" in s:
        # https://storage.googleapis.com/bucket/objpath
        parts = s.split("storage.googleapis.com/", 1)[1]
        bucket, path = parts.split("/", 1)
        return bucket, path
    if "console.cloud.google.com/storage/browser" in s:
        # dạng UI: .../_details/<bucket>/<path>?...
        # cắt sau "_details/"
        if "_details/" in s:
            suffix = s.split("_details/", 1)[1]
        else:
            suffix = s.split("browser/", 1)[1]
        suffix = suffix.split("?")[0]
        bucket, path = suffix.split("/", 1)
        return bucket, path
    # Mặc định: coi 's' là path tương đối trong bucket ENV
    return (GCS_BUCKET_NAME, s.lstrip("/"))

def download_bytes(bucket_name: str, blob_path: str) -> bytes:
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    return blob.download_as_bytes()

def upload_bytes(
    data: bytes,
    blob_path: str,
    content_type: Optional[str] = None,
    signed_url_hours: int = 24,
) -> dict:
    """
    Upload bytes -> GCS. Trả:
      {
        "bucket": ..., "path": ...,
        "gs_uri": "gs://bucket/path",
        "public_url": "https://storage.googleapis.com/bucket/path",  # nếu bucket public
        "signed_url": "...",  # nếu có thể ký
    }"""
    client = get_storage_client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_path)
    if not content_type:
        content_type = mimetypes.guess_type(blob_path)[0] or "application/octet-stream"
    blob.upload_from_string(data, content_type=content_type)

    out = {
        "bucket": GCS_BUCKET_NAME,
        "path": blob_path,
        "gs_uri": f"gs://{GCS_BUCKET_NAME}/{blob_path}",
        "public_url": blob.public_url,  # sẽ dùng được nếu bucket public
        "signed_url": None,
    }
    try:
        out["signed_url"] = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=signed_url_hours),
            method="GET",
            response_disposition=f'inline; filename="{os.path.basename(blob_path)}"',
        )
    except Exception:
        # Không có quyền ký hoặc ADC không phải key file => bỏ qua
        pass
    return out

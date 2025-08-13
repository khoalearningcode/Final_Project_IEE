from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict

from app.config import RESULTS_DIR, STORAGE_BACKEND, RESULTS_PREFIX, SIGNED_URL_EXP_HOURS
from app.utils import upload_bytes  # giữ utils của bạn
from loguru import logger


def save_result_bytes(rel_path: str, data: bytes, content_type: str) -> Dict[str, Optional[dict | str]]:
    """
    Lưu byte theo backend.
    Trả: {"web_path": Optional[str], "gcs": Optional[dict]}
    """
    rel_path = rel_path.lstrip("/")
    web_path = None
    gcs_meta = None

    if STORAGE_BACKEND in ("local", "both"):
        save_path = (RESULTS_DIR / rel_path).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(data)
        fixed = rel_path.replace("\\", "/")
        web_path = f"/results/{fixed}"

    if STORAGE_BACKEND in ("gcs", "both"):
        gcs_path = f"{RESULTS_PREFIX}/{rel_path}"
        try:
            gcs_meta = upload_bytes(
                data,
                gcs_path,
                content_type=content_type,
                signed_url_hours=SIGNED_URL_EXP_HOURS,
            )
        except Exception as e:
            logger.error(f"GCS upload failed for {gcs_path}: {e}")
            gcs_meta = None

    return {"web_path": web_path, "gcs": gcs_meta}


def make_item_dir(model_name: str | None, stem: str, ts_ms: int) -> str:
    """Folder kết quả cho từng input."""
    return f"{(model_name or 'model')}/{stem}_{ts_ms}"

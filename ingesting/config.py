# config.py
import os

class Config:
    # ===== GCS only =====
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "")
    SIGNED_URL_EXP_HOURS: int = int(os.getenv("SIGNED_URL_EXP_HOURS", "24"))

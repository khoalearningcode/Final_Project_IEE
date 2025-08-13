from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

import torch
from dotenv import load_dotenv, find_dotenv
from loguru import logger

# Load .env sớm để các module khác dùng
load_dotenv(find_dotenv() or "../.env")

# ===== Paths =====
BASE_DIR: Path = Path(__file__).resolve().parent
MODELS_DIR: Path = (BASE_DIR / "models").resolve()
RESULTS_DIR: Path = (BASE_DIR / "results").resolve()
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ===== Models =====
AVAILABLE_MODELS: Dict[str, Path] = {
    p.stem: p.resolve()
    for p in MODELS_DIR.glob("*.*")
    if p.suffix.lower() in (".pt",)  # mở rộng thêm nếu hỗ trợ loader khác
}
if not AVAILABLE_MODELS:
    logger.warning("No model files found in ./models directory")

_env_model = os.getenv("MODEL_NAME")
if _env_model and _env_model in AVAILABLE_MODELS:
    DEFAULT_MODEL_NAME: Optional[str] = _env_model
elif "yolo12m" in AVAILABLE_MODELS:
    DEFAULT_MODEL_NAME = "yolo12m"
else:
    DEFAULT_MODEL_NAME = next(iter(AVAILABLE_MODELS), None)

if DEFAULT_MODEL_NAME is None:
    raise RuntimeError("No models available. Put at least one .pt in ./models/")

# ===== Inference params =====
CONF: float = float(os.getenv("CONF", "0.25"))
IOU: float = float(os.getenv("IOU", "0.45"))
IMG_SIZE: int = int(os.getenv("IMG_SIZE", "640"))
DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"

# ===== Tracing / Metrics =====
JAEGER_HOST: str = os.getenv(
    "JAEGER_HOST", "jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local"
)
JAEGER_PORT: int = int(os.getenv("JAEGER_PORT", "6831"))
PROM_PORT: int = int(os.getenv("PROM_PORT", "8097"))
TRACING_MODE: str = os.getenv("TRACING", "auto").lower()  # auto|on|off

# ===== Storage =====
STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local").lower()  # local|gcs|both
SIGNED_URL_EXP_HOURS: int = int(os.getenv("SIGNED_URL_EXP_HOURS", "24"))
RESULTS_PREFIX: str = os.getenv("RESULTS_PREFIX", "results")

SERVICE_NAME_STR: str = "inference-service"

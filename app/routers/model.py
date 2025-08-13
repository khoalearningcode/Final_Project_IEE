from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import AVAILABLE_MODELS, CONF, IOU, IMG_SIZE
from app.services.inference import load_model, _loaded_model_name, current_model_path, _class_names
from app.schemas.model import ModelInfo

router = APIRouter(prefix="/model", tags=["model"])


@router.post("/select", response_model=ModelInfo)
def model_select(
    name: str = Query(..., description="Chọn model", enum=sorted(AVAILABLE_MODELS.keys()))
):
    if name not in AVAILABLE_MODELS:
        raise HTTPException(status_code=404, detail=f"Model '{name}' không tồn tại")
    load_model(name)
    return ModelInfo(
        name=_loaded_model_name,
        path=str(current_model_path()),
        device="cuda" if name else "cpu",
        conf=CONF,
        iou=IOU,
        img_size=IMG_SIZE,
        class_names=_class_names or [],
    )

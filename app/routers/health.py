from __future__ import annotations

from fastapi import APIRouter

from app.services.inference import _loaded_model

router = APIRouter()


@router.get("/")
def read_root():
    return {"message": "Welcome to Inference API. Visit /detection/docs to test."}


@router.get("/healthz")
def health_check():
    ok = bool(_loaded_model is not None)
    return {"status": "healthy" if ok else "not_ready", "model_loaded": ok}

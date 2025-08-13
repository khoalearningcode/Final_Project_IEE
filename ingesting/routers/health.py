from __future__ import annotations
import os
from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

router = APIRouter(tags=["health"])

@router.get("/")
def read_root() -> dict:
    return {"message": "Welcome to the Image Ingestion API. Visit /ingesting/docs to test."}

@router.get("/healthz")
def health_check() -> dict:
    return {"status": "healthy"}

@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = "static/favicon.ico"
    if os.path.exists(path):
        return FileResponse(path)
    return Response(status_code=204)

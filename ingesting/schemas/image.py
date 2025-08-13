from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl

class UrlIn(BaseModel):
    url: HttpUrl = Field(..., description="Public image URL", examples=[""])

class PushImageOut(BaseModel):
    message: str
    file_id: str
    gcs_path: str
    gs_uri: str
    signed_url: Optional[str] = None
    elapsed_seconds: float

class PushImagesOut(BaseModel):
    count: int
    results: List[dict]

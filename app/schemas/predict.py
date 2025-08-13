from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class UrlPredictIn(BaseModel):
    url: str = Field(..., description="Image URL", examples=[""])
    annotated: bool = True


class GCSPredictIn(BaseModel):
    source: str = Field(..., description="gs://... or GCS URL", examples=["gs://bucket/path/to/img.jpg"])
    annotated: bool = True


class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: List[float]


class ImageInfo(BaseModel):
    width: int
    height: int


class InferenceInfo(BaseModel):
    time_seconds: float
    detections: int


class PredictOut(BaseModel):
    model: Optional[dict] = None
    image: Optional[ImageInfo] = None
    inference: Optional[InferenceInfo] = None
    detections: List[Detection] = []
    web_path: Optional[str] = None
    gcs: Optional[dict] = None
    result_json: Optional[dict] = None

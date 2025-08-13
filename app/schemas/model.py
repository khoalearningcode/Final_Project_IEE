from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ModelInfo(BaseModel):
    name: Optional[str]
    path: str
    device: str
    conf: float
    iou: float
    img_size: int
    class_names: List[str] = []

# tests/test_predict_endpoints.py
import io
import base64
from typing import Tuple
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np

# App FastAPI phải được expose tại app.main: app
from app.main import app

client = TestClient(app)



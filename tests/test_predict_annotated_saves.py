import io, os
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np
from app.main import app

client = TestClient(app)

def make_img():
    im = Image.new("RGB", (64, 64), (123, 123, 123))
    buf = io.BytesIO(); im.save(buf, format="PNG"); buf.seek(0)
    return buf

def test_predict_annotated_saves(monkeypatch, tmp_path):
    mp = monkeypatch  # alias ngắn gọn

    class ND:
        def __init__(self, arr): self._arr = np.array(arr, dtype=float)
        def cpu(self): return self
        def numpy(self): return self._arr

    class Boxes:
        def __init__(self):
            self.xyxy = ND([[5, 5, 40, 40]])
            self.conf = ND([0.8])
            self.cls  = ND([0])
        @property
        def shape(self): return (1,)


    class Result:
        def __init__(self): self.boxes = Boxes(); self.orig_shape = (64, 64, 3)
        def plot(self): return np.zeros((64, 64, 3), dtype=np.uint8)

    class Model:
        names = {0: "class0"}
        def predict(self, *a, **k): return [Result()]

    mp.setattr("app.main._yolo_model", Model(), raising=False)
    mp.setattr("app.main._yolo_names", ["class0"], raising=False)

    # chuyển RESULTS_DIR sang tmp_path để test ghi file
    mp.setattr("app.main.RESULTS_DIR", tmp_path, raising=False)

    r = client.post("/predict/annotated", files={"file": ("t.png", make_img(), "image/png")})
    assert r.status_code == 200
    assert r.headers.get("content-type") == "image/png"
    saved = r.headers.get("X-Saved-Path")
    assert saved and os.path.exists(saved)

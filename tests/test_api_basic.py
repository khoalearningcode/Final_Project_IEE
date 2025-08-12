import io
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np
from app.main import app

client = TestClient(app)

def make_img(w=320, h=240, color=(200, 200, 200)):
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO(); im.save(buf, format="PNG"); buf.seek(0)
    return buf

def test_root_and_health():
    assert client.get("/").status_code == 200
    assert client.get("/healthz").status_code == 200

def test_predict_with_mock(monkeypatch):
    import numpy as np

    class ND:
        def __init__(self, arr): self._arr = np.array(arr, dtype=float)
        def cpu(self): return self
        def numpy(self): return self._arr

    class Boxes:
        def __init__(self):
            self.xyxy = ND([[10, 20, 100, 120]])
            self.conf = ND([0.9])
            self.cls  = ND([0])

    class Result:
        def __init__(self):
            self.boxes = Boxes()
            self.orig_shape = (240, 320, 3)
        def plot(self): return np.zeros((240, 320, 3), dtype=np.uint8)

    class Model:
        names = {0: "class0"}
        def predict(self, *a, **k): return [Result()]

    monkeypatch.setattr("app.main._yolo_model", Model(), raising=False)
    monkeypatch.setattr("app.main._yolo_names", ["class0"], raising=False)

    r = client.post("/predict", files={"file": ("a.png", make_img(), "image/png")})
    assert r.status_code == 200

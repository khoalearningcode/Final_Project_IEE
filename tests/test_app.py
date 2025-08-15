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


def make_png_bytes(w=320, h=240, color=(200, 200, 200)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def stub_infer_pil_return() -> Tuple[int, int, float, list, object]:
    """
    Giá trị giả lập cho infer_pil:
      width=320, height=240, elapsed=0.01, detections=[], res0=object()
    Trả detections = [] để tương thích chặt với mọi schema Detection.
    """
    return 320, 240, 0.01, [], object()


# ---------- /predict/image ----------
def test_predict_image_ok(monkeypatch):
    # Patch đúng module nơi endpoint gọi các hàm (giả sử router ở app.routers.predict)
    monkeypatch.setattr("app.routers.predict.resolve_requested_model", lambda req: "mock-model", raising=False)
    monkeypatch.setattr("app.routers.predict.load_model", lambda name: None, raising=False)
    monkeypatch.setattr("app.routers.predict.current_model_path", lambda: "/models/mock.pt", raising=False)
    monkeypatch.setattr("app.routers.predict.infer_pil", lambda pil: (320, 240, 0.01, [], object()), raising=False)
    monkeypatch.setattr("app.routers.predict.annotate_image", lambda res0: b"\x89PNG\r\n", raising=False)
    monkeypatch.setattr("app.routers.predict.record_metrics", lambda *a, **k: None, raising=False)

    # Trả về đường dẫn cố định để assertion exact, tránh phụ thuộc timestamp
    monkeypatch.setattr(
        "app.routers.predict.save_prediction_payload",
        lambda stem, ts, resp, png: (
            {"web_path": f"/static/{stem}.json"},
            {"web_path": f"/static/{stem}.png", "gcs": {"bucket": "bkt", "path": "p.png"}},
            None,
        ),
        raising=False,
    )

    files = {"file": ("a.png", make_png_bytes(), "image/png")}
    r = client.post("/predict/image", files=files)
    assert r.status_code == 200, r.text
    body = r.json()

    # Assertions ổn định (không phụ thuộc thời gian)
    assert body["image"]["width"] == 320
    assert body["image"]["height"] == 240
    assert "result_json" in body
    assert body.get("web_path") == "/static/a.png"
    assert body.get("gcs") == {"bucket": "bkt", "path": "p.png"}



def test_predict_image_invalid_bytes(monkeypatch):
    # Chỉ cần để PIL lỗi là đủ -> server trả 400
    monkeypatch.setattr("app.services.inference.resolve_requested_model", lambda req: "mock-model")
    monkeypatch.setattr("app.services.inference.load_model", lambda name: None)

    # Gửi file không phải ảnh
    files = {"file": ("x.txt", b"not image", "text/plain")}
    r = client.post("/predict/image", files=files)
    assert r.status_code == 400, r.text
    assert "not a valid image" in r.text or "Invalid" in r.text


# ---------- /predict/images ----------
def test_predict_images_batch(monkeypatch):
    monkeypatch.setattr("app.services.inference.resolve_requested_model", lambda req: "mock-model")
    monkeypatch.setattr("app.services.inference.load_model", lambda name: None)
    monkeypatch.setattr("app.services.inference.infer_pil", lambda pil: stub_infer_pil_return())
    monkeypatch.setattr("app.services.inference.annotate_image", lambda res0: b"\x89PNG\r\n")
    monkeypatch.setattr(
        "app.services.inference.save_prediction_payload",
        lambda stem, ts, resp, png: (
            {"web_path": f"/static/{stem}.json"},
            {"web_path": f"/static/{stem}.png", "gcs": {"bucket": "bkt", "path": f"{stem}.png"}},
            None,
        ),
    )
    monkeypatch.setattr("app.services.inference.record_metrics", lambda *a, **k: None)

    files = [
        ("files", ("a.png", make_png_bytes(), "image/png")),
        ("files", ("b.png", make_png_bytes(), "image/png")),
    ]
    r = client.post("/predict/images", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2
    assert len(body["results"]) == 2
    assert all(item["ok"] for item in body["results"])


# ---------- /predict/url ----------
def test_predict_url_ok(monkeypatch):
    # Giả lập tải ảnh từ URL thành công
    class Resp:
        status_code = 200
        content = make_png_bytes()

    monkeypatch.setattr("requests.get", lambda url, timeout=20: Resp())
    monkeypatch.setattr("app.services.inference.resolve_requested_model", lambda req: "mock-model")
    monkeypatch.setattr("app.services.inference.load_model", lambda name: None)
    monkeypatch.setattr("app.services.inference.infer_pil", lambda pil: stub_infer_pil_return())
    monkeypatch.setattr("app.services.inference.annotate_image", lambda res0: b"\x89PNG\r\n")
    monkeypatch.setattr(
        "app.services.inference.save_prediction_payload",
        lambda stem, ts, resp, png: (
            {"web_path": f"/static/{stem}.json"},
            {"web_path": f"/static/{stem}.png", "gcs": {"bucket": "bkt", "path": f"{stem}.png"}},
            None,
        ),
    )
    monkeypatch.setattr("app.services.inference.record_metrics", lambda *a, **k: None)

    data = {"annotated": "true", "url": "https://example.com/img.png"}
    r = client.post("/predict/url", data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["image"]["width"] == 320
    assert "result_json" in body


def test_predict_url_download_fail(monkeypatch):
    class Resp:
        status_code = 404
        content = b""

    monkeypatch.setattr("requests.get", lambda url, timeout=20: Resp())
    monkeypatch.setattr("app.services.inference.resolve_requested_model", lambda req: "mock-model")
    monkeypatch.setattr("app.services.inference.load_model", lambda name: None)

    data = {"annotated": "false", "url": "https://bad.example.com/x.png"}
    r = client.post("/predict/url", data=data)
    assert r.status_code == 400, r.text



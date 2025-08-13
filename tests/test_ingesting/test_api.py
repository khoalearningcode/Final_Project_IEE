# tests/test_api.py
import io
import re
import json

def _assert_signed_url_ok(value):
    # signed_url có thể là None (nếu không có private key) hoặc một URL http(s)
    assert value is None or (isinstance(value, str) and value.startswith(("http://", "https://")))

def test_root(app_client):
    r = app_client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "message" in body
    assert isinstance(body["message"], str)

def test_healthz(app_client):
    r = app_client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] in ("healthy", "degraded")

def test_push_image_ok(app_client, sample_image_bytes):
    files = {"file": ("x.png", sample_image_bytes, "image/png")}
    r = app_client.post("/push_image", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["message"] == "Successfully!"
    # images/api/<uuid>.png
    assert re.match(r"^images/api/[0-9a-fA-F-]+\.png$", data["gcs_path"]), data["gcs_path"]
    _assert_signed_url_ok(data["signed_url"])

def test_push_image_reject_ext(app_client, sample_image_bytes):
    files = {"file": ("bad.txt", sample_image_bytes, "text/plain")}
    r = app_client.post("/push_image", files=files)
    assert r.status_code == 400

def test_push_images_ok(app_client, sample_image_bytes):
    files = [
        ("files", ("a.jpg", sample_image_bytes, "image/jpeg")),
        ("files", ("b.png", sample_image_bytes, "image/png")),
    ]
    r = app_client.post("/push_images", files=files)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["count"] == 2
    assert isinstance(out["results"], list) and len(out["results"]) == 2
    for item in out["results"]:
        if "error" in item:
            raise AssertionError(f"Unexpected error for file {item.get('filename')}: {item['error']}")
        assert item["message"] == "Successfully!"
        assert re.match(r"^images/api/[0-9a-fA-F-]+\.(jpg|png)$", item["gcs_path"]), item["gcs_path"]
        _assert_signed_url_ok(item["signed_url"])

def test_push_image_url_ok(app_client, monkeypatch, sample_image_bytes):
    # Patch requests.get để không gọi mạng thật
    class FakeResp:
        status_code = 200
        headers = {"Content-Type": "image/png"}
        content = sample_image_bytes
    def fake_get(url, timeout=20):
        return FakeResp()
    import ingesting.main as main  # điều chỉnh đúng module nếu khác
    monkeypatch.setattr(main.requests, "get", fake_get)

    payload = {"url": "https://example.com/some_image.png"}
    r = app_client.post("/push_image_url", data=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["message"] == "Successfully!"
    assert re.match(r"^images/url/[0-9a-fA-F-]+\.png$", data["gcs_path"]), data["gcs_path"]
    _assert_signed_url_ok(data["signed_url"])

def test_push_video_ok(app_client):
    # Tạo bytes giả cho video
    fake_video = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 128
    files = {"file": ("clip.mp4", fake_video, "video/mp4")}
    r = app_client.post("/push_video", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["message"] == "Successfully!"
    assert re.match(r"^videos/api/[0-9a-fA-F-]+\.mp4$", data["gcs_path"]), data["gcs_path"]
    _assert_signed_url_ok(data["signed_url"])

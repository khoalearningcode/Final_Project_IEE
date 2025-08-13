# tests/test_ingesting/test_invalid_inputs.py
import io
import re
import json
import pytest

# Regex tối giản (không dùng ngày tháng)
UUID_IMG_API_RE = r"^images/api/[0-9a-fA-F-]+\.(jpg|jpeg|png)$"
UUID_IMG_URL_RE = r"^images/url/[0-9a-fA-F-]+\.(jpg|jpeg|png)$"

def _assert_signed_url_ok(value):
    # signed_url có thể None hoặc URL http(s)
    assert value is None or (isinstance(value, str) and value.startswith(("http://", "https://")))

# ---- Fixtures mẫu (nếu bạn đã có fixture sample_image_bytes/app_client thì có thể bỏ đi 2 cái dưới) ----
@pytest.fixture
def sample_image_bytes():
    # PNG 1x1 pixel hợp lệ
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
        b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    )

# ---------------------------------------------------------------------------------------------------------
# 1) /push_image invalid cases
# ---------------------------------------------------------------------------------------------------------

def test_push_image_reject_ext_txt(app_client, sample_image_bytes):
    """Đuôi file không thuộc whitelist → 400"""
    files = {"file": ("bad.txt", sample_image_bytes, "text/plain")}
    r = app_client.post("/push_image", files=files)
    assert r.status_code == 400

def test_push_image_corrupted_bytes(app_client):
    """Đuôi hợp lệ nhưng bytes không phải ảnh hợp lệ → 400"""
    files = {"file": ("x.png", b"not-really-an-image", "image/png")}
    r = app_client.post("/push_image", files=files)
    assert r.status_code == 400
    body = r.json()
    assert "Invalid image file" in (body.get("detail") or "")

def test_push_image_missing_file(app_client):
    """Thiếu phần files trong multipart → 422 (FastAPI validate) hoặc 400 tùy cấu hình"""
    r = app_client.post("/push_image", files={})
    assert r.status_code in (400, 422)

# ---------------------------------------------------------------------------------------------------------
# 2) /push_images batch: trộn OK + lỗi
# ---------------------------------------------------------------------------------------------------------

def test_push_images_mixed_ok_and_bad(app_client, sample_image_bytes):
    files = [
        ("files", ("good.jpg", sample_image_bytes, "image/jpeg")),
        ("files", ("bad.txt", sample_image_bytes, "text/plain")),  # sẽ 400 ở item này
    ]
    r = app_client.post("/push_images", files=files)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["count"] == 2
    assert len(out["results"]) == 2

    # item 1: ok
    items = out["results"]
    item_ok  = next(i for i in items if "message" in i)
    item_err = next(i for i in items if "error"   in i)

    assert item_ok["message"] == "Successfully!"
    assert re.match(r"^images/api/[0-9a-fA-F-]+\.(jpg|png)$", item_ok["gcs_path"]), item_ok["gcs_path"]
    _assert_signed_url_ok(item_ok["signed_url"])

    assert isinstance(item_err["error"], str) and item_err["error"]


# ---------------------------------------------------------------------------------------------------------
# 3) /push_image_url invalid + edge
# ---------------------------------------------------------------------------------------------------------

def test_push_image_url_http_error(app_client, monkeypatch):
    """Server nguồn trả 404 → API trả 400"""
    class FakeResp:
        status_code = 404
        headers = {}
        content = b""

    def fake_get(url, timeout=20):
        return FakeResp()

    import ingesting.main as main
    monkeypatch.setattr(main.requests, "get", fake_get)

    payload = {"url": "https://example.com/not_found.png"}
    r = app_client.post("/push_image_url", data=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert r.status_code == 400
    assert "Download failed" in r.text

def test_push_image_url_unsupported_ext(app_client, monkeypatch, sample_image_bytes):
    """URL .gif (không cho phép) → 400"""
    class FakeResp:
        status_code = 200
        headers = {"Content-Type": "image/gif"}
        content = sample_image_bytes

    def fake_get(url, timeout=20):
        return FakeResp()

    import ingesting.main as main
    monkeypatch.setattr(main.requests, "get", fake_get)

    payload = {"url": "https://cdn.example.com/some_image.gif"}
    r = app_client.post("/push_image_url", data=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert r.status_code == 400

def test_push_image_url_no_ext_but_content_type_ok(app_client, monkeypatch, sample_image_bytes):
    """
    URL không có đuôi, header Content-Type=image/png → hệ thống đoán .png và ingest OK.
    """
    class FakeResp:
        status_code = 200
        headers = {"Content-Type": "image/png"}
        content = sample_image_bytes

    def fake_get(url, timeout=20):
        return FakeResp()

    import ingesting.main as main
    monkeypatch.setattr(main.requests, "get", fake_get)

    payload = {"url": "https://images.example.com/download?id=123"}  # không có .png ở cuối
    r = app_client.post("/push_image_url", data=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["message"] == "Successfully!"
    assert re.match(UUID_IMG_URL_RE, data["gcs_path"]), data["gcs_path"]
    _assert_signed_url_ok(data["signed_url"])

# ---------------------------------------------------------------------------------------------------------
# 4) /push_video invalid
# ---------------------------------------------------------------------------------------------------------

def test_push_video_unsupported_format(app_client):
    """Định dạng video không hỗ trợ → 400"""
    fake = b"\x00" * 64
    files = {"file": ("clip.mpe", fake, "video/mpeg")}
    r = app_client.post("/push_video", files=files)
    assert r.status_code == 400

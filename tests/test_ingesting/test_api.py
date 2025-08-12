def test_root(app_client):
    r = app_client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()

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
    assert data["gcs_path"].startswith("images/")
    assert data["signed_url"].startswith("https://fake-signed-url/")

def test_push_image_reject_ext(app_client, sample_image_bytes):
    files = {"file": ("bad.txt", sample_image_bytes, "text/plain")}
    r = app_client.post("/push_image", files=files)
    assert r.status_code == 400

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_invalid_image_file():
    r = client.post("/predict", files={"file": ("x.txt", b"not image", "text/plain")})
    assert r.status_code == 400

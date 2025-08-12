import io
import importlib
import pytest
from PIL import Image

# --- Fake GCS ---
class FakeBlob:
    def __init__(self, path): self.path = path
    def exists(self): return False
    def upload_from_string(self, data, content_type=None): pass
    def generate_signed_url(self, version, expiration, method, response_disposition):
        return f"https://fake-signed-url/{self.path}"

class FakeBucket:
    def __init__(self, name): self.name = name
    def exists(self): return True
    def blob(self, path): return FakeBlob(path)

class FakeStorageClient:
    def get_bucket(self, name): return FakeBucket(name)

@pytest.fixture(autouse=True)
def patch_gcs(monkeypatch):
    # patch trước khi import ingesting.main
    import ingesting.utils as utils
    monkeypatch.setattr(utils, "get_storage_client", lambda: FakeStorageClient())
    yield

@pytest.fixture
def app_client(patch_gcs):
    # import lại sau khi đã patch
    import ingesting.main as main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    return TestClient(main.app)

@pytest.fixture
def sample_image_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()

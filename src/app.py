import io
import os
import time
from pathlib import Path
from typing import List

import torch
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from ultralytics import YOLO

# ========= Paths (relative to this file) =========
BASE_DIR = Path(__file__).resolve().parent         # -> src/
STATIC_DIR = BASE_DIR / "static"
DEFAULT_MODEL = BASE_DIR / "models" / "best.pt"

# Nếu MODEL_PATH là relative thì quy chiếu từ BASE_DIR; nếu absolute thì giữ nguyên
_env_model = os.getenv("MODEL_PATH", str(DEFAULT_MODEL))
MODEL_PATH = Path(_env_model)
if not MODEL_PATH.is_absolute():
    MODEL_PATH = (BASE_DIR / MODEL_PATH).resolve()

# ========= Config =========
CONF = float(os.getenv("CONF", "0.25"))       # ngưỡng conf
IOU = float(os.getenv("IOU", "0.45"))         # ngưỡng NMS
IMG_SIZE = int(os.getenv("IMG_SIZE", "640"))  # kích thước suy luận
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ========= App =========
app = FastAPI(title="YOLO Web Inference")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# static for results and simple UI
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Load model once
try:
    model = YOLO(str(MODEL_PATH))
    model.to(DEVICE)
except Exception as e:
    raise RuntimeError(f"Cannot load model at '{MODEL_PATH}': {e}")

@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE}

@app.get("/", response_class=HTMLResponse)
def home():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    # Fallback HTML nếu chưa có file
    return """
    <!doctype html><meta charset="utf-8">
    <h1>YOLO Web Inference</h1>
    <p>Chưa tìm thấy <code>static/index.html</code>. Dùng API <code>/predict</code> (POST form-data: file).</p>
    """

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    # kiểm tra input
    allowed_ext = (".jpg", ".jpeg", ".png", ".webp")
    if not file.filename.lower().endswith(allowed_ext):
        raise HTTPException(status_code=400, detail=f"Vui lòng upload ảnh {allowed_ext}")

    # đọc ảnh vào PIL
    raw_bytes = await file.read()
    try:
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Không đọc được ảnh")

    # suy luận
    t0 = time.time()
    results = model.predict(
        img,
        imgsz=IMG_SIZE,
        conf=CONF,
        iou=IOU,
        device=DEVICE,
        verbose=False,
    )
    dt = time.time() - t0

    # kết quả (lấy kết quả đầu)
    r = results[0]

    # vẽ và lưu ảnh đã annotate
    annotated = r.plot()  # numpy (BGR)
    out_name = f"pred_{int(time.time()*1000)}.jpg"
    out_path = STATIC_DIR / out_name
    Image.fromarray(annotated[:, :, ::-1]).save(out_path)  # BGR->RGB khi lưu bằng PIL

    # parse boxes -> JSON
    dets = []
    if getattr(r, "boxes", None) is not None and len(r.boxes) > 0:
        for b in r.boxes:
            cls_id = int(b.cls.item())
            # tên lớp
            names = getattr(getattr(model, "model", None), "names", None)
            if isinstance(names, dict):
                cls_name = names.get(cls_id, str(cls_id))
            else:
                cls_name = str(cls_id)
            dets.append({
                "class_id": cls_id,
                "class_name": cls_name,
                "confidence": float(b.conf.item()),
                "xyxy": [float(x) for x in b.xyxy.squeeze().tolist()],
            })

    return JSONResponse({
        "success": True,
        "time_ms": round(dt * 1000, 2),
        "num_detections": len(dets),
        "detections": dets,
        "result_image_url": f"/static/{out_name}",
    })

# endpoint tải ảnh kết quả (nếu muốn down trực tiếp)
@app.get("/download/{filename}")
def download(filename: str):
    fp = STATIC_DIR / filename
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file kết quả")
    return FileResponse(fp, media_type="image/jpeg", filename=filename)

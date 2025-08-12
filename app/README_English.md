
# YOLO Inference Service — Documentation

## 1. Overview
This service is a **YOLO-based object detection API** built with **FastAPI** that:
- Accepts images via API endpoints.
- Runs YOLO model inference (Ultralytics) for object detection.
- Returns either:
  - JSON with detection results (bounding boxes, class, confidence).
  - Annotated PNG image with drawn bounding boxes.
- Supports **Prometheus** metrics and **OpenTelemetry** tracing (Jaeger).
- Saves annotated images locally for later inspection.

---

## 2. Features

### API Endpoints
1. `GET /` — Root endpoint with welcome message.
2. `GET /healthz` — Health check endpoint (verifies model loaded).
3. `GET /model/info` — Returns model configuration and metadata.
4. `POST /predict` — Accepts an image and returns detection results in JSON format.
5. `POST /predict/annotated` — Accepts an image, returns annotated PNG, and saves it to `./results` folder.

### Model Handling
- **Lazy loading**: Model is loaded only when the first request is made.
- Supports **custom model path** via environment variable `MODEL_PATH`.
- Configurable confidence, IOU thresholds, and image size.

### Observability
- **Tracing** with OpenTelemetry + Jaeger (detailed spans for image validation, inference, and postprocessing).
- **Metrics** with OpenTelemetry and Prometheus:
  - `yolo_inference_requests_total`
  - `yolo_inference_latency_seconds`
  - `yolo_num_detections` (Prometheus Gauge)
  - `yolo_response_time_summary_seconds` (Prometheus Summary)

### Storage
- Annotated images are saved in the `results` folder with a timestamp-based filename.

---

## 3. Technologies Used

| Technology              | Purpose |
|-------------------------|---------|
| **FastAPI**             | Web API framework |
| **Uvicorn**              | ASGI server to run FastAPI |
| **Ultralytics YOLO**    | Object detection model |
| **PIL (Pillow)**        | Image processing |
| **NumPy**               | Array operations |
| **Loguru**              | Structured logging |
| **OpenTelemetry**       | Distributed tracing & metrics |
| **Jaeger**              | Trace visualization & analysis |
| **Prometheus**          | Metrics collection & monitoring |
| **Prometheus Client**   | Native metrics instrumentation |

---

## 4. Environment Variables

| Variable       | Description | Default |
|----------------|-------------|---------|
| `MODEL_PATH`   | Path to YOLO model file | `./models/best.pt` |
| `CONF`         | Confidence threshold | `0.25` |
| `IOU`          | IOU threshold | `0.45` |
| `IMG_SIZE`     | Image size for inference | `640` |
| `PROM_PORT`    | Port for Prometheus metrics server | `8097` |
| `JAEGER_HOST`  | Hostname of Jaeger Agent | `jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local` |
| `JAEGER_PORT`  | Port for Jaeger Agent | `6831` |

---

## 5. Running the Service

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python app/main.py
```

The service will be available at:  
`http://localhost:5002/yolo/docs` (Swagger UI)

Prometheus metrics will be available at:  
`http://localhost:8097/metrics`

---

## 6. Disabling Tracing (Jaeger)

If you only want to test the main YOLO API **without running Jaeger**:
- Set an environment variable to a non-existent host to avoid errors:
```bash
export JAEGER_HOST=disabled
```
- Or comment out/remove the Jaeger initialization block in the code:
```python
# try:
#     jaeger_exporter = JaegerExporter(
#         agent_host_name=JAEGER_HOST,
#         agent_port=JAEGER_PORT,
#     )
#     span_processor = BatchSpanProcessor(jaeger_exporter)
#     provider.add_span_processor(span_processor)
# except Exception as e:
#     logger.warning(f"Jaeger exporter init failed: {e}")
```
- This will prevent connection attempts to Jaeger and avoid the `socket.gaierror` error.

---

## 7. Notes
- The service uses **lazy model loading**, so the model will only be loaded on the first request to `/predict` or `/predict/annotated`.
- All annotated images are saved to `./results` with filenames in the format:  
  `<original_name>_<timestamp>.png`
- Ensure your YOLO model is compatible with the **Ultralytics** version installed.

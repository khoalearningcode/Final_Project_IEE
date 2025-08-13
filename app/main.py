from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger
from prometheus_client import Gauge, Summary, start_http_server

from app.config import PROM_PORT, RESULTS_DIR
from app.routers.health import router as health_router
from app.routers.model import router as model_router
from app.routers.predict import router as predict_router
from app.services.inference import set_prom_client

app = FastAPI(
    title="Detection Inference Service",
    docs_url="/detection/docs",
    openapi_url="/detection/openapi.json",
)

# Static kết quả
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")

# Routers
app.include_router(health_router)
app.include_router(model_router)
app.include_router(predict_router)


def _start_prom_server():
    try:
        start_http_server(port=PROM_PORT, addr="0.0.0.0")
        logger.info(f"Prometheus metrics server started on :{PROM_PORT}")
    except OSError as e:
        logger.warning(f"Prometheus port busy, skip starting metrics server: {e}")


def _setup_prom_client_metrics():
    det_gauge = Gauge("inference_num_detections", "Number of detections produced by the last request")
    resp_summary = Summary("inference_response_time_summary_seconds", "Summary of inference response time")
    set_prom_client(det_gauge, resp_summary)


if __name__ == "__main__":
    _start_prom_server()
    _setup_prom_client_metrics()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))

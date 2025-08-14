from __future__ import annotations
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv() or "../.env")

import uvicorn
from fastapi import FastAPI
from loguru import logger
import requests
from prometheus_client import start_http_server

from ingesting.config import (
    ENABLE_TRACING,
    DISABLE_METRICS,
    METRICS_PORT,
    PORT,
    SERVICE_NAME,
    JAEGER_HOST,
    JAEGER_PORT,
)
from ingesting.services.tracing import setup_tracing
from ingesting.routers.health import router as health_router
from ingesting.routers.images import router as images_router

# OpenTelemetry metrics (OTel SDK)
from opentelemetry import metrics
from opentelemetry.metrics import set_meter_provider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
try:
    from opentelemetry.semconv.resource import ResourceAttributes as _RA
    SERVICE_NAME_KEY = _RA.SERVICE_NAME
except Exception:
    try:
        from opentelemetry.sdk.resources import SERVICE_NAME as _SERVICE_NAME
        SERVICE_NAME_KEY = _SERVICE_NAME
    except Exception:
        SERVICE_NAME_KEY = "service.name"

app = FastAPI(
    title="Ingesting Service",
    docs_url="/ingesting/docs",
    openapi_url="/ingesting/openapi.json",
)

# Routers
app.include_router(health_router)
app.include_router(images_router)

# Tracing (nhanh, có timeout 200ms)
tracer = setup_tracing(SERVICE_NAME, JAEGER_HOST, JAEGER_PORT, ENABLE_TRACING)

# Metrics (OTel Prometheus exporter)
if not DISABLE_METRICS:
    resource = Resource.create({SERVICE_NAME_KEY: SERVICE_NAME})
    reader = PrometheusMetricReader()
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    set_meter_provider(provider)
    meter = metrics.get_meter("ingesting", "0.1.1")

    # Bạn có thể tạo thêm counter/histogram ở đây nếu muốn export qua /metrics
    # (client-side Summary/Counter có thể dùng prometheus_client bên ngoài)
else:
    logger.warning("Metrics are disabled (DISABLE_METRICS=true).")

if __name__ == "__main__":
    # Prometheus client HTTP server (cho Summary… nếu bạn dùng thêm)
    if not DISABLE_METRICS:
        start_http_server(port=METRICS_PORT, addr="0.0.0.0")
        logger.info(f"Prometheus metrics server started on :{METRICS_PORT}")

    uvicorn.run(app, host="0.0.0.0", port=PORT)

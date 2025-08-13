from __future__ import annotations
import os

# Env flags
ENABLE_TRACING: bool = os.getenv("ENABLE_TRACING", "true").lower() == "true"
DISABLE_METRICS: bool = os.getenv("DISABLE_METRICS", "false").lower() == "true"

METRICS_PORT: int = int(os.getenv("METRICS_PORT", "8098"))
PORT: int = int(os.getenv("PORT", "5001"))

JAEGER_HOST: str = os.getenv("JAEGER_AGENT_HOST", "jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local")
JAEGER_PORT: int = int(os.getenv("JAEGER_AGENT_PORT", "6831"))

GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "")

# File type allow-list
ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png"}
ALLOWED_VIDEO_EXT = {"mp4", "mov", "avi", "mkv", "webm"}  # hiện chưa dùng

# Object prefixes
IMAGES_API_PREFIX = "images/api"
IMAGES_URL_PREFIX = "images/url"
VIDEOS_API_PREFIX = "videos/api"  # hiện chưa dùng

SERVICE_NAME = "ingesting-service"

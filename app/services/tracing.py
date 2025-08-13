from __future__ import annotations

import atexit
import socket
from typing import Optional

from loguru import logger
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import SERVICE_NAME_STR, JAEGER_HOST, JAEGER_PORT, TRACING_MODE


def _should_enable_tracing() -> bool:
    if TRACING_MODE == "off":
        return False
    if TRACING_MODE == "on":
        return True
    try:
        socket.getaddrinfo(JAEGER_HOST, JAEGER_PORT)
        return True
    except socket.gaierror:
        return False


def setup_tracing() -> trace.Tracer:
    """Setup Jaeger tracer if resolvable/enabled."""
    resource = Resource.create({SERVICE_NAME: SERVICE_NAME_STR})
    provider = trace.get_tracer_provider()
    if not isinstance(provider, SDKTracerProvider):
        provider = SDKTracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

    if _should_enable_tracing():
        try:
            exporter = JaegerExporter(agent_host_name=JAEGER_HOST, agent_port=JAEGER_PORT)
            span_processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(span_processor)
            atexit.register(span_processor.shutdown)
            logger.info(f"Tracing enabled → Jaeger @ {JAEGER_HOST}:{JAEGER_PORT}")
        except Exception as e:
            logger.warning(f"Jaeger exporter init failed, tracing disabled: {e}")
    else:
        logger.info("Tracing disabled (TRACING=off or host not resolvable).")

    return trace.get_tracer_provider().get_tracer("inference", "0.1.0")

from __future__ import annotations
import atexit
import concurrent.futures as cf
import socket
from loguru import logger
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# OTel resource compat
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

def setup_tracing(service_name: str, host: str, port: int, enable: bool) -> trace.Tracer:
    provider = trace.get_tracer_provider()
    if not isinstance(provider, SDKTracerProvider):
        provider = SDKTracerProvider(resource=Resource.create({SERVICE_NAME_KEY: service_name}))
        trace.set_tracer_provider(provider)

    if not enable:
        logger.warning("Tracing is disabled (ENABLE_TRACING=false).")
        return trace.get_tracer_provider().get_tracer("ingesting", "0.1.1")

    # Resolve rất nhanh (≤200ms) để không làm chậm startup
    def _resolve():
        socket.getaddrinfo(host, port)

    try:
        with cf.ThreadPoolExecutor(max_workers=1) as ex:
            ex.submit(_resolve).result(timeout=0.2)
        jaeger_exporter = JaegerExporter(agent_host_name=host, agent_port=port)
        span_processor = BatchSpanProcessor(jaeger_exporter)
        provider.add_span_processor(span_processor)
        atexit.register(span_processor.shutdown)
        logger.info(f"Tracing enabled → Jaeger @ {host}:{port}")
    except Exception as e:
        logger.warning(f"Tracing disabled (resolve/exporter failed): {e}")

    return trace.get_tracer_provider().get_tracer("ingesting", "0.1.1")

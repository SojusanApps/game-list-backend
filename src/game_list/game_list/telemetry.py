"""Telemetry setup for the application, using OpenTelemetry to instrument Django, Celery, Psycopg, Redis, and logging.

Exports to OTLP if endpoint is configured.
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.urllib import URLLibInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased


def setup_telemetry() -> None:
    """Set up OpenTelemetry instrumentation and OTLP exporter."""
    # Set up basic resource
    resource = Resource.create(
        attributes={
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "game_list"),
        },
    )

    # Use 10% sampling, respecting parent trace decisions
    sampler = ParentBased(root=TraceIdRatioBased(0.1))

    provider = TracerProvider(resource=resource, sampler=sampler)

    # Set up OTLP exporter if endpoint is set
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        # Note: with grpc, if endpoint includes http://, insecure is implied by the OTEL env vars
        # or we can just strip http:// for the python grpc exporter explicitly
        grpc_endpoint = endpoint.replace("http://", "").replace("https://", "")
        exporter = OTLPSpanExporter(endpoint=grpc_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    # Instrument everywhere
    RequestsInstrumentor().instrument()
    URLLibInstrumentor().instrument()
    URLLib3Instrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=False)
    DjangoInstrumentor().instrument()
    CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()

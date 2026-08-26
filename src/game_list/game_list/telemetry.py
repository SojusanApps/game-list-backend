"""Telemetry setup for the application, using OpenTelemetry to instrument Django, Celery, Psycopg, Redis, and logging.

Exports to OTLP if endpoint is configured.
"""

import os
from typing import TYPE_CHECKING

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
from opentelemetry.trace import Span, format_trace_id

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def add_trace_id_response_header(span: Span, request: HttpRequest, response: HttpResponse) -> None:  # noqa: ARG001
    """Stamp the request's trace id onto the response so it can reach gunicorn's access log."""
    response["X-Trace-Id"] = format_trace_id(span.get_span_context().trace_id)


def setup_telemetry() -> None:
    """Set up OpenTelemetry instrumentation and OTLP exporter."""
    # Set up basic resource
    resource = Resource.create(
        attributes={
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "game_list"),
        },
    )

    # Sample rate is env-driven (default 10%) so dev/docker can sample everything while prod stays sparse.
    sample_rate = float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "0.1"))
    sampler = ParentBased(root=TraceIdRatioBased(sample_rate))

    provider = TracerProvider(resource=resource, sampler=sampler)

    # Set up OTLP exporter if endpoint is set
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        # Note: with grpc, if endpoint includes http://, insecure is implied by the OTEL env vars
        # or we can just strip http:// for the python grpc exporter explicitly
        grpc_endpoint = endpoint.replace("http://", "").replace("https://", "")  # NOSONAR(S5332)
        exporter = OTLPSpanExporter(endpoint=grpc_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    # Instrument everywhere
    RequestsInstrumentor().instrument()
    URLLibInstrumentor().instrument()
    URLLib3Instrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=False, inject_trace_context=True)
    DjangoInstrumentor().instrument(response_hook=add_trace_id_response_header)
    CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()

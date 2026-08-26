"""Tests for OpenTelemetry setup."""

from unittest.mock import MagicMock

import pytest
from django.http import HttpResponse
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider

from game_list.game_list import telemetry as telemetry_module

_INSTRUMENTOR_ATTRS = (
    "RequestsInstrumentor",
    "URLLibInstrumentor",
    "URLLib3Instrumentor",
    "LoggingInstrumentor",
    "DjangoInstrumentor",
    "CeleryInstrumentor",
    "PsycopgInstrumentor",
    "RedisInstrumentor",
)


@pytest.fixture
def mock_instrumentors(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace every OpenTelemetry instrumentor class used by setup_telemetry with a MagicMock."""
    mocks = {}
    for attr in _INSTRUMENTOR_ATTRS:
        mock_cls = MagicMock()
        monkeypatch.setattr(telemetry_module, attr, mock_cls)
        mocks[attr] = mock_cls
    return mocks


@pytest.fixture
def mock_tracing(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace the exporter/provider machinery so no real tracer provider is installed globally."""
    mock_exporter_cls = MagicMock()
    mock_processor_cls = MagicMock()
    mock_provider_cls = MagicMock()
    mock_set_tracer_provider = MagicMock()
    monkeypatch.setattr(telemetry_module, "OTLPSpanExporter", mock_exporter_cls)
    monkeypatch.setattr(telemetry_module, "BatchSpanProcessor", mock_processor_cls)
    monkeypatch.setattr(telemetry_module, "TracerProvider", mock_provider_cls)
    monkeypatch.setattr(otel_trace, "set_tracer_provider", mock_set_tracer_provider)
    return {
        "OTLPSpanExporter": mock_exporter_cls,
        "BatchSpanProcessor": mock_processor_cls,
        "TracerProvider": mock_provider_cls,
        "set_tracer_provider": mock_set_tracer_provider,
    }


def test_setup_telemetry_instruments_everything_without_an_otlp_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    mock_instrumentors: dict[str, MagicMock],
    mock_tracing: dict[str, MagicMock],
) -> None:
    """With no OTLP endpoint configured, every instrumentor still runs but no exporter is wired up."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    telemetry_module.setup_telemetry()

    mock_tracing["OTLPSpanExporter"].assert_not_called()
    mock_tracing["TracerProvider"].return_value.add_span_processor.assert_not_called()
    mock_tracing["set_tracer_provider"].assert_called_once_with(mock_tracing["TracerProvider"].return_value)
    for mock_cls in mock_instrumentors.values():
        mock_cls.return_value.instrument.assert_called_once()
    mock_instrumentors["LoggingInstrumentor"].return_value.instrument.assert_called_once_with(
        set_logging_format=False,
        inject_trace_context=True,
    )
    mock_instrumentors["DjangoInstrumentor"].return_value.instrument.assert_called_once_with(
        response_hook=telemetry_module.add_trace_id_response_header,
    )


@pytest.mark.parametrize(
    ("env_value", "expected_rate"),
    [
        (None, 0.1),
        ("1.0", 1.0),
        ("0.5", 0.5),
    ],
)
def test_setup_telemetry_sample_rate_is_env_driven(
    monkeypatch: pytest.MonkeyPatch,
    mock_instrumentors: dict[str, MagicMock],  # noqa: ARG001
    mock_tracing: dict[str, MagicMock],  # noqa: ARG001
    env_value: str | None,
    expected_rate: float,
) -> None:
    """The root sampler's rate defaults to 10% but can be overridden via OTEL_TRACES_SAMPLER_ARG."""
    if env_value is None:
        monkeypatch.delenv("OTEL_TRACES_SAMPLER_ARG", raising=False)
    else:
        monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", env_value)
    mock_trace_id_ratio_based = MagicMock()
    monkeypatch.setattr(telemetry_module, "TraceIdRatioBased", mock_trace_id_ratio_based)

    telemetry_module.setup_telemetry()

    mock_trace_id_ratio_based.assert_called_once_with(expected_rate)


@pytest.mark.parametrize(
    "raw_endpoint",
    [
        "http://otel-collector:4317",
        "https://otel-collector:4317",
    ],
)
def test_setup_telemetry_strips_the_scheme_from_the_otlp_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    mock_instrumentors: dict[str, MagicMock],
    mock_tracing: dict[str, MagicMock],
    raw_endpoint: str,
) -> None:
    """The http(s):// scheme is stripped before the endpoint is handed to the grpc exporter."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", raw_endpoint)

    telemetry_module.setup_telemetry()

    mock_tracing["OTLPSpanExporter"].assert_called_once_with(endpoint="otel-collector:4317", insecure=True)
    mock_tracing["BatchSpanProcessor"].assert_called_once_with(mock_tracing["OTLPSpanExporter"].return_value)
    mock_tracing["TracerProvider"].return_value.add_span_processor.assert_called_once_with(
        mock_tracing["BatchSpanProcessor"].return_value,
    )
    for mock_cls in mock_instrumentors.values():
        mock_cls.return_value.instrument.assert_called_once()


def test_add_trace_id_response_header_stamps_the_request_span_trace_id() -> None:
    """The response hook exposes the request's real trace id, e.g. for gunicorn's access log."""
    tracer = TracerProvider().get_tracer(__name__)
    response = HttpResponse()

    with tracer.start_as_current_span("test-span") as span:
        expected_trace_id = otel_trace.format_trace_id(span.get_span_context().trace_id)
        telemetry_module.add_trace_id_response_header(span, MagicMock(), response)

    assert response["X-Trace-Id"] == expected_trace_id

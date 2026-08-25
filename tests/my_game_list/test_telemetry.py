"""Tests for OpenTelemetry setup."""

from unittest.mock import MagicMock

import pytest
from opentelemetry import trace as otel_trace

from my_game_list.my_game_list import telemetry as telemetry_module

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
    )


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

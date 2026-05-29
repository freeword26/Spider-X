"""Spider-X observability module for OpenTelemetry integration."""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("spider-x.observability")

_otel_initialized = False
_tracer_provider = None
_meter_provider = None


def get_otel_config() -> dict:
    return {
        "service_name": os.getenv("OTEL_SERVICE_NAME", "spider-x"),
        "service_version": os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
        "endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318"),
        "protocol": os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"),
        "traces_enabled": os.getenv("OTEL_TRACES_ENABLED", "true").lower() == "true",
        "metrics_enabled": os.getenv("OTEL_METRICS_ENABLED", "true").lower() == "true",
        "logs_enabled": os.getenv("OTEL_LOGS_ENABLED", "true").lower() == "true",
    }


def init_otel():
    global _otel_initialized, _tracer_provider, _meter_provider
    if _otel_initialized:
        return
    config = get_otel_config()
    try:
        if config["traces_enabled"]:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPTraceExporter
            _tracer_provider = TracerProvider()
            trace.set_tracer_provider(_tracer_provider)
            trace_exporter = HTTPTraceExporter(endpoint=f"{config['endpoint']}/v1/traces")
            _tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
            logger.info("OpenTelemetry tracing initialized")
        if config["metrics_enabled"]:
            from opentelemetry import metrics
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as HTTPMetricExporter
            metric_reader = PeriodicExportingMetricReader(
                HTTPMetricExporter(endpoint=f"{config['endpoint']}/v1/metrics")
            )
            _meter_provider = MeterProvider(metric_readers=[metric_reader])
            metrics.set_meter_provider(_meter_provider)
            logger.info("OpenTelemetry metrics initialized")
        _otel_initialized = True
    except ImportError:
        logger.warning("opentelemetry packages not installed, running in degraded mode")
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")


def get_tracer(name: str = "spider-x"):
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return NoopTracer()


def get_meter(name: str = "spider-x"):
    try:
        from opentelemetry import metrics
        return metrics.get_meter(name)
    except ImportError:
        return NoopMeter()


class NoopTracer:
    def start_as_current_span(self, name, **kwargs):
        return NoopSpanContext()
    def start_span(self, name, **kwargs):
        return NoopSpan()


class NoopSpanContext:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class NoopSpan:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def set_attribute(self, key, value):
        pass
    def set_attributes(self, attrs):
        pass
    def add_event(self, name, attributes=None):
        pass
    def set_status(self, status):
        pass
    def end(self):
        pass
    @property
    def span_id(self):
        return "0" * 16
    @property
    def trace_id(self):
        return "0" * 32


class NoopMeter:
    def create_counter(self, name, description="", unit=""):
        return NoopCounter()
    def create_histogram(self, name, description="", unit=""):
        return NoopHistogram()
    def create_up_down_counter(self, name, description="", unit=""):
        return NoopUpDownCounter()


class NoopCounter:
    def add(self, amount, attributes=None):
        pass


class NoopHistogram:
    def record(self, amount, attributes=None):
        pass


class NoopUpDownCounter:
    def add(self, amount, attributes=None):
        pass


_tracer = None
_meter = None
_task_counter = None
_task_duration = None
_worker_gauge = None


def ensure_instruments():
    global _tracer, _meter, _task_counter, _task_duration, _worker_gauge
    if _tracer is not None:
        return
    _tracer = get_tracer()
    _meter = get_meter()
    _task_counter = _meter.create_counter("worker.tasks.total", "Total tasks processed", "1")
    _task_duration = _meter.create_histogram("worker.task.duration", "Task execution duration", "ms")
    _worker_gauge = _meter.create_up_down_counter("worker.active.count", "Active workers", "1")


def record_task_start(task_id: str, task_type: str):
    ensure_instruments()
    attrs = {"task.id": task_id, "task.type": task_type}
    _task_counter.add(1, attrs)
    return TaskSpan(task_id, task_type)


def record_task_complete(task_id: str, task_type: str, duration_ms: float, success: bool = True):
    ensure_instruments()
    attrs = {"task.id": task_id, "task.type": task_type, "task.success": str(success)}
    _task_duration.record(duration_ms, attrs)


class TaskSpan:
    def __init__(self, task_id: str, task_type: str):
        self.task_id = task_id
        self.task_type = task_type
        self._span = None
        self._start_time = None

    def __enter__(self):
        self._span = get_tracer().start_as_current_span(
            f"task.{self.task_type}",
            attributes={"task.id": self.task_id, "task.type": self.task_type},
        )
        if hasattr(self._span, "__enter__"):
            self._span.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            if hasattr(self._span, "set_attribute"):
                self._span.set_attribute("error", True)
                self._span.set_attribute("error.message", str(exc_val))
            if hasattr(self._span, "set_status"):
                from opentelemetry.trace import StatusCode
                self._span.set_status(StatusCode.ERROR, str(exc_val))
        if hasattr(self._span, "__exit__"):
            self._span.__exit__(exc_type, exc_val, exc_tb)

    def add_event(self, name: str, attributes: dict = None):
        if self._span and hasattr(self._span, "add_event"):
            self._span.add_event(name, attributes)

    def set_attribute(self, key: str, value):
        if self._span and hasattr(self._span, "set_attribute"):
            self._span.set_attribute(key, value)

    def get_trace_id(self) -> str:
        if self._span and hasattr(self._span, "get_span_context"):
            ctx = self._span.get_span_context()
            if ctx and hasattr(ctx, "trace_id"):
                return format(ctx.trace_id, "032x")
        return "0" * 32


__all__ = [
    "init_otel",
    "get_tracer",
    "get_meter",
    "get_otel_config",
    "record_task_start",
    "record_task_complete",
    "ensure_instruments",
    "TaskSpan",
    "NoopTracer",
    "NoopMeter",
]

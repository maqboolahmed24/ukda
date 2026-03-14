import re
import secrets
from contextvars import ContextVar
from dataclasses import dataclass

TRACEPARENT_HEADER = "traceparent"
_TRACEPARENT_PATTERN = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    parent_span_id: str | None
    span_id: str
    trace_flags: str

    @property
    def response_traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"


_trace_context_var: ContextVar[TraceContext | None] = ContextVar(
    "telemetry_trace_context",
    default=None,
)


def _new_trace_id() -> str:
    return secrets.token_hex(16)


def _new_span_id() -> str:
    return secrets.token_hex(8)


def resolve_trace_context(header_value: str | None) -> TraceContext:
    if header_value:
        match = _TRACEPARENT_PATTERN.match(header_value.strip().lower())
        if match:
            trace_id, parent_span_id, trace_flags = match.groups()
            return TraceContext(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                span_id=_new_span_id(),
                trace_flags=trace_flags,
            )

    return TraceContext(
        trace_id=_new_trace_id(),
        parent_span_id=None,
        span_id=_new_span_id(),
        trace_flags="01",
    )


def set_trace_context(trace_context: TraceContext):
    return _trace_context_var.set(trace_context)


def reset_trace_context(token) -> None:
    _trace_context_var.reset(token)


def current_trace_context() -> TraceContext | None:
    return _trace_context_var.get()


def current_trace_id() -> str | None:
    trace_context = current_trace_context()
    if trace_context is None:
        return None
    return trace_context.trace_id


def build_downstream_traceparent() -> str | None:
    trace_context = current_trace_context()
    if trace_context is None:
        return None
    return f"00-{trace_context.trace_id}-{_new_span_id()}-{trace_context.trace_flags}"

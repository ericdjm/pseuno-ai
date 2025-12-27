"""
Debug trace helper for building span-based traces.

Usage:
    tracer = DebugTracer(variant="v5_hybrid", model="gpt-4.1-mini")
    
    with tracer.span("style.generate", "llm_call", model="gpt-4.1-mini") as span:
        response = await call_llm(...)
        span.set_artifact("system_prompt", system_prompt)
        span.set_artifact("user_message", user_message)
        span.set_artifact("raw_response", response)
        span.set_meta("prompt_chars", len(system_prompt) + len(user_message))
        span.set_meta("response_chars", len(response))
    
    trace = tracer.build()  # Returns DebugTrace
"""

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

from app.schemas.advanced import DebugSpan, DebugTrace, DebugTraceSummary, SpanKind


@dataclass
class SpanBuilder:
    """Builder for a single span."""

    id: str
    parent_id: Optional[str]
    name: str
    kind: SpanKind
    start_ms: int
    _tracer: "DebugTracer"
    meta: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    end_ms: Optional[int] = None

    def set_meta(self, key: str, value: Any) -> "SpanBuilder":
        """Set a metadata field."""
        self.meta[key] = value
        return self

    def set_artifact(self, key: str, value: str) -> "SpanBuilder":
        """Set an artifact (raw text content)."""
        self.artifacts[key] = value
        return self

    def finish(self) -> None:
        """Finish the span and record end time."""
        self.end_ms = self._tracer._elapsed_ms()

    def to_span(self) -> DebugSpan:
        """Convert to DebugSpan model."""
        end = self.end_ms if self.end_ms is not None else self._tracer._elapsed_ms()
        return DebugSpan(
            id=self.id,
            parent_id=self.parent_id,
            name=self.name,
            kind=self.kind,
            start_ms=self.start_ms,
            end_ms=end,
            elapsed_ms=end - self.start_ms,
            meta=self.meta,
            artifacts=self.artifacts,
        )


class DebugTracer:
    """
    Tracer for building debug traces with nested spans.
    
    Thread-safe for single-request use (not shared across requests).
    """

    def __init__(
        self,
        variant: str,
        model: str,
        fast_model: Optional[str] = None,
        architecture: str = "single_step",
    ) -> None:
        self._variant = variant
        self._model = model
        self._fast_model = fast_model
        self._architecture = architecture
        self._start_time = time.time()
        self._spans: List[SpanBuilder] = []
        self._span_stack: List[str] = []  # Stack of parent span IDs
        self._llm_call_count = 0
        self._repair_count = 0
        self._success = True
        self._error: Optional[str] = None

    def _elapsed_ms(self) -> int:
        """Get elapsed time in ms since tracer start."""
        return int((time.time() - self._start_time) * 1000)

    def _generate_id(self) -> str:
        """Generate a unique span ID."""
        return uuid.uuid4().hex[:8]

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind,
        **initial_meta: Any,
    ) -> Generator[SpanBuilder, None, None]:
        """
        Context manager for creating a span.
        
        Args:
            name: Span name (e.g., "style.generate", "lyrics.repair.1")
            kind: Type of operation (llm_call, validate, parse, etc.)
            **initial_meta: Initial metadata to set on the span
        
        Yields:
            SpanBuilder for setting additional meta/artifacts
        """
        span_id = self._generate_id()
        parent_id = self._span_stack[-1] if self._span_stack else None

        builder = SpanBuilder(
            id=span_id,
            parent_id=parent_id,
            name=name,
            kind=kind,
            start_ms=self._elapsed_ms(),
            _tracer=self,
            meta=dict(initial_meta),
        )

        # Track counts
        if kind == "llm_call":
            self._llm_call_count += 1
        if kind == "repair":
            self._repair_count += 1

        # Push to stack for nesting
        self._span_stack.append(span_id)

        try:
            yield builder
        finally:
            # Pop from stack and finish
            self._span_stack.pop()
            builder.finish()
            self._spans.append(builder)

    def add_span(
        self,
        name: str,
        kind: SpanKind,
        start_ms: int,
        end_ms: int,
        meta: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, str]] = None,
        parent_id: Optional[str] = None,
    ) -> None:
        """
        Manually add a completed span (for cases where context manager doesn't fit).
        """
        span_id = self._generate_id()
        builder = SpanBuilder(
            id=span_id,
            parent_id=parent_id,
            name=name,
            kind=kind,
            start_ms=start_ms,
            end_ms=end_ms,
            _tracer=self,
            meta=meta or {},
            artifacts=artifacts or {},
        )

        if kind == "llm_call":
            self._llm_call_count += 1
        if kind == "repair":
            self._repair_count += 1

        self._spans.append(builder)

    def set_error(self, error: str) -> None:
        """Mark the trace as failed with an error message."""
        self._success = False
        self._error = error

    def build(self) -> DebugTrace:
        """Build the final DebugTrace model."""
        total_elapsed = self._elapsed_ms()

        summary = DebugTraceSummary(
            variant=self._variant,
            model=self._model,
            fast_model=self._fast_model,
            total_elapsed_ms=total_elapsed,
            llm_calls=self._llm_call_count,
            repairs=self._repair_count,
            architecture=self._architecture,
            success=self._success,
            error=self._error,
        )

        # Sort spans by start time
        sorted_spans = sorted(self._spans, key=lambda s: s.start_ms)

        return DebugTrace(
            version=1,
            summary=summary,
            spans=[s.to_span() for s in sorted_spans],
        )

    def to_dict(self) -> Dict[str, Any]:
        """Build and convert to dict for JSON serialization."""
        return self.build().model_dump()


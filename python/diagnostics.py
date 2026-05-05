"""Structured diagnostics for proof generation.

The Swift app consumes these events to populate the diagnostics panel.  The
module is intentionally independent from DrawBot so it can also be used by the
subprocess worker before the rendering stack is fully initialized.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


DiagnosticSink = Callable[[dict[str, Any]], None]


@dataclass
class DiagnosticEvent:
    level: str
    category: str
    message: str
    font_path: str | None = None
    proof_name: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now().isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DiagnosticsCollector:
    """Collect diagnostics and optionally stream them to a caller."""

    def __init__(self, debug: bool = False, sink: DiagnosticSink | None = None):
        self.debug = debug
        self.sink = sink
        self.events: list[DiagnosticEvent] = []

    def add(
        self,
        level: str,
        category: str,
        message: str,
        *,
        font_path: str | None = None,
        proof_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        event = DiagnosticEvent(
            level=level,
            category=category,
            message=message,
            font_path=font_path,
            proof_name=proof_name,
            details=details or {},
        )
        self.events.append(event)
        if self.sink:
            self.sink({"type": "diagnostic", "event": event.to_dict()})

    def debug_event(
        self,
        category: str,
        message: str,
        *,
        font_path: str | None = None,
        proof_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if self.debug:
            self.add(
                "debug",
                category,
                message,
                font_path=font_path,
                proof_name=proof_name,
                details=details,
            )

    def to_list(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]

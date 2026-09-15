"""Deterministic message/fault schedule with canonical serialized replay."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class Delivery:
    trace_id: str
    sequence: int
    source: str
    target: str
    message_type: str
    payload_digest: str
    action: str = "deliver"
    delay_ticks: int = 0

    def __post_init__(self) -> None:
        if self.action not in {"deliver", "drop", "duplicate", "disconnect"}:
            raise ValueError("unsupported deterministic action")
        if self.sequence < 0 or self.delay_ticks < 0:
            raise ValueError("schedule counters must not be negative")


class DeterministicTransport:
    def __init__(self, trace_id: str) -> None:
        if not trace_id:
            raise ValueError("trace_id is required")
        self.trace_id = trace_id
        self._events: list[Delivery] = []

    def schedule(self, source: str, target: str, message_type: str,
                 payload_digest: str, *, action: str = "deliver",
                 delay_ticks: int = 0) -> Delivery:
        event = Delivery(self.trace_id, len(self._events), source, target,
                         message_type, payload_digest, action, delay_ticks)
        self._events.append(event)
        return event

    def replay_order(self) -> tuple[Delivery, ...]:
        return tuple(sorted(self._events,
                            key=lambda item: (item.delay_ticks, item.sequence)))

    def to_json(self) -> str:
        document = {"schemaVersion": "gse-v50-network-trace-v1",
                    "traceId": self.trace_id,
                    "events": [asdict(event) for event in self._events]}
        return json.dumps(document, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "DeterministicTransport":
        document = json.loads(raw)
        if document.get("schemaVersion") != "gse-v50-network-trace-v1":
            raise ValueError("unsupported trace schema")
        transport = cls(document["traceId"])
        for raw_event in document["events"]:
            event = Delivery(**raw_event)
            if event.trace_id != transport.trace_id or event.sequence != len(transport._events):
                raise ValueError("non-canonical trace identity or sequence")
            transport._events.append(event)
        return transport

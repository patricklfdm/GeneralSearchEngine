"""Deterministic message/fault schedule with canonical serialized replay."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import hashlib
from typing import Callable


MAX_EVENTS = 10_000
MAX_TRACE_BYTES = 8 * 1024 * 1024


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
        if self.action not in {"deliver", "drop", "duplicate", "disconnect", "reconnect"}:
            raise ValueError("unsupported deterministic action")
        if (type(self.sequence) is not int or type(self.delay_ticks) is not int
                or self.sequence < 0 or not 0 <= self.delay_ticks <= 1_000_000):
            raise ValueError("schedule counters must not be negative")
        if not all(isinstance(value, str) and value for value in (
                self.trace_id, self.source, self.target, self.message_type, self.payload_digest)):
            raise ValueError("event identities must be nonempty strings")


class DeterministicTransport:
    def __init__(self, trace_id: str) -> None:
        if not trace_id:
            raise ValueError("trace_id is required")
        self.trace_id = trace_id
        self._events: list[Delivery] = []
        self._payloads: dict[str, dict] = {}
        self._payload_bytes = 0
        self._event_bytes = 0

    def schedule(self, source: str, target: str, message_type: str,
                 payload_digest: str, *, action: str = "deliver",
                 delay_ticks: int = 0) -> Delivery:
        if len(self._events) >= MAX_EVENTS:
            raise ValueError("trace event capacity exceeded")
        event = Delivery(self.trace_id, len(self._events), source, target,
                         message_type, payload_digest, action, delay_ticks)
        event_bytes = len(json.dumps(asdict(event), sort_keys=True, separators=(",", ":")).encode()) + 1
        if self._event_bytes + self._payload_bytes + event_bytes + 512 > MAX_TRACE_BYTES:
            raise ValueError("trace byte capacity exceeded")
        self._events.append(event)
        self._event_bytes += event_bytes
        return event

    def message(self, source: str, target: str, message_type: str,
                payload: dict, **delivery_options) -> Delivery:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(raw.encode()) > MAX_TRACE_BYTES:
            raise ValueError("payload capacity exceeded")
        digest = hashlib.sha256(raw.encode()).hexdigest()
        new_bytes = 0 if digest in self._payloads else len(raw.encode()) + len(digest) + 4
        # Reserve the complete payload before accepting an event. Roll back the
        # reservation on rejection so failed admission does not grow the trace.
        self._payload_bytes += new_bytes
        try:
            event = self.schedule(source, target, message_type, digest, **delivery_options)
        except ValueError:
            self._payload_bytes -= new_bytes
            raise
        self._payloads[digest] = json.loads(raw)
        return event

    def payload(self, event: Delivery) -> dict:
        if event.payload_digest not in self._payloads:
            raise ValueError("trace lacks replay payload")
        return json.loads(json.dumps(self._payloads[event.payload_digest]))

    def replay(self, receive: Callable[[Delivery], object]) -> list[dict]:
        """Execute a fresh schedule. Disconnects affect both link directions.

        Ticks are absolute delivery ticks; equal ticks retain schedule order.
        Rejected messages remain in the transcript and do not stop later retries.
        """
        disconnected = set()
        transcript = []
        for event in self.replay_order():
            link = tuple(sorted((event.source, event.target)))
            result = {"sequence": event.sequence, "tick": event.delay_ticks}
            if event.action in {"disconnect", "reconnect"}:
                if event.action == "disconnect":
                    disconnected.add(link)
                else:
                    disconnected.discard(link)
                transcript.append(dict(result, outcome=event.action))
            elif event.action == "drop" or link in disconnected:
                transcript.append(dict(result, outcome="dropped"))
            else:
                for copy in range(2 if event.action == "duplicate" else 1):
                    try:
                        value = receive(event)
                        transcript.append(dict(result, copy=copy, outcome="delivered", result=value))
                    except ValueError as error:
                        transcript.append(dict(result, copy=copy, outcome="rejected", reason=str(error)))
        return transcript

    def replay_order(self) -> tuple[Delivery, ...]:
        return tuple(sorted(self._events,
                            key=lambda item: (item.delay_ticks, item.sequence)))

    def to_json(self) -> str:
        document = {"schemaVersion": "gse-v50-network-trace-v1",
                    "traceId": self.trace_id,
                    "events": [asdict(event) for event in self._events],
                    "payloads": self._payloads}
        raw = json.dumps(document, sort_keys=True, separators=(",", ":"))
        if len(raw.encode()) > MAX_TRACE_BYTES:
            raise ValueError("trace byte capacity exceeded")
        return raw

    @classmethod
    def from_json(cls, raw: str) -> "DeterministicTransport":
        if len(raw.encode()) > MAX_TRACE_BYTES:
            raise ValueError("trace byte capacity exceeded")
        document = json.loads(raw)
        if document.get("schemaVersion") != "gse-v50-network-trace-v1":
            raise ValueError("unsupported trace schema")
        transport = cls(document["traceId"])
        if len(document["events"]) > MAX_EVENTS:
            raise ValueError("trace event capacity exceeded")
        for digest, payload in document.get("payloads", {}).items():
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if not isinstance(payload, dict) or hashlib.sha256(encoded.encode()).hexdigest() != digest:
                raise ValueError("trace payload digest mismatch")
            transport._payloads[digest] = payload
            transport._payload_bytes += len(encoded.encode()) + len(digest) + 4
        for raw_event in document["events"]:
            event = Delivery(**raw_event)
            if event.trace_id != transport.trace_id or event.sequence != len(transport._events):
                raise ValueError("non-canonical trace identity or sequence")
            transport.schedule(event.source, event.target, event.message_type,
                               event.payload_digest, action=event.action, delay_ticks=event.delay_ticks)
        return transport

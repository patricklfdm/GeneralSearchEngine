"""Independent validation of production wire attempts and deterministic fault evidence."""
import hashlib
from collections import Counter
from scripts.v50 import wire_fixture as wire


def check(condition, message):
    if not condition:
        raise ValueError(message)


def validate(events, *, retry_limit=1, required_actions=()):
    check(0 < len(events) <= 300_000, "missing or oversized network transcript")
    sequences, attempts, digests = {}, {}, {}
    actions = Counter()
    for event in events:
        node, pid = event["node"], event["pid"]
        check(node in {"node-1", "node-2", "node-3"} and type(pid) is int and pid > 0, "invalid process identity")
        owner = (node, pid)
        check(event["sequence"] == sequences.get(owner, 0) + 1, "network event sequence gap")
        sequences[owner] = event["sequence"]
        request, response = event["request"], event["response"]
        digest = hashlib.sha256(wire.encode(request)).hexdigest()
        check(digest == event["requestSha256"], "wire request checksum mismatch")
        barrier, action = event["barrier"], event["action"]
        check(barrier in {"BEFORE_REQUEST_WRITE", "BEFORE_RESPONSE_WRITE", "AFTER_RESPONSE_READ"}, "unknown network barrier")
        check(action in {"deliver", "disconnect", "hold"}, "unknown fault action")
        check(node == request["recipient" if barrier == "BEFORE_RESPONSE_WRITE" else "sender"], "wire attempt has wrong process owner")
        key = (node, pid, barrier, request["traceId"])
        check(event["attempt"] == attempts.get(key, 0) + 1, "attempt count gap")
        attempts[key] = event["attempt"]
        check(digests.setdefault(key, digest) == digest, "retry changed request bytes")
        if barrier == "BEFORE_REQUEST_WRITE":
            check(event["attempt"] <= retry_limit + 1, "request exceeded retry bound")
        if response:
            wire.encode(response)
            check(all(response[field] == request[field] for field in (
                "protocol", "groupId", "configurationId", "epoch", "incarnationId", "traceId", "eventSequence")), "uncorrelated response")
            check(response["sender"] == request["recipient"] and response["recipient"] == request["sender"], "wrong response voter")
        else:
            check(barrier == "BEFORE_REQUEST_WRITE", "missing received/durable response")
        if action != "deliver": actions[(request["type"], action)] += 1
    for required in required_actions:
        check(actions[tuple(required)] > 0, "required fault was never exercised")
    return {"status": "PASS", "processes": len(sequences), "events": len(events),
            "faults": [{"type": kind, "action": action, "count": count} for (kind, action), count in sorted(actions.items())]}

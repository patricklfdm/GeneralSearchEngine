import copy
import hashlib
import unittest
from scripts.v50.hardening_trace import validate
from scripts.v50.wire_fixture import encode


class HardeningTraceTest(unittest.TestCase):
    def fixture(self):
        request = {"protocol": "gse-replication/1.0", "groupId": "33333333-3333-3333-3333-333333333333",
                   "configurationId": "leader-v1", "sender": "node-1", "recipient": "node-2", "epoch": 2,
                   "incarnationId": "44444444-4444-4444-4444-444444444444", "traceId": "55555555-5555-5555-5555-555555555555",
                   "eventSequence": 1, "type": "APPEND", "payload": {"manifestDigest": "a" * 64, "entry": "AA=="}}
        response = dict(request, sender="node-2", recipient="node-1", type="DURABLE_ACK")
        events = []
        for attempt in (1, 2):
            events += [{"node": "node-1", "pid": 100, "sequence": attempt, "attempt": attempt, "barrier": "BEFORE_REQUEST_WRITE",
                        "action": "deliver", "request": copy.deepcopy(request), "response": {}, "requestSha256": hashlib.sha256(encode(request)).hexdigest()},
                       {"node": "node-2", "pid": 101, "sequence": attempt, "attempt": attempt, "barrier": "BEFORE_RESPONSE_WRITE",
                        "action": "disconnect" if attempt == 1 else "deliver", "request": copy.deepcopy(request), "response": copy.deepcopy(response),
                        "requestSha256": hashlib.sha256(encode(request)).hexdigest()}]
        return events

    def test_lost_ack_and_exact_retry_are_valid(self):
        self.assertEqual("PASS", validate(self.fixture(), required_actions=[("APPEND", "disconnect")])["status"])

    def test_changed_retry_bytes_reject_even_with_recomputed_checksum(self):
        events = self.fixture(); events[2]["request"]["payload"]["entry"] = "AQ=="
        events[2]["requestSha256"] = hashlib.sha256(encode(events[2]["request"])).hexdigest()
        with self.assertRaisesRegex(ValueError, "changed request bytes"): validate(events)

    def test_missing_fault_rejects(self):
        with self.assertRaisesRegex(ValueError, "never exercised"): validate(self.fixture(), required_actions=[("COMMIT_PROOF", "disconnect")])

    def test_uncorrelated_response_rejects(self):
        events = self.fixture(); events[1]["response"]["eventSequence"] = 9
        with self.assertRaisesRegex(ValueError, "uncorrelated"): validate(events)

    def test_excessive_retries_reject(self):
        with self.assertRaisesRegex(ValueError, "retry bound"): validate(self.fixture(), retry_limit=0)

    def test_invented_process_owner_rejects(self):
        events = self.fixture(); events[0]["node"] = "node-3"
        with self.assertRaisesRegex(ValueError, "wrong process owner"): validate(events)

    def test_missing_event_rejects(self):
        events = self.fixture(); events[2]["sequence"] = 4
        with self.assertRaisesRegex(ValueError, "sequence gap"): validate(events)


if __name__ == "__main__": unittest.main()

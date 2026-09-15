import unittest

from scripts.v50.deterministic_transport import DeterministicTransport


class DeterministicTransportTest(unittest.TestCase):
    def test_round_trip_preserves_exact_trace(self):
        transport = DeterministicTransport("trace-1")
        transport.schedule("node-1", "node-2", "APPEND", "a", delay_ticks=3)
        transport.schedule("node-1", "node-3", "APPEND", "a", action="duplicate")
        transport.schedule("node-2", "node-1", "ACK", "b", action="drop")
        encoded = transport.to_json()
        replay = DeterministicTransport.from_json(encoded)
        self.assertEqual(encoded, replay.to_json())
        self.assertEqual((1, 2, 0), tuple(item.sequence for item in replay.replay_order()))

    def test_unknown_action_is_rejected(self):
        transport = DeterministicTransport("trace-2")
        with self.assertRaises(ValueError):
            transport.schedule("a", "b", "APPEND", "x", action="corrupt")


if __name__ == "__main__":
    unittest.main()

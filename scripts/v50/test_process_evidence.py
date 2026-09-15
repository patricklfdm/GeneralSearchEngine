"""Negative evidence admission cases; the shell gate separately runs real JVMs."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.v50.evidence import validate, write_bundle, write_harness


class ProcessEvidenceTest(unittest.TestCase):
    def fixture(self, workspace):
        events = []

        def event(action, node=None, pid=None, generation=None, **extra):
            item = dict(sequence=len(events), action=action, **extra)
            if node is not None:
                item.update(node=node, pid=pid, generation=generation)
            events.append(item)

        for index in range(1, 4):
            node = f"node-{index}"
            directory = workspace / node
            directory.mkdir()
            (directory / "stdout.log").write_text("")
            (directory / "stderr.log").write_text("")
            event("ready", node, 1000 + index, 1)
        event("concurrent", pids={f"node-{i}": 1000 + i for i in range(1, 4)})
        event("crash", "node-1", 1001, 1, exitCode=137)
        event("ready", "node-1", 2001, 2)
        event("storage-fault", "node-3", 1003, 1, exitCode=20)
        event("ready", "node-3", 2003, 2)
        event("concurrent", pids={"node-1": 2001, "node-2": 1002, "node-3": 2003})
        for index, generation in ((1, 2), (2, 1), (3, 2)):
            node = f"node-{index}"
            pid = generation * 1000 + index
            event("cleanup", node, pid, generation, exitCode=137)
            directory = workspace / node
            (directory / "ready.properties").write_text(f"nodeId={node}\ngeneration={generation}\npid={pid}\n")
            lines = [f"READY node={node} generation={e['generation']} pid={e['pid']}\n"
                     for e in events if e["action"] == "ready" and e["node"] == node]
            if node == "node-3":
                lines.append("STORAGE_FAULT node=node-3 generation=1 pid=1003\n")
            (directory / "events.log").write_text("".join(lines))
        (workspace / "node-3/storage-fault.properties").write_text(
            "nodeId=node-3\ngeneration=1\npid=1003\nexitCode=20\n")
        (workspace / "process-events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
        output = workspace / "evidence"
        write_harness(output, "1" * 40, workspace)
        return output

    def test_raw_process_artifacts_are_required_even_with_a_valid_summary_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = self.fixture(Path(temporary))
            original = validate(output)
            (output / "members/node-1/events.log").unlink()
            write_bundle(output, original)
            with self.assertRaisesRegex(ValueError, "artifact inventory"):
                validate(output)

    def test_wrong_pid_exit_or_restart_concurrency_fails_with_recomputed_checksums(self):
        changes = (
            lambda e: e[4].update(pid=9999),
            lambda e: e[4].update(exitCode=0),
            lambda e: e[5].update(pid=1001),
            lambda e: e[6].update(action="cleanup"),
            lambda e: e[8].update(pids={"node-1": 2001}),
        )
        for index, change in enumerate(changes):
            with self.subTest(change=index), tempfile.TemporaryDirectory() as temporary:
                output = self.fixture(Path(temporary))
                document = validate(output)
                journal = output / "members/process-events.jsonl"
                events = [json.loads(line) for line in journal.read_text().splitlines()]
                change(events)
                journal.write_text("".join(json.dumps(e) + "\n" for e in events))
                write_bundle(output, document)
                with self.assertRaises(ValueError):
                    validate(output)

    def test_worker_receipts_must_agree_with_parent_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = self.fixture(Path(temporary))
            document = validate(output)
            (output / "members/node-3/storage-fault.properties").write_text(
                "nodeId=node-3\ngeneration=1\npid=9999\nexitCode=20\n")
            write_bundle(output, document)
            with self.assertRaisesRegex(ValueError, "storage-fault receipt mismatch"):
                validate(output)

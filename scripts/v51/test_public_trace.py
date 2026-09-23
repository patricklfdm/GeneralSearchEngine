"""Observer completion preserves evidence and rejects unwitnessed corruption."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from . import public_trace as trace


class PublicTraceTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.path = self.root / 'node-1-trace.jsonl'
        self.pending = self.path.with_name(self.path.name + '.pending')
        self.proc = SimpleNamespace(pid=41, returncode=-9, poll=lambda: -9)
        self.first = self.line(order=1, event='STARTED')
        self.last = self.line(order=2, event='RECEIVED', frame='x'*32768)

    def line(self, **values):
        return (json.dumps(dict(node='node-1', pid=41, generation=1, **values))+'\n').encode()

    def publish(self, count=8192, *, offset=None, line=None):
        line = self.last if line is None else line
        self.path.write_bytes(self.first + line[:count])
        self.pending.write_bytes(b'GSETRC1\n'+struct.pack('>Q',len(self.first) if offset is None else offset)
                                 +hashlib.sha256(line).digest()+line)

    def finish(self): trace.finish(self.root, 'node-1', self.proc)

    def reject(self, message):
        before = self.path.read_bytes(); pending = self.pending.read_bytes() if self.pending.exists() else None
        with self.assertRaisesRegex(ValueError, message): self.finish()
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(pending, self.pending.read_bytes() if self.pending.exists() else None)
        self.assertEqual([], list(self.root.glob('*.recovery-*')))

    def test_sigkill_at_each_append_boundary_preserves_complete_row(self):
        for count in (0, 1, 8192, 16384, len(self.last)-1, len(self.last)):
            with self.subTest(count=count):
                self.publish(count); self.finish(); self.finish()
                self.assertEqual(self.first+self.last, self.path.read_bytes())
                self.assertFalse(self.pending.exists())
                archive = self.root / 'node-1-trace.jsonl.recovery-41-2'
                self.assertEqual(self.last[:count], (archive/'partial.bin').read_bytes())
                self.assertEqual(self.last, (archive/'pending.bin').read_bytes()[48:])
                self.assertEqual(len(self.last)-count, json.loads((archive/'receipt.json').read_text())['appendedBytes'])

    def test_live_reader_waits_for_newline_even_if_partial_row_ends_in_brace(self):
        self.path.write_bytes(self.first + b'{"nested":{}')
        self.assertEqual([json.loads(self.first)], trace.live_rows(self.root,'node-1'))

    def test_live_reader_rejects_malformed_complete_row(self):
        self.path.write_bytes(self.first + b'{bad}\n')
        with self.assertRaises(ValueError): trace.live_rows(self.root,'node-1')

    def test_unpublished_staging_file_is_not_a_recovery_source(self):
        self.path.write_bytes(self.first)
        self.path.with_name(self.path.name+'.staging').write_bytes(b'partial staging')
        self.finish(); self.assertEqual(self.first,self.path.read_bytes())
        self.path.write_bytes(self.first+self.last[:8192])
        self.reject('lacks published record')

    def test_running_process_is_never_completed(self):
        self.publish(); self.proc.poll=lambda: None; self.reject('still running')

    def test_corrupt_header_and_digest_fail_closed(self):
        for position, message in ((0,'header'), (16,'digest'), (100,'digest')):
            with self.subTest(position=position):
                self.publish(); raw=bytearray(self.pending.read_bytes()); raw[position]^=1; self.pending.write_bytes(raw)
                self.reject(message)

    def test_wrong_process_generation_or_node_fails_closed(self):
        for key,value in (('pid',42),('generation',2),('node','node-2')):
            with self.subTest(key=key):
                row=json.loads(self.last); row[key]=value
                self.publish(line=(json.dumps(row)+'\n').encode()); self.reject('process identity')

    def test_non_boundary_or_out_of_range_offset_fails_closed(self):
        for offset in (1, len(self.first)-1, 1<<40):
            with self.subTest(offset=offset): self.publish(offset=offset); self.reject('offset')

    def test_divergent_append_and_extra_bytes_fail_closed(self):
        self.publish(); self.path.write_bytes(self.first+b'?'+self.last[1:8192]); self.reject('differs')
        self.publish(len(self.last)); self.path.write_bytes(self.first+self.last+b'extra'); self.reject('offset')

    def test_missing_event_is_not_reconstructed_from_a_later_one(self):
        row=json.loads(self.last); row['order']=3
        self.publish(line=(json.dumps(row)+'\n').encode()); self.reject('discontinuity')

    def test_invalid_published_json_or_multiple_rows_fail_closed(self):
        self.publish(line=b'{bad}\n'); self.reject('property name')
        self.publish(line=self.last+self.last); self.reject('pending line')

    def test_first_row_of_new_generation_can_complete_after_previous_owner(self):
        self.last=self.line(order=1,event='STARTED',payload='x'*32768)
        row=json.loads(self.last); row.update(pid=42,generation=2); self.last=(json.dumps(row)+'\n').encode()
        self.publish(); self.proc.pid=42
        trace.finish(self.root,'node-1',self.proc,2)
        self.assertEqual(self.first+self.last,self.path.read_bytes())

    def test_first_observation_can_complete_before_jsonl_exists(self):
        self.first=b''; self.last=self.line(order=1,event='STARTED')
        self.publish(0); self.path.unlink(); self.finish()
        self.assertEqual(self.last,self.path.read_bytes())


if __name__ == '__main__': unittest.main()

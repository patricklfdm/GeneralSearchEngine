import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import retention_quorum_evidence as e


class RetentionQuorumEvidenceTest(unittest.TestCase):
    def test_ack_binds_exact_request_and_local_durable_bytes(self):
        # Syntax-only fixture: no assertion that these rows are an actual quorum.
        from .format_fixture import generate
        sent = next(v['value'] for v in generate()['fixtures'] if v['name'] == 'RETENTION_INTENT')
        intent, ledger = 'a'*64, b'actual-local-record'
        value = dict(sent, sender=sent['recipient'], recipient=sent['sender'],
                     payload=dict(intent=intent, revision=1, ledger=e.sha(ledger)))
        raw = e.f.encode('wire', 'RETENTION_ACK', value)
        e.response(raw, sent, intent, ledger)
        for field in ('intent', 'ledger', 'revision'):
            bad = copy.deepcopy(value)
            bad['payload'][field] = 2 if field == 'revision' else 'b'*64
            with self.assertRaisesRegex(ValueError, 'exact durable acknowledgement'):
                e.response(e.f.encode('wire', 'RETENTION_ACK', bad), sent, intent, ledger)
        with self.assertRaisesRegex(ValueError, 'exact durable acknowledgement'):
            e.response(raw, dict(sent, sequence=sent['sequence']+1), intent, ledger)

    def test_unknown_wire_fields_and_truncated_frames_are_rejected(self):
        from .format_fixture import generate
        row = next(v for v in generate()['fixtures'] if v['name'] == 'RETENTION_ACK')
        raw = bytes.fromhex(row['hex'])
        for broken in (raw[:-1], raw[:47], raw[:-1]+bytes([raw[-1] ^ 1])):
            with self.assertRaises(ValueError): e.f.decode(broken, 'wire', 'RETENTION_ACK')
        bad = copy.deepcopy(row['value']); bad['payload']['extra'] = True
        with self.assertRaises(ValueError): e.f.encode('wire', 'RETENTION_ACK', bad)

    def test_original_failure_cannot_be_counted_as_negative_success(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(e, 'validate', side_effect=ValueError('original invalid')) as validate, patch.object(e.shutil, 'copytree') as copies:
                with self.assertRaisesRegex(ValueError, 'original invalid'): e.qualify(Path(temp))
                validate.assert_called_once(); copies.assert_not_called()


if __name__ == '__main__': unittest.main()

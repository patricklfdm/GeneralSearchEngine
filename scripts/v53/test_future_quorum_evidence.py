import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import future_quorum_evidence as q
from .format_fixture import generate


class FutureQuorumEvidenceTest(unittest.TestCase):
    def test_ack_cannot_substitute_another_owner_store_or_request(self):
        # Codec fixture only; actual ownership/force comes from original replay.
        sent = next(row['value'] for row in generate()['fixtures'] if row['name'] == 'FUTURE_RETENTION_INTENT')
        intent, retained = 'a'*64, b'local-native-proof'
        response = dict(sent, sender=sent['recipient'], recipient=sent['sender'],
                        payload=dict(intent=intent, storage='FUTURE', revision=1, digest=q.e.digest(retained)))
        raw = q.f.encode('wire', 'FUTURE_RETENTION_ACK', response)
        q.acknowledgement(raw, sent, intent, retained)
        for field, value in [('intent', 'b'*64), ('storage', 'CURRENT'), ('revision', 2), ('digest', 'b'*64)]:
            bad = copy.deepcopy(response); bad['payload'][field] = value
            with self.assertRaisesRegex(ValueError, 'exact native acknowledgement'):
                q.acknowledgement(q.f.encode('wire', 'FUTURE_RETENTION_ACK', bad), sent, intent, retained)
        with self.assertRaisesRegex(ValueError, 'exact native acknowledgement'):
            q.acknowledgement(raw, dict(sent, sequence=sent['sequence']+1), intent, retained)
        with self.assertRaisesRegex(ValueError, 'exact native acknowledgement'):
            q.acknowledgement(raw, sent, intent, retained+b'changed')

    def test_both_negative_drivers_validate_original_before_copying(self):
        for reader, qualify in [('validate', q.qualify), ('processes', q.qualify_processes)]:
            with self.subTest(reader=reader), tempfile.TemporaryDirectory() as temp:
                with patch.object(q, reader, side_effect=ValueError('invalid original')) as original, patch.object(q.shutil, 'copytree') as copies:
                    with self.assertRaisesRegex(ValueError, 'invalid original'): qualify(Path(temp))
                    original.assert_called_once(); copies.assert_not_called()

    def test_new_controls_reject_unknown_fields_and_corrupted_frames(self):
        for row in generate()['fixtures']:
            if row['name'] not in ('FUTURE_RETENTION_INTENT', 'FUTURE_RETENTION_ACK'): continue
            raw = bytes.fromhex(row['hex'])
            for damaged in (raw[:-1], raw[:47], raw[:-1]+bytes([raw[-1]^1])):
                with self.assertRaises(ValueError): q.f.decode(damaged, 'wire', row['name'])
            bad = copy.deepcopy(row['value']); bad['payload']['extra'] = True
            with self.assertRaises(ValueError): q.f.encode('wire', row['name'], bad)


if __name__ == '__main__': unittest.main()

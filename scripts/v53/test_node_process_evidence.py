from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import node_process_evidence as p


class NodeProcessEvidenceTest(unittest.TestCase):
    def result(self, mode='kill'):
        rows = [dict(life=i, pid=100+i, started=dict(life=i, pid=100+i, mode=mode),
                     exit=(137 if mode == 'kill' else 73) if i == 1 else 0) for i in (1, 2)]
        rows[0].update(lockHeldBeforeDeath=True, lockReleasedAfterDeath=True); rows[1]['drained'] = True
        return dict(mode=mode, cut='AFTER_DATA_RETURN', children=rows, status='PARTIAL', powerLoss=False, phase3Complete=False)

    def test_both_observed_process_modes_require_distinct_successor(self):
        for mode in ('halt', 'kill'):
            result = self.result(mode)
            self.assertEqual(result['children'], p.children(result))

    def test_normal_exit_or_missing_original_lock_cannot_count_as_crash(self):
        for key, value in [('exit', 0), ('lockHeldBeforeDeath', False), ('lockReleasedAfterDeath', False)]:
            with self.subTest(key=key):
                result = self.result(); result['children'][0][key] = value
                with self.assertRaisesRegex(ValueError, 'exact death and drain'): p.children(result)

    def test_reused_or_boolean_pid_is_not_a_fresh_process(self):
        for value in (101, True):
            result = self.result(); result['children'][1]['pid'] = value
            with self.assertRaisesRegex(ValueError, 'fresh child identities'): p.children(result)

    def test_numeric_true_and_invented_complete_scope_are_rejected(self):
        result = self.result(); result['children'][0]['lockHeldBeforeDeath'] = 1
        with self.assertRaisesRegex(ValueError, 'exact death and drain'): p.children(result)
        for key in ('powerLoss', 'phase3Complete'):
            result = self.result(); result[key] = True
            with self.assertRaisesRegex(ValueError, 'producer scope'): p.children(result)

    def test_original_failure_cannot_become_a_negative_success(self):
        with (patch.object(p, 'inventory'), patch.object(p.net, 'validate', side_effect=ValueError('original failed')),
                patch.object(p, 'configuration') as configuration, patch.object(p.shutil, 'copytree') as copied):
            with self.assertRaisesRegex(ValueError, '^original failed$'): p.qualify('unused')
            configuration.assert_not_called(); copied.assert_not_called()

    def test_link_is_rejected_before_process_or_physical_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'target').write_text('data'); (root/'linked').symlink_to('target')
            with patch.object(p.net, 'validate') as validate:
                with self.assertRaisesRegex(ValueError, 'regular inventory'): p.validate(root)
                validate.assert_not_called()

    def test_transcript_requires_complete_canonical_records(self):
        message = dict(action='opened', value=1); raw = p.f.canonical(message)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'stdout'; path.write_bytes(raw+b'\n')
            self.assertEqual([message], p.transcript(path))
            for bad, reason in [(raw, 'complete bounded'), (raw+b'\n\n', 'transcript lines'),
                                (b'{"action": "opened", "value": 1}\n', 'noncanonical evidence')]:
                path.write_bytes(bad)
                with self.assertRaisesRegex(ValueError, reason): p.transcript(path)


if __name__ == '__main__': unittest.main()

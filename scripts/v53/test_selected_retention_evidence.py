import copy
import tempfile
import unittest
from pathlib import Path
from . import selected_retention_evidence as e


class SelectedRetentionEvidenceTest(unittest.TestCase):
    def state(self, ends=(0,), revision=0):
        return e.r.frame(dict(root='a'*64, owner={'node': 'local'}, revision=revision,
            previous='b'*64 if revision else None, plan=dict(root='a'*64, view={'generation': 0},
            peers=[dict(identity={'node': 'peer'}, possible=[dict(cut={'index': n}, catalog=str(n), application='image') for n in ends])])))

    def test_selected_later_cut_does_not_remove_uncertain_old_endpoint(self):
        before, remote = self.state(), self.state((1,), 20)
        merged = e.r.decode(e.merged(before, [remote])); self.assertEqual(1, merged['revision'])
        self.assertEqual(e.sha(before), merged['previous'])
        self.assertEqual([0, 1], [v['cut']['index'] for v in merged['plan']['peers'][0]['possible']])
        self.assertEqual(before, e.merged(before, [before]))

    def test_conflicting_original_or_third_endpoint_refuses(self):
        before = self.state((0, 1)); bad = e.r.decode(before)
        bad['plan']['peers'][0]['possible'][0]['catalog'] = 'conflict'
        with self.assertRaisesRegex(ValueError, 'conflicting endpoint'):
            e.merged(before, [e.r.frame(bad)])
        with self.assertRaisesRegex(ValueError, 'endpoint bound'):
            e.merged(before, [self.state((2,))])

    def test_foreign_root_view_or_permanent_identity_refuses(self):
        before = self.state(); original = e.r.decode(before)
        for field in ('root', 'view', 'identity'):
            bad = copy.deepcopy(original)
            if field == 'root': bad['root'] = bad['plan']['root'] = 'c'*64
            elif field == 'view': bad['plan']['view']['generation'] += 1
            else: bad['plan']['peers'][0]['identity']['node'] = 'replacement'
            with self.assertRaises(ValueError): e.merged(before, [e.r.frame(bad)])

    def test_force_order_is_causal_and_requires_every_boundary(self):
        required = ['force', 'rename', 'parent', 'return']
        e.ordered(required, required, 'fixture')
        for bad in (required[:-1], list(reversed(required)), ['force', 'rename', 'return']):
            with self.assertRaisesRegex(ValueError, 'force order'):
                e.ordered(bad, required, 'fixture')

    def test_original_is_checked_before_mutating_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises((ValueError, FileNotFoundError)):
                e.qualify(Path(temp))


if __name__ == '__main__': unittest.main()

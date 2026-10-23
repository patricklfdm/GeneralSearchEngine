"""Protected join orchestration with synthetic collectors and physical results.

Real object decoding, provenance negatives and physical replay have independent
tests. These fixtures cannot demonstrate an actual protected/cloud acceptance.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_acceptance as c
from .test_cloud_member_seal import fixture
from .test_cloud_set_evidence import fixture as whole_set


class AcceptanceTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        _, self.replayed, _, _, _ = whole_set(); self.selected = {}; self.records = {}; self.values = []
        ledger = None
        for i, name in enumerate(c.suite.MEMBERS, 1):
            f = fixture(member=name, attempt=f'{i:032x}', baseline=ledger)
            f['ledger']['generation'] = 10+i; f['context'].update(runId=1000+i, runAttempt=1)
            seal = c.seal.create(**f); self.cfg = f['cfg']; self.bound = f['source']; self.ledger = f['ledger']
            ledger = dict(generation=f['ledger']['generation'], ledger=f['ledger']['value'])
            self.selected[name] = dict(requestSha256=seal['requestSha256'], runId=1000+i, runAttempt=1)
            self.records[name] = dict(status='ORIGINAL_RUNNER_VERIFIED_NOT_QUALIFIED', seal=seal)
            self.values.append(dict(root=str(self.root/name), request=f['request'], manifest=f['manifest'], completed=f['completed'], cleanup=f['clean']))
        self.calls = []; self.mutate = lambda:None
    def restore(self, source, selected, output, **kw):
        self.calls.append('restore')
        self.assertEqual({k:v['requestSha256'] for k,v in self.selected.items()}, selected)
        (output/'originals').mkdir(parents=True); c.artifacts.save(output/'originals/ledger-after.json', self.ledger)
        return dict(inputs=deepcopy(self.values), ledger=self.ledger['value'], receipt=dict(status='ORIGINALS_RESTORED_NOT_QUALIFIED', execution='native-v52-evidence-reads'))
    def provenance(self, source, request, chosen, output):
        name = request['selection']['member']['name']; self.calls.append('runner:'+name)
        self.assertEqual({k:self.selected[name][k] for k in ('runId','runAttempt')}, chosen)
        return deepcopy(self.records[name])
    def physical(self, root, req, manifest, completed, clean, ledger, source, cfg, output, **kw):
        name = req['selection']['member']['name']; self.calls.append('replay:'+name)
        output.mkdir(); c.artifacts.save(output/'receipt.json', self.replayed[name]); self.mutate()
        return deepcopy(self.replayed[name])
    def execute(self):
        self.output = self.root/('accept-'+str(len(list(self.root.iterdir()))))
        with patch.object(c.reads, 'source_configuration', side_effect=lambda source:deepcopy(self.cfg)), \
             patch.object(c.inputs, 'checkout', return_value=self.bound), patch.object(c.runners, 'contract', return_value='fixture workflow'), \
             patch.object(c.objects, 'restore_native', side_effect=self.restore), patch.object(c.runners, 'collect_native', side_effect=self.provenance), \
             patch.object(c.evidence.member, 'replay', side_effect=self.physical), patch.object(c.member.Progress, 'report'):
            return c.verify_native('a'*40, self.selected, self.output)
    def test_only_complete_original_join_can_promote_and_preserves_all_totals(self):
        result = self.execute(); self.assertEqual('PASS', result['status']); self.assertTrue(result['fullRemoteQualification'])
        self.assertEqual(27428, result['totals']['reads']); self.assertEqual(2760, result['totals']['updates'])
        self.assertEqual(439, result['totals']['formalNegativesPerLocation'])
        self.assertEqual(19, len(self.calls)); self.assertFalse(result['paidCloud'])
        self.assertEqual(36_000_000, result['ledgerReservedCostMicrousd'])
    def test_any_whole_member_order_is_permitted(self):
        for first in range(len(c.suite.MEMBERS)):
            self.values = self.values[1:]+self.values[:1]; self.calls = []
            result = self.execute(); self.assertEqual('PASS', result['status'])
            self.assertEqual('replay:'+self.values[0]['request']['selection']['member']['name'], self.calls[len(c.suite.MEMBERS)+1])
    def test_missing_or_duplicate_selection_rejects_before_native_reads(self):
        for change in (lambda v:v.pop('experiment'), lambda v:v.update(experiment=v['canonical-1']),
                       lambda v:v['experiment'].update(runAttempt=True)):
            chosen = deepcopy(self.selected); change(chosen)
            with patch.object(c.objects, 'restore_native') as restore, self.assertRaises(ValueError):
                c.verify_native('a'*40, chosen, self.root/'rejected')
            restore.assert_not_called()
    def test_wrong_seal_or_original_objects_stop_before_expensive_replay(self):
        self.records['experiment']['seal']['completionSha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'immutable object'): self.execute()
        self.assertFalse(any(v.startswith('replay:') for v in self.calls))
        result = c.artifacts.read(self.output/'receipt.json'); self.assertEqual('FAIL', result['status']); self.assertFalse(result['fullRemoteQualification'])
    def test_different_replayed_invocation_is_rejected_and_not_retried(self):
        self.replayed['experiment']['invocation']['attempt'] = 2
        with self.assertRaisesRegex(ValueError, 'original protected invocation'): self.execute()
        self.assertEqual(1, self.calls.count('replay:experiment'))
        self.assertFalse(c.artifacts.read(self.output/'receipt.json')['fullRemoteQualification'])
    def test_original_physical_failure_or_final_source_change_never_promotes(self):
        def fail(): raise ValueError('original physical error')
        self.mutate = fail
        with self.assertRaisesRegex(ValueError, 'original physical'): self.execute()
        self.assertFalse(c.artifacts.read(self.output/'receipt.json')['fullRemoteQualification'])
        self.mutate = lambda:self.cfg.update(projectNumber='999999')
        with self.assertRaisesRegex(ValueError, 'source changed'): self.execute()
        self.assertFalse(c.artifacts.read(self.output/'receipt.json')['fullRemoteQualification'])


if __name__ == '__main__': unittest.main()

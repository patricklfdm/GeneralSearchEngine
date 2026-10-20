"""Original prepare factory with real decoders and modeled external API effects."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import cloud_prepare as p
from . import test_cloud_native_runner as fixture
from .test_cloud_identity import public_key


class PrepareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.NativeRunnerTest.setUpClass()
    def setUp(self):
        self.base = fixture.NativeRunnerTest(); self.base.setUp(); self.addCleanup(self.base.doCleanups)
        self.request = dict(member='canonical-3', sequence='c'*32, estimate=deepcopy(self.base.arguments['quote']))
        self.count = 0
    def execute(self):
        self.count += 1; self.output = self.base.root/f'prepare-{self.count}'
        def controls(output):
            output.mkdir()
            for name in p.inputs.CONTROL_NAMES: (output/name).write_bytes(('synthetic-'+name).encode())
        with patch.object(p.controls, 'resolve', side_effect=controls):
            return p.prepare_native('a'*40, self.request, public_key(), self.output)
    def test_original_build_package_preflight_cleanup_produce_only_unconfirmed_plan(self):
        result = self.execute(); self.assertEqual('PREPARED_NOT_ADMITTED', result['status'])
        self.assertFalse(result['paidAdmission']); self.assertEqual([], self.base.mutations())
        self.assertEqual({}, self.base.case.server.resources); self.assertEqual({}, self.base.case.server.objects)
        files = {v.name:v.read_bytes() for v in (self.output/'public').iterdir()}
        receipt = p.package.validate(files, self.base.cfg, self.base.arguments['proof']['source'], dict(runId=654321,runAttempt=2), now=fixture.NOW)
        self.assertFalse(p.artifacts.read(self.output/'public/approval.json')['confirmed'])
        plan = p.artifacts.read(self.output/'public/plan.json'); self.assertEqual('canonical-3',plan['request']['selection']['member']['name'])
        self.assertEqual(result['planSha256'],receipt['planSha256'])
    def test_active_lease_blocks_public_preparation_without_mutation(self):
        self.base.case.prepared(active=True); original = deepcopy(self.base.case.server.objects)
        with self.assertRaisesRegex(ValueError, 'native preflight unavailable'): self.execute()
        self.assertEqual(original,self.base.case.server.objects); self.assertEqual([], self.base.mutations())
        self.assertFalse((self.output/'public').exists()); self.assertTrue((self.output/'failure.json').exists())
    def test_independent_second_build_replay_keeps_check_diagnostics(self):
        original=p.artifacts.replay; calls=[]
        def replay(*args,**kwargs):
            calls.append(True)
            if len(calls)==2: raise ValueError('private-check-detail')
            return original(*args,**kwargs)
        with patch.object(p.artifacts,'replay',side_effect=replay):
            with self.assertRaisesRegex(ValueError,'private-check-detail'): self.execute()
        failure=p.artifacts.read(self.output/'build/failure.json')
        self.assertEqual('artifact-replay',failure['phase'])
        self.assertEqual('V52_PROVENANCE_ARTIFACT_REPLAY_REJECTED',failure['code'])
        self.assertNotIn('private-check-detail',str(failure));self.assertEqual(2,len(calls))
        self.assertFalse((self.output/'public').exists());self.assertEqual([],self.base.mutations())
    def test_expired_or_foreign_estimate_rejects_without_public_plan_or_resources(self):
        self.request['estimate']['configurationSha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'configuration/layout'): self.execute()
        self.assertFalse((self.output/'public').exists()); self.assertEqual([], self.base.mutations())


if __name__ == '__main__': unittest.main()

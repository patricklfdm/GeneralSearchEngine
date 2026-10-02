from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_cleanup_fixture as f, cloud_cleanup_fixture_qualification as q
from . import cloud_preflight as p, remote_command as c, performance_model as m


class CleanupFixtureReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.cfg=c.read(p.CONFIG); self.source='c'*40

    def test_review_preserves_native_limits_and_is_never_approval(self):
        plan=f.plan(self.cfg,self.source)
        self.assertEqual((1,100,0,0),(plan['resource']['maximumCount'],plan['resource']['sizeGiB'],
                                    plan['resource']['instances'],plan['resource']['firewalls']))
        self.assertEqual((5400,1080),(plan['authority']['leaseSeconds'],plan['authority']['graceSeconds']))
        self.assertEqual(['n1-data'],plan['authority']['attemptedRows'])
        self.assertFalse(plan['authority']['backdatingAllowed']);self.assertFalse(plan['authority']['ledgerResetAllowed'])
        self.assertFalse(plan['budget']['priceQualified']);self.assertFalse(plan['budget']['hardProviderSpendingCap'])
        self.assertEqual(200_000_000,plan['budget']['cumulativeCeilingMicrousd'])
        self.assertEqual(1_000_000,plan['budget']['proposedReservationMicrousd'])
        self.assertFalse(plan['objectProbes']['realProbeDriverAvailable'])
        for name in f.BOUNDARY:self.assertIs(plan[name],False)

    def test_plan_generation_never_executes_provider_or_git_commands(self):
        with (patch('subprocess.run',side_effect=AssertionError('subprocess')),
              patch('subprocess.check_output',side_effect=AssertionError('subprocess'))):
            expected=f.write(self.root/'review',self.cfg,self.source)
            self.assertEqual(expected,f.validate(self.root/'review',self.cfg,self.source))

    def test_rehashed_unsafe_plan_cannot_pass(self):
        changes=[lambda v:v['resource'].update(maximumCount=3),lambda v:v['resource'].update(instances=1),
                 lambda v:v['authority'].update(leaseSeconds=60),lambda v:v['authority'].update(backdatingAllowed=True),
                 lambda v:v['authority'].update(completionStatus='PASS'),lambda v:v.update(paidAdmission=True),
                 lambda v:v['budget'].update(priceQualified=True),
                 lambda v:v['objectProbes'].update(writeDeletePrecondition=None,expectedDenial=412)]
        for i,change in enumerate(changes):
            with self.subTest(i=i):
                root=self.root/str(i);f.write(root,self.cfg,self.source)
                value=c.read(root/'plan.json');change(value);(root/'plan.json').write_bytes(m.canonical(value)+b'\n')
                receipt=c.read(root/'review.json');receipt['files']['plan.json']=m.sha((root/'plan.json').read_bytes())
                (root/'review.json').write_bytes(m.canonical(receipt)+b'\n')
                with self.assertRaises(ValueError):f.validate(root,self.cfg,self.source)

    def test_create_only_source_config_and_inventory_checks(self):
        root=self.root/'review';f.write(root,self.cfg,self.source)
        with self.assertRaises(FileExistsError):f.write(root,self.cfg,self.source)
        with self.assertRaises(ValueError):f.validate(root,self.cfg,'d'*40)
        cfg=c.read(p.CONFIG);cfg['provider']['project']='different-project'
        with self.assertRaises(ValueError):f.validate(root,cfg,self.source)
        (root/'extra').touch()
        with self.assertRaises(ValueError):f.validate(root,self.cfg,self.source)
        (root/'extra').unlink();(root/'plan.json').unlink()
        with self.assertRaises(ValueError):f.validate(root,self.cfg,self.source)

    def test_symlinked_payload_manifest_and_workflow_destination_fail(self):
        for name in ('plan.json','review.json'):
            root=self.root/name;f.write(root,self.cfg,self.source)
            original=(root/name).read_bytes();(root/name).unlink()
            other=self.root/(name+'.original');other.write_bytes(original);(root/name).symlink_to(other)
            with self.assertRaises(ValueError):f.validate(root,self.cfg,self.source)
        github=self.root/'.github';github.mkdir();alias=self.root/'alias';alias.symlink_to(github)
        for root in (github/'review',alias/'review'):
            with self.assertRaises(ValueError):f.write(root,self.cfg,self.source)

    def test_no_native_request_or_lease_is_emitted_as_execution_authority(self):
        root=self.root/'review';f.write(root,self.cfg,self.source)
        self.assertEqual({'plan.json','review.json','REVIEW.md'},{v.name for v in root.iterdir()})
        self.assertNotIn('requestSha256',c.read(root/'plan.json'))
        self.assertIn('exact-fixture-request-approval',c.read(root/'plan.json')['prerequisites'])

    def test_offline_single_disk_matrix_preserves_failed_costs_and_never_qualifies_cloud(self):
        with patch('subprocess.run',side_effect=AssertionError('subprocess')):
            result=q.qualify(self.root/'qualification',self.source)
        self.assertEqual(list(f.CASES),[v['case'] for v in result['cases']])
        self.assertTrue(all(v['status']=='PASS' and v['retainedCostMicrousd']==1_000_123 for v in result['cases']))
        self.assertEqual('offline-single-disk-cleanup-qualification',result['execution'])
        for key in f.BOUNDARY:self.assertIs(result[key],False)


if __name__=='__main__': unittest.main()

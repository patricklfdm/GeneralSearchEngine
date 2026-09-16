"""Lifecycle failure matrix, admission negatives and exact GCP mutation contracts."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch
from .cloud_bundle import extract
from .cloud_common import canonical, plan, request, resources, sha
from .cloud_fake import Fake, FakeProbe
from .cloud_gcp import Api, ApiError, Gcp
from .cloud_preflight import PROJECT_PERMISSIONS, STORAGE_PERMISSIONS, admission, check_observations, claims, condition_allows_only
from .cloud_runner import BUDGET, LEASE, Runner, reconcile, reserve_budget


def observations(p):
    return dict(github=dict(master='a' * 40, ciHead='a' * 40, ciStatus='completed', ciConclusion='success', runnerGate='success',
        cleanup=dict(head='a' * 40, conclusion='success', stepConclusion='success', updatedAt=1000),
        jobs={k: 'success' for k in ('Reactor tests', 'Compatibility', 'Release artifacts', 'Cloud runner (no GCP)', 'Required')}),
        principal=p['serviceAccount'], provider=dict(state='ACTIVE', oidc=dict(issuerUri='https://token.actions.githubusercontent.com'),
            attributeCondition=' && '.join("assertion." + k + " == '" + v + "'" for k, v in claims(p).items())),
        image=dict(id=p['imageId'], status='READY', architecture='X86_64'), machine=dict(guestCpus=8, memoryMb=32768), zone=dict(status='UP'),
        project=dict(quotas=[dict(metric=k, usage=0, limit=v) for k, v in [('CPUS_ALL_REGIONS', 32), ('FIREWALLS', 100)]]),
        region=dict(quotas=[dict(metric=k, usage=0, limit=v) for k, v in [('N2_CPUS', 200), ('CPUS', 200), ('SSD_TOTAL_GB', 500)]]),
        subnetwork=dict(network='/networks/default', region='/regions/us-west4'), effectiveFirewalls=dict(firewalls=[]), regionalFirewalls={},
        permissions=dict(permissions=PROJECT_PERMISSIONS), storagePermissions=dict(permissions=STORAGE_PERMISSIONS),
        bucket=dict(name=p['bucket'], iamConfiguration=dict(uniformBucketLevelAccess=dict(enabled=True))),
        budget=dict(schema='gse-v50-budget-v1', reservations=[]))


class CloudRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.plan = plan(); self.req = request('a' * 40, 1, 1, 'b' * 64)

    def run_case(self, fault=None, label='evidence'):
        backend = Fake(self.plan, self.req, fault); probe = FakeProbe(backend)
        runner = Runner(backend, probe, self.root / label)
        return backend, probe, runner.run()

    def test_success_uses_private_three_volume_bootstrap_order_and_retains(self):
        backend, probe, state = self.run_case()
        self.assertEqual(state['status'], 'PASS'); self.assertFalse(backend.resources); self.assertNotIn(LEASE, backend.objects)
        calls = backend.calls
        self.assertLess(calls.index(('bootstrap', 1)), calls.index(('detach', self.req['owner'] + '-n2-data')))
        self.assertLess(calls.index(('unmount', 2)), calls.index(('detach', self.req['owner'] + '-n2-data')))
        self.assertLess(calls.index(('start', 3)), calls.index(('exercise', 3)))
        self.assertEqual(probe.stopped, [3, 2, 1]); self.assertTrue(any(k.endswith('/completion.json') for k in backend.objects))
        self.assertEqual(state['probeValidation']['execution'], 'fake-owned-runner-only')

    def test_failure_cleanup_continues_and_failure_is_retained(self):
        for fault in ('partial-create', 'startup-failure', 'unreachable', 'cancel'):
            with self.subTest(fault=fault):
                backend, probe, state = self.run_case(fault, fault)
                self.assertEqual(state['status'], 'FAIL'); self.assertEqual(state['cleanup']['status'], 'PASS')
                self.assertFalse(backend.resources); self.assertNotIn(LEASE, backend.objects)
                self.assertTrue(any(k.endswith('/completion.json') for k in backend.objects))

    def test_unknown_forbidden_foreign_reused_and_failed_deletions_hold_lease(self):
        for fault in ('unresolved-create', 'forbidden-read', 'foreign-owner', 'reused-id', 'delete-failure'):
            with self.subTest(fault=fault):
                backend, _, state = self.run_case(fault, fault)
                self.assertEqual(state['status'], 'FAIL'); self.assertEqual(state['cleanup']['status'], 'FAIL')
                self.assertIn(LEASE, backend.objects)
                before = len([c for c in backend.calls if c[0] == 'create'])
                next_state = Runner(backend, FakeProbe(backend), self.root / (fault + '-next')).run()
                self.assertEqual(next_state['status'], 'FAIL')
                self.assertEqual(before, len([c for c in backend.calls if c[0] == 'create']))

    def test_interrupted_upload_still_deletes_and_holds_lease(self):
        backend, _, state = self.run_case('upload-failure')
        self.assertFalse(backend.resources); self.assertEqual(state['cleanup']['status'], 'PASS')
        self.assertEqual(state['retention'], 'INCOMPLETE'); self.assertIn(LEASE, backend.objects)

    def test_reconciliation_rechecks_owner_ids_expiry_and_retains_receipt(self):
        backend, _, _ = self.run_case('delete-failure')
        with self.assertRaisesRegex(ValueError, 'active owner'): reconcile(backend, self.root / 'early')
        backend.fault = None
        with patch('scripts.v50.cloud_runner.time.time', return_value=time.time() + 6000):
            result = reconcile(backend, self.root / 'recovered')
        self.assertEqual(result['status'], 'PASS'); self.assertFalse(backend.resources); self.assertNotIn(LEASE, backend.objects)

    def test_expired_lease_never_automatically_admits_new_creation(self):
        backend = Fake(self.plan, self.req); backend.objects[LEASE] = ('99', b'{"expiresAt":0}')
        result = Runner(backend, FakeProbe(backend), self.root / 'held').run()
        self.assertEqual(result['status'], 'FAIL'); self.assertFalse(any(c[0] == 'create' for c in backend.calls))

    def test_preflight_admission_rejects_stale_forged_and_unfunded(self):
        receipt = check_observations(self.plan, observations(self.plan), self.req['source'], 1000)
        self.assertEqual(receipt['status'], 'READY_FOR_PAID_REVIEW')
        approval = dict(schema='gse-v50-paid-admission-v1', confirmed=True, requestSha256=sha(canonical(self.req)),
            preflightSha256=sha(canonical(receipt)), planSha256=sha(canonical(self.plan)), expiresAt=1900,
            maximumCostMicrousd=10_000_000, previousAttemptsCostMicrousd=0, priceSources=['https://cloud.google.com/compute/all-pricing'],
            pricedThroughTopologySeconds=5400, cleanupOverhangSeconds=1080,
            estimateIncludes=['three-vms', 'boot-disks', 'data-disks', 'control', 'evidence', 'cleanup', 'failed-attempts'])
        admission(self.plan, receipt, self.req, approval, now=1001)
        for changed in [dict(confirmed=False), dict(maximumCostMicrousd=40_000_001), dict(previousAttemptsCostMicrousd=31_000_000),
                        dict(requestSha256='c' * 64), dict(estimateIncludes=['three-vms']), dict(priceSources=[])]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                admission(self.plan, receipt, self.req, dict(approval, **changed), now=1001)
        with self.assertRaisesRegex(ValueError, 'stale'): admission(self.plan, receipt, self.req, approval, now=1901)
        forged = deepcopy(receipt); forged['observations']['region']['quotas'][0]['usage'] = 190
        with self.assertRaisesRegex(ValueError, 'not admitted'): admission(self.plan, forged, self.req, approval, now=1001)

    def test_readonly_findings_fail_closed(self):
        for key in ('github', 'principal', 'provider', 'image', 'machine', 'zone', 'region', 'project',
                    'subnetwork', 'effectiveFirewalls', 'regionalFirewalls', 'permissions', 'storagePermissions', 'bucket', 'budget'):
            value = observations(self.plan); value[key] = dict(error='403')
            with self.subTest(key=key): self.assertEqual(check_observations(self.plan, value, self.req['source'], 1001)['status'], 'BLOCKED')

    def test_watchdog_requires_executed_recent_cleanup_for_exact_source(self):
        for changes in [dict(head='b' * 40), dict(stepConclusion='skipped'), dict(conclusion='failure'), dict(updatedAt=-10000)]:
            value = observations(self.plan); value['github']['cleanup'].update(changes)
            with self.subTest(changes=changes): self.assertEqual(check_observations(self.plan, value, self.req['source'], 1001)['status'], 'BLOCKED')

    def test_wif_or_precedence_cannot_bypass_repository_guards(self):
        c = claims(self.plan); strict = observations(self.plan)['provider']['attributeCondition']
        condition_allows_only(strict, c)
        for unsafe in [strict + " || assertion.ref == 'refs/heads/master'", "assertion.workflow_ref == '" + c['workflow_ref'] + "'",
                       strict.replace("assertion.environment == 'cloud-benchmark'", 'true'), strict.replace('refs/heads/master', 'refs/heads/other')]:
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError): condition_allows_only(unsafe, c)

    def test_archive_rejects_links_escape_duplicate_and_expansion(self):
        for label, names in [('escape', ['../escape']), ('absolute', ['/tmp/escape']), ('duplicate', ['x', 'x'])]:
            archive = self.root / (label + '.tar.gz')
            with tarfile.open(archive, 'w:gz') as out:
                for name in names:
                    member = tarfile.TarInfo(name); member.size = 1; out.addfile(member, io.BytesIO(b'x'))
            with self.subTest(label=label), self.assertRaises(ValueError): extract(archive, self.root / label)

    def test_api_readonly_rejects_mutation_before_acquiring_credentials(self):
        with self.assertRaisesRegex(ValueError, 'paid admission'):
            Api().call('POST', 'https://compute.googleapis.com/compute/v1/projects/x/zones/y/instances', {})

    def test_budget_failed_attempts_remain_reserved_and_request_cannot_repeat(self):
        backend = Fake(self.plan, self.req)
        approval = dict(maximumCostMicrousd=25_000_000, previousAttemptsCostMicrousd=0)
        reserve_budget(backend, approval)
        with self.assertRaisesRegex(ValueError, 'already attempted'): reserve_budget(backend, approval)
        backend.request = request('a' * 40, 2, 1, 'c' * 64)
        with self.assertRaisesRegex(ValueError, 'budget changed'): reserve_budget(backend, approval)
        with self.assertRaisesRegex(ValueError, 'budget changed'):
            reserve_budget(backend, dict(maximumCostMicrousd=16_000_000, previousAttemptsCostMicrousd=25_000_000))
        reserve_budget(backend, dict(maximumCostMicrousd=15_000_000, previousAttemptsCostMicrousd=25_000_000))
        self.assertEqual(sum(v['maximumCostMicrousd'] for v in json.loads(backend.objects[BUDGET][1])['reservations']), 40_000_000)

    def test_gcp_404_is_absence_403_is_error(self):
        class Denied:
            def __init__(self, status): self.status = status
            def call(self, method, url): raise ApiError(self.status, method, url)
        row = resources(self.plan, self.req)[0]
        self.assertIsNone(Gcp(self.plan, self.req, self.root, api=Denied(404)).describe(row))
        with self.assertRaises(ApiError): Gcp(self.plan, self.req, self.root, api=Denied(403)).describe(row)

    def test_gcp_exact_private_instance_request_and_watchdog(self):
        calls = []
        class Capture:
            def call(_, method, url, body=None):
                calls.append((method, url, body))
                if method == 'POST': return dict(status='DONE', selfLink=url.split('/instances')[0] + '/operations/op')
                return dict(id='123', labels={'gse-owner': self.req['owner']})
        row = dict(resources(self.plan, self.req)[-1], requestId='12345678-1234-1234-1234-123456789012')
        Gcp(self.plan, self.req, self.root, api=Capture()).create(row)
        body = calls[0][2]
        self.assertEqual(body['networkInterfaces'][0]['accessConfigs'], []); self.assertEqual(body['serviceAccounts'], [])
        self.assertEqual(body['scheduling']['maxRunDuration']['seconds'], '5400')
        self.assertEqual(body['scheduling']['instanceTerminationAction'], 'DELETE'); self.assertTrue(body['disks'][0]['autoDelete'])
        self.assertIn('requestId=' + row['requestId'], calls[0][1])

    def test_real_evidence_rejects_fake_or_false_cleanup(self):
        from .cloud_evidence import validate
        from .cloud_common import save
        _, _, state = self.run_case()
        with self.assertRaisesRegex(ValueError, 'real completed lifecycle'): validate(self.root / 'evidence')
        state['execution'] = 'gcp-owned-runtime'
        state['cleanup']['checks'][0]['absent'] = False
        save(self.root / 'evidence/completion.json', state)
        with self.assertRaisesRegex(ValueError, 'cleanup'): validate(self.root / 'evidence')

    def test_vm_delete_refuses_auto_delete_of_foreign_attached_disk(self):
        rows = resources(self.plan, self.req); vm = dict(rows[-1], id='123'); disk = next(r for r in rows if r.get('node') == 3 and r['purpose'] == 'boot')
        class Changed:
            def call(_, method, url, body=None):
                self.assertEqual(method, 'GET', 'must refuse before DELETE')
                if '/instances/' in url:
                    return dict(id='123', labels={'gse-owner': self.req['owner']}, disks=[dict(source='https://compute.googleapis.com/disks/' + disk['name'])])
                return dict(id='456', labels={'gse-owner': 'someone-else'})
        with self.assertRaisesRegex(ValueError, 'changed disk'): Gcp(self.plan, self.req, self.root, api=Changed()).delete(vm, '123')

    def test_gcs_generation_guard_and_readback_detect_changed_content(self):
        calls = []
        class Corrupt:
            def call(_, method, url, body=None, **kwargs):
                calls.append((method, url))
                if method == 'POST' or 'alt=media' not in url: return dict(generation='7')
                return b'corrupt'
        adapter = Gcp(self.plan, self.req, self.root, api=Corrupt())
        with self.assertRaisesRegex(ValueError, 'read-back'): adapter.put_object('owned/receipt.json', b'original', '6')
        self.assertIn('ifGenerationMatch=6', calls[0][1]); self.assertIn('generation=7', calls[-1][1])


if __name__ == '__main__': unittest.main()

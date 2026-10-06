from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from . import cloud_runner_admission as r, cloud_runner_admission_qualification as q
from . import cloud_http as h, cloud_native_authority as n, performance_model as m
from .remote_command import read


class RunnerAdmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen = r.workload.load()
        loader = patch.object(r.workload, 'load', side_effect=lambda:deepcopy(frozen))
        loader.start(); cls.addClassCleanup(loader.stop)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.f = q.fixture(Path(self.tmp.name)/'inputs')
    def inspect(self): return q.inspect(self.f)
    def approve(self):
        self.f['approved'] = r.approval_template(self.f['value']); self.f['approved']['confirmed'] = True
        self.f['env']['RUNNER_EXPERIMENT_CONFIRMATION'] = self.f['approved']['planSha256']
    def context(self):
        f = self.f
        return r.context(f['cfg'],f['env'],q.pq.SOURCE,q.pq.SOURCE,f['preflight'],f['root'],f['value'],f['approved'],
            get=lambda p:deepcopy(f['data'][p]),now=f['clock'].wall())

    def test_original_request_is_bound_without_cloud_or_ledger_mutation(self):
        before = q.cleanup.snapshot(self.f['http']); value = self.inspect().result
        self.assertEqual('REQUEST_BOUND',value['status']); self.assertEqual('offline-runner-request-inspection',value['execution'])
        self.assertEqual(before,q.cleanup.snapshot(self.f['http']))
        self.assertEqual(['oidc','sts','impersonation'],[v['stage'] for v in self.f['issuer'].calls])
        self.assertTrue(all(row['method']=='GET' for row in self.f['http'].requests))
        for flag in r.FLAGS: self.assertIs(value[flag],False)
        self.assertEqual(self.f['value'],m.strict_json(m.canonical(self.f['value'])))

    def test_exact_unconfirmed_approval_and_confirmation_fail_before_exchange(self):
        original = deepcopy(self.f['approved'])
        for key, value in [('confirmed',False),('planSha256','0'*64),('requestSha256','0'*64),
                           ('maximumCostMicrousd',1),('previousCostMicrousd',1),('expiresAt',q.pq.NOW+9999)]:
            self.f['approved'] = dict(original,**{key:value})
            with self.subTest(key=key), self.assertRaises(ValueError): self.inspect()
        self.f['approved'] = original; self.f['env']['RUNNER_EXPERIMENT_CONFIRMATION'] = '0'*64
        with self.assertRaises(ValueError): self.inspect()
        self.assertEqual([],self.f['issuer'].calls); self.assertEqual([],self.f['http'].requests)

    def test_price_coverage_bounds_and_original_expiry(self):
        original = deepcopy(self.f['value'])
        for change in (lambda v:v['prices'].update(pricedThroughSeconds=6479),
            lambda v:v['prices'].update(retentionDays=29),lambda v:v['prices'].update(region='foreign'),
            lambda v:v['prices']['otherCostsMicrousd'].pop('network'),lambda v:v['prices']['sources'].update(compute='https://example.org/price'),
            lambda v:v['prices']['sources'].update(storage='https://cloud.google.com@evil.example/pricing'),
            lambda v:v['prices'].update(vmMicrousdPerHour=True),
            lambda v:v['resourcePlan']['reservation'].update(maximumCostMicrousd=200_000_001),
            lambda v:v['resourcePlan']['reservation'].update(maximumCostMicrousd=1),
            lambda v:v.update(paidAdmission=True)):
            value = deepcopy(original); change(value)
            with self.assertRaises((ValueError,KeyError)): r.validate_plan(value,self.f['clock'].wall())
        self.assertEqual(3_002_000,r.prices(original['prices'],self.f['clock'].wall()))
        self.f['clock'].sleep(900)
        with self.assertRaises(ValueError): self.inspect()
        self.assertEqual([],self.f['issuer'].calls)

    def test_changed_artifact_and_raw_precheck_block_before_credentials(self):
        for relative in ('originals/package.zip','permissions/receipt.json','preflight/provider.json'):
            path = self.f['root']/relative; raw = path.read_bytes(); path.write_bytes(b'{}')
            with self.subTest(path=relative), self.assertRaises((ValueError,KeyError)): self.inspect()
            path.write_bytes(raw)
        self.assertEqual([],self.f['issuer'].calls)

    def test_changed_ci_attempt_master_or_run_blocks_without_mutations(self):
        original = deepcopy(self.f['data'])
        changes = [lambda d:d['actions/runs/12'].update(run_attempt=3),
            lambda d:d['actions/runs/12'].update(conclusion='failure'),
            lambda d:d['branches/master']['commit'].update(sha='b'*40),
            lambda d:d['actions/runs/222'].update(run_attempt=3),
            lambda d:d['actions/artifacts/102'].update(expired=True)]
        for change in changes:
            self.f['data'] = deepcopy(original); change(self.f['data'])
            with self.assertRaises((ValueError,KeyError)): self.inspect()
        self.assertEqual([],self.f['issuer'].calls)

    def test_new_ci_run_during_inspection_is_not_hidden_by_previous_green(self):
        bound = self.context(); f = self.f
        tokens = r.credentials.Credentials(bound['binding'],f['env'],f['descriptor'],transport=f['issuer'],clock=f['clock'].seconds,wall=f['clock'].wall)
        api = r.ControlReads(f['cfg']['provider'],transport=q.auth.Provider(f['http']),tokens=tokens,clock=f['clock'].seconds,expires=f['clock'].seconds()+180)
        old = f['data']['actions/runs/12']; newer = dict(old,id=13,status='in_progress',conclusion=None)
        f['data']['actions/workflows/ci.yml/runs?branch=master&head_sha='+q.pq.SOURCE+'&per_page=100']['workflow_runs'].append(newer)
        f['data']['actions/runs/13'] = newer
        f['data']['actions/runs/13/attempts/2/jobs?per_page=100&page=1'] = f['data']['actions/runs/12/attempts/2/jobs?per_page=100&page=1']
        with self.assertRaises(ValueError):
            r.inspect(api,f['value'],bound,f['originals'],f['binding'],get=lambda p:deepcopy(f['data'][p]),wall=f['clock'].wall,offline_controls=f['controls'])
        self.assertEqual({},f['http'].objects)

    def test_current_lease_and_changed_ledger_rejected_read_only(self):
        for key, value in ((n.LEASE,dict(active=True)),(n.LEDGER,n.empty_ledger())):
            self.f['http'].objects = {key:(1,m.canonical(value),'application/json')}; before = deepcopy(self.f['http'].objects)
            with self.assertRaisesRegex(ValueError,'control state changed'): self.inspect()
            self.assertEqual(before,self.f['http'].objects)

    def test_ledger_recheck_detects_concurrent_change(self):
        http = self.f['http']; send = http.send; reads = 0
        def change(method,url,*args):
            nonlocal reads
            reads += 1
            if reads == 3: http.objects[n.LEDGER] = (2,m.canonical(n.empty_ledger()),'application/json')
            return send(method,url,*args)
        http.send = change
        with self.assertRaisesRegex(ValueError,'control state changed'): self.inspect()

    def test_historical_failed_cost_and_cumulative_ceiling_are_not_reset(self):
        v = self.f['value']; req = n.request(q.pq.SOURCE,'a'*64,r.g.config(self.f['cfg']['provider']),
            '1'*32,'2'*32,'experiment',now=q.pq.NOW,guest_access_sha256='3'*64)
        old = n.reserve(n.empty_ledger(),req,dict(previousCostMicrousd=0,maximumCostMicrousd=198_000_000))
        old = n.finish(old,req,dict(requestSha256=n.validate_request(req),status='FAIL'))
        with self.assertRaisesRegex(ValueError,'budget'):
            r.plan(self.f['cfg'],v['artifacts'],v['resourcePlan']['guestAccess'],v['prices'],[99,old],
                sequence='4'*32,now=self.f['clock'].wall(),maximum_cost=q.COST)
        self.assertEqual(198_000_000,n.inspect_ledger(old)[0])

    def test_wrong_oidc_attempt_issuer_denial_and_account_descriptor(self):
        self.f['issuer'].claim_changes['run_attempt'] = '1'
        with self.assertRaises(ValueError): self.inspect()
        self.f['issuer'].claim_changes.clear(); self.f['issuer'].fail = 'sts'
        with self.assertRaises(ValueError): self.inspect()
        self.f['issuer'].fail = None; self.f['descriptor']['audience'] += '-wrong'
        with self.assertRaises(ValueError): self.inspect()
        self.assertEqual([],self.f['http'].requests)

    def test_read_401_refresh_and_original_deadline(self):
        http = self.f['http']; send = http.send; calls = 0
        def once(method,url,*args):
            nonlocal calls
            calls += 1
            return (401,b'') if calls == 1 else send(method,url,*args)
        http.send = once; self.assertEqual('REQUEST_BOUND',self.inspect().result['status'])
        self.assertEqual(6,len(self.f['issuer'].calls))
        def late(method,url,*args):
            self.f['clock'].sleep(181); return send(method,url,*args)
        http.send = late
        with self.assertRaisesRegex(ValueError,'late response'): self.inspect()

    def test_mutation_and_foreign_reads_block_even_via_base_api(self):
        api = self.inspect().api; before = deepcopy(self.f['http'].requests)
        for method,url,body in [('POST',api.store.url(n.LEDGER),{}),('DELETE',api.store.url(n.LEASE),None),
            ('GET',api.store.url(n.LEDGER)+'?alt=media',None),('GET','https://compute.googleapis.com/compute/v1/projects/x',None)]:
            for call in (api.call,lambda *args,**kwargs:h.Api.call(api,*args,**kwargs)):
                with self.assertRaises(ValueError): call(method,url,body,deadline=api.clock()+30)
        self.assertEqual(before,self.f['http'].requests)

    def test_native_constructor_owns_boundaries_and_does_not_accept_injection(self):
        f = self.f; get = lambda path:deepcopy(f['data'][path]); original_read = read
        # Test wiring with synthetic provider responses, never claim live WIF/IAM.
        class Wire:
            offline = False
            def send(self,method,url,*args):
                return (q.auth.Provider(f['http']) if urlsplit(url).netloc == 'storage.googleapis.com' else f['issuer']).send(method,url,*args)
        pins = r.ci.ROOT/'docs/v5x/v5.1/published-controls.json'
        with patch.object(r.ci,'github',side_effect=get),patch.object(r.build,'binding',return_value=f['binding']) as bind,\
             patch.object(r.entry,'credential_file',return_value=f['descriptor']),patch.object(h,'Network',Wire),\
             patch.object(r.time,'time',side_effect=f['clock'].wall),patch.object(r.time,'monotonic',side_effect=f['clock'].seconds),\
             patch.dict(r.credentials._Exchange.__init__.__kwdefaults__,clock=f['clock'].seconds,wall=f['clock'].wall),\
             patch.object(r.artifacts.c,'read',side_effect=lambda path:f['controls'] if path == pins else original_read(path)):
            native = r.NetworkAdmission(f['cfg'],f['env'],q.pq.SOURCE,q.pq.SOURCE,f['preflight'],f['root'],f['value'],f['approved'],f['originals'])
        self.assertEqual('native-runner-request-inspection',native.result['execution'])
        bind.assert_called_once_with(r.ci.ROOT,q.pq.SOURCE)
        with self.assertRaises(TypeError): r.NetworkAdmission(transport=Wire())
        with self.assertRaisesRegex(ValueError,'offline constructors'):
            r.OfflineAdmission(f['cfg'],f['env'],q.pq.SOURCE,f['preflight'],f['root'],f['value'],f['approved'],f['originals'],f['binding'],
                transport=Wire(),issuer=f['issuer'],descriptor=f['descriptor'],clock=f['clock'].seconds,wall=f['clock'].wall,get=get)


if __name__ == '__main__': unittest.main()

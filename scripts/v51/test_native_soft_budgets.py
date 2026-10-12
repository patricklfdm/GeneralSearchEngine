"""Soft native budgets with real guards, fake clocks and no cloud execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_preset_timing as t, native_experiment_timing as timing
from . import cloud_native_authority as n, cloud_authority as a, performance_model as m
from . import cloud_runner_admission as admission, cloud_runner_retention as retention
from . import remote_command as c, remote_collection as parts, remote_budget
from . import test_native_presets as legacy


def request(member='canonical-1', *, attempt='e'*32, sequence='d'*32):
    value=legacy.request(member,'any-order',attempt)
    return dict(value,schema=t.SOFT_REQUEST_SCHEMA,timingProfile=t.allocation(member,soft=True)['profile'],
                timingPlanSha256=t.SOFT_PLAN_SHA256,sequence=sequence)


class TimingTest(unittest.TestCase):
    def test_review_hash_and_all_five_members_select_warning_thresholds(self):
        policy=Path('docs/v5x/v5.1/native-soft-budget-policy.json')
        self.assertEqual(t.SOFT_PLAN_SHA256,m.sha(policy.read_bytes()))
        frozen=c.read(policy)
        for member in t.MEMBERS:
            req=request(member);limits=t.validate(req)
            self.assertEqual(n.validate_request(req),t.request_sha(req))
            self.assertEqual(frozen['stageWarningsSeconds'][member],limits['limitsSeconds'])
            self.assertEqual(t.allocation(member)['cells'],limits['cells'])
            self.assertEqual(45000,limits['priceCoverageSeconds'])
            self.assertEqual(21600,timing.preparation(req))
            self.assertIsNone(limits['commandGuardSeconds'])
            lease=n.lease(req,101);n.validate_lease(lease)
            self.assertEqual((21701,1800),(lease['expiresAt'],lease['graceSeconds']))
            with self.assertRaises(ValueError):n.validate_lease(dict(lease,expiresAt=21702))
            from .guest_delivery_receiver import deadline_limit_nanos
            self.assertEqual(21600*10**9,deadline_limit_nanos(limits['profile']))

    def test_each_stage_and_control_overrun_warns_and_preserves_original_clock(self):
        for member in t.MEMBERS:
            allocation=t.allocation(member,soft=True)
            for name,limit in allocation['limitsSeconds'].items():
                with self.subTest(member=member,stage=name):
                    now=[0];budget=remote_budget.Budget(clock=lambda:now[0],profile=allocation['profile'])
                    if name=='control':now[0]=(limit+1)*10**9
                    else:
                        with budget.stage(name) as deadline:
                            self.assertEqual(21600*10**9,deadline);now[0]=(limit+1)*10**9
                    with budget.stage('cleanup' if name!='cleanup' else 'healthy' if member!='failure-drill' else 'leader-loss') as deadline:
                        self.assertEqual(21600*10**9,deadline);now[0]+=10**9
                    result=budget.finish()
                    self.assertEqual('PASS',result['status']);self.assertIn(name,result['warnings'])
                    self.assertEqual(result['elapsedNanos'],sum(result['spentNanos'].values()))

    def test_explicit_failure_is_not_masked_by_soft_overrun(self):
        now=[0];budget=remote_budget.Budget(clock=lambda:now[0],profile=t.allocation('canonical-1',soft=True)['profile'])
        with self.assertRaisesRegex(ValueError,'broken evidence'):
            with budget.stage('validation-retention'):
                now[0]=2500*10**9;raise ValueError('broken evidence')
        self.assertIn('validation-retention',budget.finish()['warnings'])
        with self.assertRaisesRegex(ValueError,'restart'):
            with budget.stage('validation-retention'):pass

    def test_fault_duration_and_legacy_request_semantics_are_preserved(self):
        for name in ('isolation','hold-controller'):
            self.assertEqual(timing.CONTROLS[name],timing.control(request(),name,1))
        for name in ('activation','convergence','rejoin','service-stop','progress','mode'):
            self.assertEqual(21600,timing.control(request(),name,1))
        old=legacy.request();self.assertEqual(600,timing.cell(old,'leader-loss'))
        self.assertEqual(21600,timing.cell(request(),'leader-loss'))
        bad=dict(old,schema=t.SOFT_REQUEST_SCHEMA)
        with self.assertRaises(ValueError):n.validate_request(bad)

    def test_trusted_guest_bundle_accepts_bound_soft_session_without_repository_imports(self):
        import base64,subprocess,sys
        from . import guest_native_session as session, guest_delivery_receiver as receiver
        from .cloud_runner_guest_setup import trusted_source
        desc,old_session=legacy.descriptor('canonical-3');volume=desc['nativeVolume']['request']
        req=volume['nativeRequest'];req.update(schema=t.SOFT_REQUEST_SCHEMA,
            timingProfile=t.allocation('canonical-3',soft=True)['profile'],timingPlanSha256=t.SOFT_PLAN_SHA256)
        volume['requestSha256']=n.validate_request(req)
        sample=receiver.clock_sample(session.identity(desc),'f'*32)
        bound=dict(old_session,packageSha256=m.sha(m.canonical(desc)),
            preparation=dict(schema='gse-v51-helper-deadline-v1',sample=sample,
                expiresNanos=sample['sampledNanos']+21600*10**9),leaseExpiresNanos=sample['sampledNanos']+21600*10**9)
        cfg=session.configuration(desc,bound,session.MODES[2],'entry-chosen')
        source=trusted_source('session').rsplit("sys.modules['trusted.guest_native_session'].main()",1)[0]
        encoded=base64.b64encode(m.canonical([desc,bound,cfg])).decode()
        source+="value,session,config=json.loads(base64.b64decode("+repr(encoded)+"))\n"
        source+="sys.modules['trusted.guest_native_volume'].validate(value['nativeVolume']['request'])\n"
        source+="sys.modules['trusted.guest_native_session'].check_config(config,value,session)\nprint('PASS')\n"
        with tempfile.TemporaryDirectory() as tmp:
            result=subprocess.run([sys.executable,'-I','-c',source],cwd=tmp,capture_output=True,text=True,timeout=30)
        self.assertEqual(0,result.returncode,result.stderr);self.assertEqual('PASS',result.stdout.strip())

    def test_healthy_running_observation_outlasts_threshold_without_resubmitting(self):
        from . import test_native_experiment_timing as fixtures
        test=fixtures.NativeWindowCommandTest();test.setUp();self.addCleanup(test.doCleanups)
        old=test.probe.services.provider.req
        test.probe.services.provider.req=dict(old,schema=t.SOFT_REQUEST_SCHEMA,
            timingProfile=t.allocation('canonical-1',soft=True)['profile'],timingPlanSha256=t.SOFT_PLAN_SHA256)
        test.ready=test.start+550
        with patch('builtins.print') as output:
            result=test.observe(seconds=1000)
        self.assertEqual('SUCCEEDED',result['state']);test.client.submit.assert_called_once()
        self.assertGreater(test.client.query.call_count,256)
        self.assertEqual({test.start+1000},set(test.deadlines));self.assertEqual(1,output.call_count)
        self.assertIn('WARNING',output.call_args.args[0])

    def test_soft_observation_keeps_fast_fail_and_original_identity_guards(self):
        from . import test_native_experiment_timing as fixtures
        for method in ('test_terminal_failure_is_returned_immediately_and_not_retried',
                       'test_repeated_transient_failures_still_fail_fast',
                       'test_repeated_uncertainty_and_permanent_transport_errors_still_fail_fast',
                       'test_window_identity_or_caller_supplied_timeout_cannot_select_headroom'):
            with self.subTest(case=method):
                test=fixtures.NativeWindowCommandTest();test.setUp()
                try:
                    old=test.probe.services.provider.req
                    test.probe.services.provider.req=dict(old,schema=t.SOFT_REQUEST_SCHEMA,
                        timingProfile=t.allocation('canonical-1',soft=True)['profile'],timingPlanSha256=t.SOFT_PLAN_SHA256)
                    getattr(test,method)()
                finally:test.doCleanups()


class LedgerTest(unittest.TestCase):
    def test_new_charges_cross_200_without_reset_and_pending_still_blocks(self):
        old=legacy.request('experiment','experiment-first')
        ledger=n.reserve(n.empty_ledger(),old,dict(previousCostMicrousd=0,maximumCostMicrousd=200_000_000))
        ledger=n.finish(ledger,old,dict(requestSha256=n.validate_request(old),status='FAIL'))
        req=request(attempt='1'*32,sequence='2'*32)
        ledger=n.reserve(ledger,req,dict(previousCostMicrousd=200_000_000,maximumCostMicrousd=250_000_000))
        self.assertEqual(450_000_000,n.inspect_ledger(ledger)[0])
        with self.assertRaisesRegex(ValueError,'unresolved'):
            n.reserve(ledger,request('experiment',attempt='3'*32),dict(previousCostMicrousd=450_000_000,maximumCostMicrousd=1))
        final=n.finish(ledger,req,dict(requestSha256=n.validate_request(req),status='FAIL'))
        self.assertEqual(450_000_000,n.inspect_ledger(final)[0])
        with self.assertRaisesRegex(ValueError,'failed canonical'):
            n.reserve(final,request('experiment',attempt='3'*32,sequence='2'*32),dict(previousCostMicrousd=450_000_000,maximumCostMicrousd=1))

    def test_legacy_ceiling_and_invalid_amounts_still_rejected(self):
        req=legacy.request()
        with self.assertRaises(ValueError):n.reserve(n.empty_ledger(),req,dict(previousCostMicrousd=0,maximumCostMicrousd=200_000_001))
        for cost in (True,0,-1,2**63):
            with self.subTest(cost=cost),self.assertRaises(ValueError):
                n.reserve(n.empty_ledger(),request(),dict(previousCostMicrousd=0,maximumCostMicrousd=cost))
        with self.assertRaisesRegex(ValueError,'stale budget'):
            n.reserve(n.empty_ledger(),request(),dict(previousCostMicrousd=1,maximumCostMicrousd=1))

    def test_price_overrun_is_visible_but_exact_approval_and_coverage_still_required(self):
        from . import cloud_runner_admission_qualification as fixture
        with tempfile.TemporaryDirectory() as tmp:
            frozen=admission.workload.load()
            with patch.object(admission.workload,'load',side_effect=lambda:deepcopy(frozen)):
                f=fixture.fixture(Path(tmp)/'input');old=f['value'];stage=old['resourcePlan'];now=stage['request']['createdAt']
                quote=dict(old['prices'],pricedThroughSeconds=45000)
                def plan(cost):return admission.plan(old['configuration'],old['artifacts'],stage['guestAccess'],quote,None,
                    sequence='d'*32,now=now,maximum_cost=cost,member='canonical-3',order='any-order',soft_budget=True)
                value=plan(1);self.assertTrue(value['budgetWarnings']['estimateExceedsReservation'])
                value=plan(250_000_000);self.assertTrue(value['budgetWarnings']['projectedExceedsThreshold'])
                from . import cloud_runner_entry as entry
                summary=Path(tmp)/'summary';(summary/'prepared').mkdir(parents=True)
                c.write_once(summary/'prepared/plan.json',value)
                c.write_once(summary/'receipt.json',dict(mode='prepare',status='PREPARED',result=dict(budget=dict(
                    spentNanos={'validation-retention':2501*10**9},warnings=['validation-retention']))))
                text=entry.summary(summary)
                self.assertIn('WARNING: cumulative estimate exceeds threshold',text)
                self.assertIn('| validation-retention | 2501.0 | 2400 | WARNING |',text)
                approved=admission.approval_template(value);approved['confirmed']=True
                admission.approval(value,approved,approved['planSha256'],now)
                with self.assertRaises(ValueError):admission.approval(value,dict(approved,maximumCostMicrousd=1),approved['planSha256'],now)
                with self.assertRaises(ValueError):admission.validate_plan(value,value['expiresAt'])
                quote['pricedThroughSeconds']=44999
                with self.assertRaisesRegex(ValueError,'coverage'):plan(1)

    def test_manual_cleanup_waits_for_original_lease_then_keeps_over_threshold_charge(self):
        from . import cloud_experiment_resource_qualification as q, cloud_gcp as g
        from . import cloud_cleanup_qualification as snapshots
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old,clock,http,reader,_=q.fixture();guest=old['guestAccess']
            req=n.request(old['request']['source'],old['request']['bundleSha256'],g.config(old['configuration']),
                old['request']['sequence'],guest['attempt'],'canonical-3',now=clock.wall(),order='any-order',
                guest_access_sha256=m.sha(m.canonical(guest)),timing_profile=t.allocation('canonical-3',soft=True)['profile'],
                timing_plan_sha256=t.SOFT_PLAN_SHA256)
            store=g.Store(old['configuration'],reader,authority=n);baseline=store.get(n.LEDGER)
            value=q.r.make(old['configuration'],req,guest,baseline,old['inputs'],now=clock.wall(),maximum_cost=250_000_000)
            api=q.r.OfflineApi(value,clock.wall(),transport=http,tokens=lambda _:'synthetic',clock=clock.seconds)
            self.assertEqual('RESOURCES_PREPARED',q.r.prepare(value,api,root/'prepare',now=clock.wall(),sleep=clock.sleep)['status'])
            saved=snapshots.snapshot(http);expiry=api.lease['expiresAt']+api.lease['graceSeconds']
            for now in (api.lease['startedAt']+6000,expiry-1):
                waiting,unchanged,calls=q.replay(api.cfg,req['source'],saved,root/str(now),now)
                self.assertEqual('WAITING',waiting['status']);self.assertEqual(saved,unchanged)
                self.assertTrue(all(v['method']=='GET' for v in calls))
            cleaned,after,calls=q.replay(api.cfg,req['source'],saved,root/'cleaned',expiry)
            self.assertEqual('PASS',cleaned['status']);self.assertFalse(after['resources'])
            _,model,raw,_=snapshots.restore(after)
            total,attempts=n.inspect_ledger(g.Store(api.cfg,raw,authority=n).get(n.LEDGER)[1])
            self.assertEqual(value['reservation']['previousCostMicrousd']+250_000_000,total)
            self.assertEqual('FAIL',attempts[n.validate_request(req)]['status'])
            self.assertEqual({v['id'] for v in saved['resources'].values()},
                {v['path'].rsplit('/',1)[1] for v in calls if v['method']=='DELETE' and v['path'].startswith('/compute/')})


class MetadataTest(unittest.TestCase):
    def test_pack_replays_original_paths_bytes_and_binding_with_few_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'metadata';rows=[('startup/node/'+str(i)+'.json',m.canonical(dict(index=i))) for i in range(900)]
            rows += [('preparation/receipt.json',b'original'),('sessions/node-1.json',b'session')]
            uploads=list(retention.pack(root,iter(rows),'a'*64))
            self.assertEqual(2,len(uploads));self.assertEqual(902,c.read(root/'receipt.json')['files'])
            parts.unpack(root/'parts',Path(tmp)/'replay','a'*64)
            for name,raw in rows:self.assertEqual(raw,(Path(tmp)/'replay'/name).read_bytes())
            with self.assertRaises(ValueError):parts.unpack(root/'parts',Path(tmp)/'foreign','b'*64)
            part=root/'parts/part-0000.bin';part.write_bytes(part.read_bytes()[:-1]+b'!')
            with self.assertRaisesRegex(ValueError,'hash'):parts.unpack(root/'parts',Path(tmp)/'changed','a'*64)

    def test_duplicate_unsafe_and_excessive_metadata_fail_before_any_upload(self):
        for rows in ([('../escape',b'a')],[('a',b'a'),('a',b'b')],[(parts.INDEX,b'a')],[('a','text')]):
            with tempfile.TemporaryDirectory() as tmp,self.assertRaises(ValueError):
                list(retention.pack(Path(tmp)/'metadata',rows,'a'*64))
        with tempfile.TemporaryDirectory() as tmp,patch.dict(parts.LIMITS,memberBytes=2),self.assertRaisesRegex(ValueError,'bound'):
            list(retention.pack(Path(tmp)/'metadata',[('large',b'abc')],'a'*64))


class LifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen=admission.workload.load();p=patch.object(admission.workload,'load',side_effect=lambda:deepcopy(frozen))
        p.start();cls.addClassCleanup(p.stop)
    @staticmethod
    def configure(f):
        old=f['value'];stage=old['resourcePlan'];req=stage['request']
        f['value']=admission.plan(old['configuration'],old['artifacts'],stage['guestAccess'],
            dict(old['prices'],pricedThroughSeconds=45000),None,sequence=req['sequence'],now=req['createdAt'],
            maximum_cost=250_000_000,member='canonical-1',order='any-order',soft_budget=True)
        f['approved']=admission.approval_template(f['value']);f['approved']['confirmed']=True
        f['env'].update(RUNNER_MEMBER='canonical-1',RUNNER_ORDER='any-order',RUNNER_EXPERIMENT_CONFIRMATION=f['approved']['planSha256'])
    def execute(self,fault=None,**options):
        from . import test_cloud_runner_owned as tests
        test=tests.LifecycleTest();test.configure_fixture=self.configure
        test.setUp();self.addCleanup(test.doCleanups)
        return test.execute(fault,**options),test
    def test_slow_preparation_and_retention_still_finish_cleanup_and_keep_charge(self):
        original=retention.pack
        def slow(*args):
            test.f['clock'].sleep(2501)
            yield from original(*args)
        from . import test_cloud_runner_owned as tests
        test=tests.LifecycleTest();test.configure_fixture=self.configure;test.setUp();self.addCleanup(test.doCleanups)
        with patch.object(retention,'pack',side_effect=slow):result,events=test.execute(preparation_seconds=5501)
        self.assertEqual('PASS',result['status'],result)
        self.assertEqual(['preparation','validation-retention'],result['budget']['warnings'])
        self.assertEqual(t.allocation('canonical-1')['cells'],result['evidence']['cells'])
        self.assertTrue(result['leaseReleased']);self.assertEqual('VERIFIED',result['retention'])
        self.assertTrue(any(key.endswith('metadata/parts.json') for key in test.f['http'].objects))
        from . import cloud_gcp as g, cloud_http as h
        reader=g.Store(test.f['cfg']['provider'],h.Api(transport=test.f['http'],tokens=lambda _:'fake',clock=test.f['clock'].seconds),authority=n)
        self.assertEqual(250_000_000,n.inspect_ledger(reader.get(n.LEDGER)[1])[0])
    def test_bad_evidence_is_failed_without_replaying_cells(self):
        (result,events),test=self.execute('evidence')
        self.assertEqual('FAIL',result['status']);self.assertTrue(result['leaseReleased'])
        self.assertEqual('PASS',result['cleanup']['status']);self.assertEqual(1,events.count('healthy'))
    def test_lost_packed_upload_keeps_lease_but_cleans_resources(self):
        (result,_),test=self.execute('upload')
        self.assertEqual('FAIL',result['status']);self.assertEqual('INCOMPLETE',result['retention'])
        self.assertFalse(result['leaseReleased']);self.assertEqual('PASS',result['cleanup']['status'])
        self.assertFalse(test.f['http'].resources)

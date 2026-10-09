"""Native full-preset binding qualification; no live network or paid execution."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from . import native_preset_timing as t, native_preset_review as review
from . import cloud_native_authority as n, cloud_authority as a, performance_model as m
from . import cloud_runner_admission as admission, cloud_runner_entry as entry, remote_budget
from . import cloud_runner_admission_qualification as fixture
from . import guest_native_session as session, guest_native_volume as volume, guest_delivery_receiver as receiver
from . import guest_native_owned as bridge, cloud_package as package, cloud_guest
from .test_cloud_runner_guest_setup import request as volume_fixture


def request(member='canonical-1', order='canonical-first', attempt='e'*32):
    return n.request('a'*40,'b'*64,'c'*64,'d'*32,attempt,member,now=100,order=order,
                     guest_access_sha256='f'*64,timing_profile=t.allocation(member)['profile'],timing_plan_sha256=t.PLAN_SHA256)


def descriptor(member):
    value=volume_fixture();req=request(member)
    req['attempt']=value['access']['attempt'];req['guestAccessSha256']=m.sha(m.canonical(value['access']))
    value.update(schema=volume.FULL_SCHEMA,nativeRequest=req,requestSha256=n.validate_request(req))
    value['binding'].update({k:req[k] for k in ('source','bundleSha256','workloadSha256','attempt')})
    volume.validate(value)
    desc=dict(schema='gse-v51-native-package-transfer-v1',binding=value['binding'],instanceId='123',diskId='456',
        guestAccessSha256=req['guestAccessSha256'],manifestSha256='a'*64,nativeVolume=dict(request=value))
    sample=receiver.clock_sample(session.identity(desc),'f'*32)
    limits=t.allocation(member)
    budget=dict(schema='gse-v51-helper-deadline-v1',sample=sample,
                expiresNanos=sample['sampledNanos']+limits['limitsSeconds']['preparation']*10**9)
    sess=dict(schema=session.SCHEMA,packageSha256=m.sha(m.canonical(desc)),preparation=budget,
        leaseExpiresNanos=sample['sampledNanos']+limits['leaseSeconds']*10**9,hosts=['10.0.0.1','10.0.0.2','10.0.0.3'],port=19000)
    session.validate(sess,desc)
    return desc,sess


class PresetIdentityTest(unittest.TestCase):
    def test_compiled_limits_match_hash_bound_review_and_frozen_cells(self):
        self.assertEqual(t.PLAN_SHA256,m.sha(review.PLAN.read_bytes()))
        for member in t.MEMBERS:
            self.assertEqual(review.allocation(member),t.allocation(member))
            req=request(member);self.assertEqual(n.validate_request(req),t.request_sha(req))
            limits=t.validate(req);lease=n.lease(req,101);n.validate_lease(lease)
            self.assertEqual((101+limits['leaseSeconds'],limits['operationGraceSeconds']), (lease['expiresAt'],lease['graceSeconds']))
            budget=remote_budget.Budget(profile=limits['profile'])
            self.assertEqual(limits['leaseSeconds']*10**9,budget.lease)
            self.assertEqual(set(limits['cells'])|{'preparation','validation-retention','cleanup','control'},set(budget.limits))
            self.assertLessEqual(limits['commandGuardSeconds']+60,limits['jobMinutes']*60)

    def test_mutated_request_domain_profile_plan_and_repetition_fail(self):
        for key,value in [('timingPlanSha256','a'*64),('timingProfile','owned-failure-drill-v1'),
            ('member','canonical-4'),('member',True),('order','arbitrary'),('paidCloud',False),('schema','gse-v51-native-request-v2')]:
            req=request();req[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):n.validate_request(req)
        with self.assertRaises(ValueError):a.validate_request(request())

    def test_both_complete_orders_keep_all_charges_and_one_identity(self):
        for order in a.ORDERS:
            ledger=n.empty_ledger()
            for i,member in enumerate(a.ORDERS[order]):
                req=request(member,order,attempt=f'{i+1:032x}')
                ledger=n.reserve(ledger,req,dict(previousCostMicrousd=i*1_000_000,maximumCostMicrousd=1_000_000))
                ledger=n.finish(ledger,req,dict(requestSha256=n.validate_request(req),status='PASS'))
            total,entries=n.inspect_ledger(ledger)
            self.assertEqual((5_000_000,5),(total,len(entries)))

    def test_failed_canonical_blocks_sequence_and_old_new_records_cannot_mix(self):
        req=request();ledger=n.reserve(n.empty_ledger(),req,dict(previousCostMicrousd=0,maximumCostMicrousd=1))
        ledger=n.finish(ledger,req,dict(requestSha256=n.validate_request(req),status='FAIL'))
        with self.assertRaisesRegex(ValueError,'failed canonical'):
            n.reserve(ledger,request(attempt='1'*32),dict(previousCostMicrousd=1,maximumCostMicrousd=1))
        old=request('experiment','experiment-first');old.pop('timingPlanSha256');old['schema']='gse-v51-native-request-v2'
        ledger=n.reserve(n.empty_ledger(),old,dict(previousCostMicrousd=0,maximumCostMicrousd=1))
        ledger=n.finish(ledger,old,dict(requestSha256=n.validate_request(old),status='PASS'))
        with self.assertRaisesRegex(ValueError,'sequence changed'):
            n.reserve(ledger,request('failure-drill','experiment-first','1'*32),dict(previousCostMicrousd=1,maximumCostMicrousd=1))

    def test_entry_selection_is_closed_and_controller_selects_complete_original_algorithms(self):
        for member in t.MEMBERS:
            self.assertEqual(member,entry.member_selection(dict(RUNNER_MEMBER=member,RUNNER_ORDER='canonical-first'))['member'])
            services,probe,cells,scope=bridge.selection(request(member))
            self.assertFalse(services.offline);self.assertIs(probe.authority,n)
            self.assertEqual(t.allocation(member)['cells'],list(cells))
        for env in ({'RUNNER_MEMBER':'canonical-1'},{'RUNNER_ORDER':'canonical-first'},
                    {'RUNNER_MEMBER':'canonical','RUNNER_ORDER':'canonical-first'}):
            with self.assertRaises(ValueError):entry.member_selection(env)


class GuestSelectionTest(unittest.TestCase):
    def test_complete_guest_configs_are_session_bound_with_rotated_local_control(self):
        for member in t.MEMBERS:
            desc,sess=descriptor(member);limits=t.allocation(member);selected=[]
            for cell in limits['cells']:
                modes=package.MODES if cell=='healthy' else (package.MODES[2],)
                for mode in modes:
                    workload=dict(cell=cell,preset='canonical',repetition=limits['repetition']) if limits['preset']=='canonical' and cell in package.WORKLOAD_CELLS else None
                    fault=None if cell in package.WORKLOAD_CELLS else cell
                    cfg=session.configuration(desc,sess,mode,fault,workload=workload)
                    cloud_guest.validate(cfg);session.check_config(cfg,desc,sess);selected.append(cfg)
                    if workload:self.assertEqual('node-'+str(limits['repetition']),package.control_node(cfg))
                    bad=deepcopy(cfg);bad['nativeRequest']['attempt']='0'*32
                    with self.assertRaises(ValueError):session.check_config(bad,desc,sess)
            self.assertEqual(len(selected),len(limits['cells'])+(0 if member=='failure-drill' else 2))

    def test_cross_preset_extra_cell_wrong_repetition_and_renewed_clock_fail(self):
        desc,sess=descriptor('experiment')
        with self.assertRaises(ValueError):session.configuration(desc,sess,package.MODES[2],'entry-chosen')
        desc,sess=descriptor('failure-drill')
        with self.assertRaises(ValueError):session.configuration(desc,sess,package.MODES[2])
        desc,sess=descriptor('canonical-2')
        with self.assertRaises(ValueError):session.configuration(desc,sess,package.MODES[0],workload=dict(cell='healthy',preset='canonical',repetition=1))
        with self.assertRaises(ValueError):session.validate(dict(sess,leaseExpiresNanos=sess['leaseExpiresNanos']+1),desc)
        for mutate in (lambda v:v['nativeVolume']['request'].update(requestSha256='0'*64),
                       lambda v:v['nativeVolume']['request']['nativeRequest'].update(timingPlanSha256='0'*64)):
            bad=deepcopy(desc);mutate(bad)
            with self.assertRaises(ValueError):t.package_request(bad)

    def test_native_probe_rotates_real_receiver_and_uses_same_scope(self):
        for rep in (1,2,3):
            desc,sess=descriptor('canonical-'+str(rep))
            group=bridge.Group.__new__(bridge.Group);group.mode=package.MODES[0];group.canonical_cell='healthy'
            group.canonical_repetition=rep;group.bootstrap=object();group.provider=SimpleNamespace(req=desc['nativeVolume']['request']['nativeRequest'])
            with tempfile.TemporaryDirectory() as temp:
                probe=bridge.SingleProbe(group,Path(temp)/'probe')
                self.assertEqual((rep,),probe.nodes);self.assertEqual('node-'+str(rep),probe.control_node)
                self.assertEqual('canonical',probe.preset)


class AdmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen=admission.workload.load();p=patch.object(admission.workload,'load',side_effect=lambda:deepcopy(frozen));p.start();cls.addClassCleanup(p.stop)
        tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(tmp.cleanup);cls.f=fixture.fixture(Path(tmp.name)/'inputs')
    def plan(self,member='canonical-1'):
        old=self.f['value'];stage=old['resourcePlan'];req=stage['request'];quote=deepcopy(old['prices'])
        quote['pricedThroughSeconds']=t.allocation(member)['priceCoverageSeconds']
        return admission.plan(old['configuration'],old['artifacts'],stage['guestAccess'],quote,None,
            sequence=req['sequence'],now=req['createdAt'],maximum_cost=20_000_000,member=member,
            order='canonical-first' if member=='canonical-1' else 'experiment-first')
    def test_plan_roundtrip_quote_coverage_and_exact_approval(self):
        for member in ('experiment','canonical-1'):
            value=self.plan(member);req=value['resourcePlan']['request'];now=req['createdAt']
            digest=admission.validate_plan(value,now);approval=admission.approval_template(value);approval['confirmed']=True
            self.assertEqual(digest,admission.approval(value,approval,digest,now))
            bad=deepcopy(value);bad['timing']['limitsSeconds']['preparation']+=1
            with self.assertRaises(ValueError):admission.validate_plan(bad,now)
            bad=deepcopy(value['prices']);bad['pricedThroughSeconds']-=1
            with self.assertRaisesRegex(ValueError,'lifetime coverage'):admission.prices(bad,now,req)
    def test_prepared_selection_change_fails_before_live_reads(self):
        value=self.plan();approval=admission.approval_template(value);approval['confirmed']=True
        env=dict(self.f['env'],RUNNER_MEMBER='experiment',RUNNER_ORDER='canonical-first',RUNNER_EXPERIMENT_CONFIRMATION=approval['planSha256'])
        get=Mock(side_effect=AssertionError('must not read live state'))
        with patch.object(admission.precheck,'identity',return_value={}),self.assertRaisesRegex(ValueError,'selected member or order'):
            admission.context(self.f['cfg'],env,value['artifacts']['source'],'unused','unused','unused',value,approval,get=get,now=value['resourcePlan']['request']['createdAt'])
        get.assert_not_called()

    def test_summary_keeps_all_selected_cells_when_session_recovery_is_present(self):
        from . import remote_command as c
        value=self.plan()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'prepared').mkdir();(root/'execution/preparation').mkdir(parents=True)
            c.write_once(root/'receipt.json',dict(mode='prepare',status='PREPARED'))
            c.write_once(root/'prepared/plan.json',value)
            c.write_once(root/'execution/preparation/session-recovery.json',dict(sessions=[dict(
                node='node-3',status='PASS',begins=1,events=[],transientFailures=0,uncertain=0,startNanos=1,endNanos=2,code=None)]))
            rendered=entry.summary(root)
            for cell in t.allocation('canonical-1')['cells']:self.assertIn('| '+cell+' | NOT_ESTABLISHED |',rendered)
            self.assertIn('| Measured calls | 1080 |',rendered)
            self.assertIn('| Member | canonical-1 |',rendered)


class CleanupCompatibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen=admission.workload.load();p=patch.object(admission.workload,'load',side_effect=lambda:deepcopy(frozen));p.start();cls.addClassCleanup(p.stop)
    def test_each_new_member_preserves_active_grace_exact_cleanup_and_charges(self):
        from . import cloud_experiment_resource_qualification as q, cloud_gcp as g
        from . import cloud_cleanup_qualification as snapshots
        for member in t.MEMBERS:
            with self.subTest(member=member),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);old,clock,http,reader,_=q.fixture();guest=old['guestAccess']
                req=n.request(old['request']['source'],old['request']['bundleSha256'],g.config(old['configuration']),
                    old['request']['sequence'],guest['attempt'],member,now=clock.wall(),order='experiment-first',
                    guest_access_sha256=m.sha(m.canonical(guest)),timing_profile=t.allocation(member)['profile'],timing_plan_sha256=t.PLAN_SHA256)
                store=g.Store(old['configuration'],reader,authority=n);generation,ledger=store.get(n.LEDGER)
                for i,prior in enumerate(a.ORDERS['experiment-first'][:a.ORDERS['experiment-first'].index(member)]):
                    previous=dict(req,member=prior,attempt=f'{i+1:032x}',timingProfile=t.allocation(prior)['profile'])
                    cost,_=n.inspect_ledger(ledger)
                    ledger=n.reserve(ledger,previous,dict(previousCostMicrousd=cost,maximumCostMicrousd=1))
                    ledger=n.finish(ledger,previous,dict(requestSha256=n.validate_request(previous),status='PASS'))
                generation=store.put(n.LEDGER,ledger,generation)
                value=q.r.make(old['configuration'],req,guest,[generation,ledger],old['inputs'],now=clock.wall(),maximum_cost=q.COST)
                api=q.r.OfflineApi(value,clock.wall(),transport=http,tokens=lambda _:'synthetic',clock=clock.seconds)
                prepared=q.r.prepare(value,api,root/'prepare',now=clock.wall(),sleep=clock.sleep)
                self.assertEqual('RESOURCES_PREPARED',prepared['status']);self.assertEqual(13,http.inserts)
                self.assertEqual({str(t.allocation(member)['leaseSeconds'])}, {v['scheduling']['maxRunDuration']['seconds'] for v in http.resources.values() if 'machineType' in v})
                saved=snapshots.snapshot(http);expiry=api.lease['expiresAt']+api.lease['graceSeconds']
                waiting,unchanged,calls=q.replay(api.cfg,req['source'],saved,root/'waiting',expiry-1)
                self.assertEqual('WAITING',waiting['status']);self.assertEqual(saved,unchanged)
                self.assertTrue(all(v['method']=='GET' for v in calls))
                cleaned,after,calls=q.replay(api.cfg,req['source'],saved,root/'cleaned',expiry)
                self.assertEqual('PASS',cleaned['status']);self.assertFalse(after['resources'])
                _,model,raw,_=snapshots.restore(after)
                total,attempts=n.inspect_ledger(g.Store(api.cfg,raw,authority=n).get(n.LEDGER)[1])
                self.assertEqual(value['reservation']['previousCostMicrousd']+q.COST,total)
                self.assertEqual('FAIL',attempts[n.validate_request(req)]['status'])
                ids={v['id'] for v in saved['resources'].values()}
                self.assertEqual(ids,{v['path'].rsplit('/',1)[1] for v in calls if v['method']=='DELETE' and v['path'].startswith('/compute/')})


class TrustedReceiverTest(unittest.TestCase):
    def test_native_receiver_bundle_imports_and_checks_new_session_without_repo_imports(self):
        import base64,subprocess,sys
        from .cloud_runner_guest_setup import trusted_source
        for member in ('failure-drill','canonical-2'):
            desc,sess=descriptor(member)
            cfg=session.configuration(desc,sess,package.MODES[2],'entry-chosen')
            source=trusted_source('session').rsplit("sys.modules['trusted.guest_native_session'].main()",1)[0]
            encoded=base64.b64encode(m.canonical([desc,sess,cfg])).decode()
            source+="value,session,config=json.loads(base64.b64decode("+repr(encoded)+"))\n"
            source+="sys.modules['trusted.guest_native_volume'].validate(value['nativeVolume']['request'])\n"
            source+="sys.modules['trusted.guest_native_session'].check_config(config,value,session)\nprint('PASS')\n"
            with tempfile.TemporaryDirectory() as temp:
                result=subprocess.run([sys.executable,'-I','-c',source],cwd=temp,capture_output=True,timeout=10)
            self.assertEqual(0,result.returncode,result.stderr.decode());self.assertEqual(b'PASS\n',result.stdout)

    def test_full_fault_handlers_require_native_request_and_use_bounded_watchdog(self):
        from .test_guest_owned_faults import HandlerTest
        from . import guest_fault_network as network, guest_fault_recovery as recovery, native_experiment_timing as limits
        for kind,case,action,module in [('network','asymmetric-requests','isolate',network),('recovery','minority-capacity','prepare-direction',recovery)]:
            fixture=HandlerTest();fixture.setUp()
            try:
                desc,sess=descriptor('failure-drill');cfg=session.configuration(desc,sess,package.MODES[2],case)
                fixture.s.config=cfg;fixture.handler.case=case
                if action=='prepare-direction':fixture.handler.generation=0;fixture.s.jvm=None
                controls=module.Controls(fixture.handler)
                with patch.object(module.threading,'Timer') as timer:
                    controls.handle(dict(action=action,**({'node':'node-1'} if action=='isolate' else {})))
                    self.assertEqual(limits.CONTROLS['isolation'],timer.call_args.args[0])
                fixture.s.config=dict(cfg);fixture.s.config.pop('nativeRequest')
                with self.assertRaises(ValueError):controls.handle(dict(action=action))
            finally:fixture.doCleanups()


class FullControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen=admission.workload.load();p=patch.object(admission.workload,'load',side_effect=lambda:deepcopy(frozen));p.start();cls.addClassCleanup(p.stop)
    @staticmethod
    def configure(f):
        old=f['value'];stage=old['resourcePlan'];req=stage['request']
        prices=dict(old['prices'],pricedThroughSeconds=t.allocation('canonical-1')['priceCoverageSeconds'])
        f['value']=admission.plan(old['configuration'],old['artifacts'],stage['guestAccess'],prices,None,
            sequence=req['sequence'],now=req['createdAt'],maximum_cost=20_000_000,member='canonical-1',order='canonical-first')
        f['approved']=admission.approval_template(f['value']);f['approved']['confirmed']=True
        f['env'].update(RUNNER_MEMBER='canonical-1',RUNNER_ORDER='canonical-first',RUNNER_EXPERIMENT_CONFIRMATION=f['approved']['planSha256'])
    def execute(self,fault=None):
        from . import test_cloud_runner_owned as tests
        test=tests.LifecycleTest();test.configure_fixture=self.configure
        test.setUp();self.addCleanup(test.doCleanups)
        return test.execute(fault),test
    def test_fifteen_cell_native_controller_uses_one_original_lease_then_retains_and_cleans(self):
        (result,events),test=self.execute()
        self.assertEqual('PASS',result['status'],result)
        self.assertEqual(t.allocation('canonical-1')['cells'],result['evidence']['cells'])
        self.assertEqual('owned-complete-canonical',result['qualificationScope'])
        self.assertEqual(13,test.f['http'].inserts);self.assertEqual({},test.f['http'].resources)
        self.assertTrue(result['leaseReleased']);self.assertFalse(result['fullRemoteQualification'])
        self.assertEqual('VERIFIED',result['retention'])
    def test_failed_original_cell_is_not_replayed_and_retains_failure_before_exact_cleanup(self):
        (result,events),test=self.execute('entry-chosen')
        self.assertEqual('FAIL',result['status']);self.assertEqual(1,events.count('entry-chosen'))
        self.assertNotIn('proof-quorum',events);self.assertEqual('PASS',result['cleanup']['status'])
        self.assertEqual('VERIFIED',result['retention']);self.assertTrue(result['leaseReleased'])
        self.assertEqual({},test.f['http'].resources)


class IndependentAdmissionTest(unittest.TestCase):
    """Synthetic shape fixtures only: no claim of native physical qualification."""
    def setUp(self):
        from .test_guest_owned_canonical import AggregateAdmissionTest
        from . import guest_owned_canonical as canonical, remote_command as c
        AggregateAdmissionTest.setUp(self)
        self.req=request('canonical-2');sha=n.validate_request(self.req)
        plan=c.read(self.root/'plan.json');plan['request']=self.req;plan['services']['requestSha256']=sha
        (self.root/'plan.json').write_bytes(m.canonical(plan))
        for folder in self.root.iterdir():
            if not folder.is_dir():continue
            local=c.read(folder/'plan.json');local['request']=self.req
            for cfg in local['configs']:
                import uuid
                cfg.update(execution=cloud_guest.NATIVE_EXECUTION,nativeRequest=deepcopy(self.req))
                label=package.bootstrap_directory_name(cfg) if 'workload' in cfg else cfg['faultCell']
                cfg['binding']=c.binding(self.req['source'],self.req['bundleSha256'],self.req['attempt'],cfg['binding']['node'])
                cfg['groupId']=str(uuid.uuid5(uuid.NAMESPACE_URL,sha+':'+label))
            (folder/'plan.json').write_bytes(m.canonical(local))
    def test_explicit_native_authority_requires_complete_domain_and_selection(self):
        from . import guest_canonical_evidence as evidence, guest_owned_canonical as canonical, remote_command as c
        self.assertEqual(2,evidence.admission(self.root,authority=n)['repetition'])
        with self.assertRaises(ValueError):evidence.admission(self.root)
        path=self.root/canonical.key(*canonical.TAPES[0])/'plan.json';original=path.read_bytes()
        for mutate in (lambda cfg:cfg.pop('nativeRequest'),lambda cfg:cfg.update(execution=cloud_guest.EXECUTION),
                       lambda cfg:cfg['nativeRequest'].update(member='canonical-3'),lambda cfg:cfg['workload'].update(repetition=3)):
            value=c.read(path);mutate(value['configs'][0]);path.write_bytes(m.canonical(value))
            with self.assertRaises(ValueError):evidence.admission(self.root,authority=n)
            path.write_bytes(original)
        path=self.root/'plan.json';plan=c.read(path);plan['services']['faults'].pop();path.write_bytes(m.canonical(plan))
        with self.assertRaisesRegex(ValueError,'complete service set'):evidence.admission(self.root,authority=n)
    def test_static_guest_config_cannot_omit_selected_canonical_workload(self):
        desc,sess=descriptor('canonical-2')
        cfg=session.configuration(desc,sess,package.MODES[2],workload=dict(cell='healthy',preset='canonical',repetition=2))
        cfg.pop('workload')
        with self.assertRaisesRegex(ValueError,'preset selection'):cloud_guest.validate(cfg)
    def test_native_replay_child_is_explicit_and_deadline_is_not_renewed(self):
        from . import guest_canonical_evidence as canonical, guest_fault_evidence as drill, remote_command as c
        for label,module,options in [('canonical',canonical,dict(authority=n)),('drill',drill,{})]:
            dest=self.root/label
            def child(command,**kwargs):
                if label=='canonical':self.assertIn('--native',command)
                self.assertEqual(9,kwargs['timeout'])
                c.write_once(dest.with_name(dest.name+'-result.json'),dict(status='PASS'))
                return SimpleNamespace(returncode=0)
            with patch('subprocess.run',side_effect=child) as spawn:
                self.assertEqual('PASS',module.bounded_replay(self.root,dest,10,clock=lambda:1,**options)['status'])
                with self.assertRaisesRegex(ValueError,'consumed'):module.bounded_replay(self.root,dest,20,clock=lambda:1,**options)
                spawn.assert_called_once()


class NativeNetworkControlTest(unittest.TestCase):
    def test_delayed_observations_finish_under_fault_before_single_controller_heal(self):
        from . import guest_owned_network as network, guest_owned_faults as faults, cloud_fake
        clock=cloud_fake.Clock();members=[(i,Mock(),{}) for i in (1,2,3)]
        with tempfile.TemporaryDirectory() as temp:
            cell=network.Cell(SimpleNamespace(clients=members,provider=SimpleNamespace(req=request('failure-drill'))),
                              Path(temp)/'cell','asymmetric-requests',clock=clock.seconds,sleep=clock.sleep)
            cell.end=clock.seconds()+600;cell.running={};cell.status=Mock(return_value={'provenIndex':1})
            cell.succeeded=Mock(return_value={'result':{}});seen=[]
            def progress(*args,**kwargs):
                self.assertFalse(cell.network_healed);clock.sleep(25);return 'node-2'
            cell.progress=Mock(side_effect=progress)
            def execute(cell,member,name,payload,end):
                seen.append((member[0],clock.seconds(),payload['action']));return {'state':'SUCCEEDED'}
            with patch.object(network.threading,'Timer') as timer,patch.object(faults.Cell,'execute',execute):
                timer.return_value.is_alive.return_value=False
                timer.return_value.join.side_effect=lambda *args,**kwargs: timer.call_args.args[1]() if not seen else None
                network.scenario(cell,'node-1',cell.end)
            self.assertEqual([(i,26,'heal') for i in (1,2,3)],sorted(seen))
            self.assertTrue(cell.network_healed);self.assertFalse(cell.reserved)


class NativeEntryTest(unittest.TestCase):
    def test_prepare_then_fresh_dispatch_passes_exact_v3_member_into_owner_once(self):
        from contextlib import ExitStack
        import shutil
        from .test_cloud_runner_entry import EntryTest
        from . import remote_command as c
        test=EntryTest();test.setUp();self.addCleanup(test.doCleanups)
        quote=m.strict_json(test.env['RUNNER_EXPERIMENT_QUOTE'])
        quote['prices']['pricedThroughSeconds']=t.allocation('canonical-1')['priceCoverageSeconds']
        quote['maximumCostMicrousd']=20_000_000
        test.env.update(RUNNER_MEMBER='canonical-1',RUNNER_ORDER='canonical-first',RUNNER_EXPERIMENT_QUOTE=m.canonical(quote).decode())
        with ExitStack() as stack:
            test.dependencies(stack)
            prepared=test.call('prepare')
        self.assertEqual('PREPARED',prepared['status'],prepared)
        test.f['value']=c.read(test.root/'entry/prepared/plan.json')
        self.assertEqual(t.REQUEST_SCHEMA,test.f['value']['resourcePlan']['request']['schema'])
        test.f['approved']=admission.approval_template(test.f['value']);test.f['approved']['confirmed']=True
        archive=test.setup_run();test.env.update(RUNNER_MEMBER='canonical-1',RUNNER_ORDER='canonical-first')
        collect=entry.prepared.collect
        with ExitStack() as stack:
            test.dependencies(stack)
            stack.enter_context(patch.object(entry.prepared,'collect',side_effect=lambda *args,**kwargs:
                collect(*args,**kwargs,get=entry.ci.github,fetch=lambda _,path:shutil.copyfile(archive,path))))
            owner=stack.enter_context(patch.object(entry.owned,'run_native',return_value=dict(status='PASS',paidCloud=True,engineWorkloadExecuted=True,fullRemoteQualification=False)))
            result=test.call('run','execution-entry')
        self.assertEqual('PASS',result['status'],result);owner.assert_called_once()
        self.assertEqual(test.f['value'],owner.call_args.args[6])
        self.assertEqual('canonical-1',owner.call_args.args[1]['RUNNER_MEMBER'])
        self.assertFalse(Path(owner.call_args.args[-2]).exists())

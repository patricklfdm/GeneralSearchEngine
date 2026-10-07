"""Owner policy/lifecycle tests; every provider operation uses synthetic HTTP."""
from copy import deepcopy
from contextlib import chdir
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode
from . import cloud_runner_owned as o, cloud_runner_resource_qualification as q, cloud_http as h
from . import cloud_runner as runner, cloud_native_authority as n, cloud_gcp as g, performance_model as m
from . import cloud_runner_failure as failure


class OwnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen=failure.workload.load();p=patch.object(failure.workload,'load',side_effect=lambda:deepcopy(frozen))
        p.start();cls.addClassCleanup(p.stop)
    def prepare_source(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.f=q.fixture(self.root/'inputs',self.root/'private');original=q.r._run
        def run(*args,**kwargs):
            def capture(api,*args):self.source=api;return []
            return original(*args,**kwargs,guest_stage=capture)
        with patch.object(q.r,'_run',side_effect=run):self.preparation=q.prepare(self.f,self.root/'preparation')
        self.assertEqual('PARTIAL',self.preparation['status'])
        # Exercise the real native policy after synthetic admission, with a
        # network-shaped transport that only delegates to the in-memory server.
        fake=self.f['http']
        self.source.transport=SimpleNamespace(offline=False,send=fake.send)
    def setUp(self):
        self.prepare_source()
        self.api=o._Api(self.source);self.store=self.api.admit()
    def stage(self,name,seconds=30):self.api.stage(name,self.api.clock()+seconds)
    def cleanup(self):
        self.stage('cleanup');lease=deepcopy(self.api.lease);generation=self.api.lease_generation
        def persist():
            nonlocal generation
            generation=self.store.put(n.LEASE,lease,generation)
        result=runner.cleanup(self.api.provider,lease,persist,authority=n,redact=True)
        return lease,generation,result
    def complete(self,*,status='PASS',cleanup_result=None):
        value=dict(schema=n.COMPLETION_SCHEMA,execution=n.EXECUTION,paidCloud=True,requestSha256=self.api.sha,
            status=status,engineWorkloadExecuted=True,fullRemoteQualification=False,cleanup=cleanup_result)
        self.api.expected_completion=value
        runner.finalize(self.store,self.api.lease,value,authority=n)
        return value
    def test_runtime_cannot_create_delete_refund_or_change_lease(self):
        self.stage('healthy')
        spec=self.api.lease['resources'][0]['spec']
        for action in (lambda:self.api.provider.delete(spec,self.api.lease['resources'][0]['id']),
                       lambda:self.store.put(n.LEASE,self.api.lease,self.api.lease_generation),
                       lambda:self.store.put(n.LEDGER,n.empty_ledger(),self.api.ledger_generation),
                       lambda:self.api.provider.create(spec,int(self.api.deadline*1e9))):
            with self.assertRaises(ValueError):action()
        self.assertEqual(13,self.f['http'].inserts);self.assertEqual(13,len(self.f['http'].resources))
    def test_runtime_reads_exact_guest_ids_without_granting_cleanup_resolution(self):
        self.stage('healthy')
        for node in (1,2,3):
            observed=self.api.provider.guest_identity(self.api.lease,node,deadline=self.api.deadline)
            self.assertEqual(self.preparation['guests'][node-1]['facts'],observed['facts'])
            self.assertEqual(self.source.value['guestAccess']['publicKey'],observed['publicKey'])
        self.assertEqual({},self.api.resolved)
        # Reading an owned ID must not substitute for insert reconciliation.
        self.stage('cleanup')
        row=next(v for v in self.api.lease['resources'] if v['spec']['kind']=='instance')
        with self.assertRaises(ValueError):self.api.provider.delete(row['spec'],row['id'])
        self.api.provider.operation(row['spec']);self.api.provider.delete(row['spec'],row['id'])
    def test_runtime_read_scope_rejects_foreign_ids_names_queries_and_mutations_before_http(self):
        row=next(v for v in self.api.lease['resources'] if v['spec']['kind']=='instance')
        numeric=self.api.provider.url(row['spec'],row['id']);named=self.api.provider.url(row['spec'])
        with self.assertRaises(ValueError):self.api.check('GET',numeric,None)  # admission, before cells
        self.stage('healthy');before=len(self.f['http'].requests)
        for method,url,body in [('GET',url,None) for url in (
            named,numeric+'?alt=json',numeric+'#fragment',numeric.replace('offline-project','foreign-project'),
            numeric.rsplit('/',1)[0]+'/99999999',numeric.rsplit('/',1)[0],
            named+'/getGuestAttributes?queryPath=hostkeys%2F&unused=',
            named+'/getGuestAttributes?queryPath=hostkeys%2F&queryPath=hostkeys%2F',
            named+'/getGuestAttributes?queryPath=other%2F')] + [
            ('GET',numeric,{}),('POST',numeric,{}),('DELETE',numeric,None)]:
            with self.subTest(method=method,url=url),self.assertRaises(ValueError):
                self.api.call(method,url,body,deadline=self.api.deadline)
        self.assertEqual(before,len(self.f['http'].requests))
        for field,value in (('attempted',False),('id',None)):
            old=row[field];row[field]=value
            try:
                with self.assertRaises(ValueError):self.api.check('GET',numeric,None)
            finally:row[field]=old
        self.assertEqual(before,len(self.f['http'].requests))
    def test_runtime_numeric_response_must_match_retained_id_and_owned_shape(self):
        self.stage('healthy');row=next(v for v in self.api.lease['resources'] if v['spec']['kind']=='disk')
        original=self.source.transport.send
        for key,value in (('id','99999999'),('labels',{}),('description','foreign')):
            def changed(*args,**kwargs):
                status,raw=original(*args,**kwargs);body=m.strict_json(raw);body[key]=value
                return status,m.canonical(body)
            with self.subTest(key=key),patch.object(self.source.transport,'send',side_effect=changed),self.assertRaises(ValueError):
                self.api.provider.describe(row['spec'],identity=row['id'],deadline=self.api.deadline)
        self.assertEqual({},self.api.resolved)
    def test_success_retains_exact_bytes_finishes_charge_and_deletes_only_exact_ids(self):
        self.stage('validation-retention');digest=self.api.retain(self.store,'parts/part-0000.bin',b'physical evidence')
        self.assertEqual(m.sha(b'physical evidence'),digest);self.api.seal()
        lease,generation,clean=self.cleanup();self.assertEqual('PASS',clean['status'])
        self.stage('completion');value=self.complete(cleanup_result=clean);self.store.delete(n.LEASE,generation)
        self.assertIsNone(self.store.get(n.LEASE));self.assertEqual({},self.f['http'].resources)
        total,rows=n.inspect_ledger(self.store.get(n.LEDGER)[1]);self.assertEqual(q.q.COST,total)
        self.assertEqual('PASS',rows[self.api.sha]['status']);self.assertFalse(value['fullRemoteQualification'])
        deletes=[v for v in self.f['http'].requests if v['method']=='DELETE' and v['path'].startswith('/compute/')]
        self.assertEqual({r['id'] for r in lease['resources']},{v['path'].rsplit('/',1)[-1] for v in deletes})
    def test_lost_retention_response_still_allows_cleanup_but_not_release(self):
        self.stage('validation-retention');send=self.api.transport.send
        def lost(method,url,*args):
            result=send(method,url,*args)
            if method=='POST' and 'owned-experiment' in url:raise ConnectionError('lost upload response')
            return result
        self.api.transport.send=lost
        with self.assertRaises(ConnectionError):self.api.retain(self.store,'evidence.json',b'partial')
        with self.assertRaises(ValueError):self.api.seal()
        _,generation,clean=self.cleanup();self.assertEqual('PASS',clean['status']);self.stage('completion')
        with self.assertRaises(ValueError):self.complete(status='FAIL',cleanup_result=clean)
        with self.assertRaises(ValueError):self.store.delete(n.LEASE,generation)
        self.assertIsNotNone(self.store.get(n.LEASE));self.assertEqual(13,self.f['http'].inserts)
    def test_mutation_lost_reply_cannot_be_retried_under_new_credentials(self):
        self.stage('validation-retention');send=self.api.transport.send
        def denied(method,url,*args):
            if method=='POST':return 401,b''
            return send(method,url,*args)
        self.api.transport.send=denied
        with self.assertRaises(h.ApiError):self.api.retain(self.store,'evidence.json',b'x')
        key=next(iter(self.api.retained))
        with self.assertRaisesRegex(ValueError,'already submitted'):self.store.put(key,b'x',0)
        self.assertEqual(1,len(self.api.mutations));self.assertFalse(self.api.retention_sealed)
    def test_failed_workload_keeps_charge_when_cleanup_and_retention_succeed(self):
        self.stage('validation-retention');self.api.retain(self.store,'failure.json',b'original failure');self.api.seal()
        _,generation,clean=self.cleanup();self.stage('completion');self.complete(status='FAIL',cleanup_result=clean)
        self.store.delete(n.LEASE,generation)
        total,rows=n.inspect_ledger(self.store.get(n.LEDGER)[1]);self.assertEqual(q.q.COST,total)
        self.assertEqual('FAIL',rows[self.api.sha]['status'])
    def test_changed_or_unread_evidence_cannot_be_completed(self):
        self.stage('validation-retention');self.api.retain(self.store,'data.bin',b'original')
        key=next(iter(self.api.retained))
        with self.assertRaises(ValueError):self.api.observe(('object',key,'media:1'),b'changed')
        self.api.verified.clear()
        with self.assertRaises(ValueError):self.api.seal()
    def test_stage_replay_out_of_order_or_extended_ceiling_rejected(self):
        with self.assertRaises(ValueError):self.stage('maintenance')
        with self.assertRaises(ValueError):self.stage('healthy',901)
        self.stage('healthy')
        with self.assertRaises(ValueError):self.stage('healthy')
        self.stage('cleanup')
        with self.assertRaises(ValueError):self.stage('validation-retention')
    def test_original_owner_deadline_never_renews_after_preparation(self):
        end=self.source.owner_deadline;self.f['clock'].sleep(1801);self.stage('healthy')
        self.assertEqual(end,self.source.owner_deadline)
        self.f['clock'].sleep(end-self.api.clock())
        with self.assertRaises(ValueError):self.stage('cleanup')
        with self.assertRaises(ValueError):self.store.get(n.LEASE)
    def test_consumed_source_cannot_resume_creation_or_another_recovery(self):
        with self.assertRaises(ValueError):o._Api(self.source)
        self.source.failed=True
        with self.assertRaises(ValueError):failure._Api(self.source)
        with self.assertRaises(ValueError):self.source.store.get(n.LEASE)
    def test_evidence_paths_and_namespace_are_closed(self):
        self.stage('validation-retention')
        for name in ('../credentials','a/../secret','/root/key','a//b','a\\b'):
            with self.assertRaises(ValueError):self.api.retain(self.store,name,b'x')
        with self.assertRaises(ValueError):self.store.put(n.PREFIX+'foreign.json',{},0)
    def test_manual_still_waits_for_expiry_of_active_owner(self):
        saved=q.q.cleanup.snapshot(self.f['http']);lease=self.api.lease
        result,after,_=q.resources.replay(self.f['cfg']['provider'],q.q.pq.SOURCE,saved,self.root/'manual',lease['startedAt'])
        self.assertEqual('WAITING',result['status']);self.assertEqual(saved,after)


class EntryBoundaryTest(unittest.TestCase):
    def test_linked_controller_parent_is_rejected_before_native_admission(self):
        with tempfile.TemporaryDirectory() as directory,\
             patch.object(o.resources,'_prepare_native',return_value=dict(status='FAIL',paidCloud=False)) as prepare:
            root=Path(directory);(root/'real').mkdir();(root/'linked').symlink_to(root/'real',target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'directory symlink'):
                o.run_native(*([None]*6),{'artifacts':{}},None,None,None,root/'linked/execution')
            prepare.assert_not_called()
    def test_relative_entry_binds_absolute_output_before_admission_and_cannot_reuse_it(self):
        with tempfile.TemporaryDirectory() as directory,chdir(directory),\
             patch.object(o.resources,'_prepare_native',return_value=dict(status='FAIL',paidCloud=False)) as prepare:
            output=Path('nested/execution')
            result=o.run_native(*([None]*6),{'artifacts':{}},None,None,None,output)
            self.assertEqual(Path(directory)/output/'preparation',prepare.call_args.args[-1])
            self.assertFalse(result['paidCloud'])
            with self.assertRaises(FileExistsError):o.run_native(*([None]*6),{'artifacts':{}},None,None,None,output)
            prepare.assert_called_once()
    def test_public_entry_fixes_fresh_admission_and_no_override_parameters(self):
        import inspect
        self.assertEqual(['cfg','env','source','checkout','preflight','precheck_root','value','approved','artifacts','key','output'],
                         list(inspect.signature(o.run_native).parameters))
        with tempfile.TemporaryDirectory() as directory,patch.object(o.resources,'_prepare_native',return_value=dict(status='FAIL',paidCloud=False)) as prepare:
            result=o.run_native(*([None]*6),{'artifacts':{}},None,None,None,Path(directory)/'out')
        self.assertEqual('FAIL',result['status']);self.assertEqual(1,prepare.call_count)
        self.assertFalse(result['engineWorkloadExecuted']);self.assertFalse(result['leaseReleased'])
    def test_offline_and_copied_authority_cannot_construct_owner(self):
        for value in ({},SimpleNamespace(offline=True)):
            with self.assertRaises(ValueError):o._Api(value)


class BridgeTest(unittest.TestCase):
    setUpClass=classmethod(OwnerTest.setUpClass.__func__)
    prepare_source=OwnerTest.prepare_source
    def setUp(self):
        from . import guest_delivery_receiver as r, guest_native_volume as volume, guest_package_delivery as delivery
        from . import guest_startup_fake as block, guest_volume
        self.prepare_source();self.recheck=Mock()
        archive,manifest=o.setup._archive(self.f['originals'],self.f['value']['artifacts'],self.root/'inputs')
        self.archive=archive;self.prepared=[]
        for number,record in enumerate(self.preparation['guests'],1):
            facts=record['facts'];binding=o.c.binding(self.source.req['source'],self.source.req['bundleSha256'],self.source.req['attempt'],'node-'+str(number))
            access=self.source.value['guestAccess']
            value=dict(schema=volume.SCHEMA,binding=binding,provider=facts['provider'],bootDiskId=facts['bootDiskId'],
                       access=access,requestSha256=n.validate_request(self.source.req))
            desc=delivery.describe(archive,manifest,binding,facts['provider'],m.sha(m.canonical(access)))
            desc.update(schema='gse-v51-native-package-transfer-v1',nativeVolume=dict(request=value,startupSha256='a'*64,
                volume=dict(device='/dev/sdb',majorMinor='8:16',uuid='12345678-1234-1234-1234-123456789abc',mount='/mnt/gse-v51',uid=1001,gid=1001)))
            target=dict(instanceId=desc['instanceId'],instance=facts['instance'],project=facts['project'],zone=facts['zone'],
                user=access['user'],key=str(self.f['key']),knownHosts=str(self.root/'preparation/iap'/f'node-{number}.known_hosts'))
            endpoint=o.setup._PackageEndpoint(self.source,target,desc,self.recheck)
            endpoint.deadline=self.source.deadline
            sample=r.clock_sample(o.native.session.identity(desc),'e'*32)
            endpoint.budget=dict(schema='gse-v51-helper-deadline-v1',sample=sample,expiresNanos=sample['sampledNanos']+500*10**9)
            self.prepared.append(dict(endpoint=endpoint,recheck=self.recheck,facts=facts,startup={},installed=dict(state='SUCCEEDED')))
        self.services=o.native.Services(self.source.provider(),archive,self.prepared)
    def test_all_six_groups_use_native_factories_and_original_package_pool(self):
        services=self.services;services.root=self.root/'services';services.root.mkdir();services.source=services.shared_source()
        self.assertIsInstance(services.source.remote,o.native.RemoteSource)
        groups=[services.group(mode=mode,bootstrap=services.seed()) for mode in o.native.healthy.package.MODES]
        groups += [services.group(fault_cell=case) for case in o.native.experiment.FAULTS]
        self.assertEqual(6,len(groups));self.assertTrue(all(type(v) is o.native.Group and not v.offline for v in groups))
        self.assertTrue(all(v.pool is services.pool for v in groups))
        for ep in services.pool.endpoints.values():
            self.assertEqual(dict(state='SUCCEEDED'),services.pool.deliver(ep,self.archive,self.source.deadline))
            with self.assertRaises(ValueError):services.pool.deliver(ep,self.archive,self.source.deadline+1)
    def test_lost_begin_queries_original_session_without_new_claim(self):
        ep=self.services.pool.endpoints['node-1'];actions=[]
        expected=dict(state='SUCCEEDED',sessionSha256=m.sha(m.canonical(ep.session)))
        def exchange(api,target,remote,data,deadline,**options):
            actions.append(remote[4]);self.assertIs(api,self.source)
            self.assertLessEqual(deadline,self.source.deadline)
            self.assertLessEqual(deadline,self.source.clock()+30)
            if remote[4]=='begin':raise o.native.recovery.transport.ProcessError('SSH_DISCONNECTED')
            return m.canonical(expected)
        with patch.object(o.native.iap,'_network_exchange',side_effect=exchange):
            self.assertEqual(expected,ep.begin())
            with self.assertRaises(ValueError):ep.begin()
        self.assertEqual(['begin','query'],actions)
    def test_client_calls_scoped_network_exchange_and_forwards_original_lease_session(self):
        import base64
        ep=self.services.pool.endpoints['node-1'];ep.started=True
        cfg=o.native.session.configuration(ep.value,ep.session,o.native.session.MODES[2]);client=ep.client(cfg)
        with patch.object(o.native.iap,'_network_exchange',return_value=m.canonical({'ready':None,'closed':None})) as call:
            result=client.ready(self.source.deadline)
        args=call.call_args.args;self.assertIs(self.source,args[0]);self.assertEqual(ep.target,args[1])
        self.assertEqual('service',args[2][4]);self.assertEqual(ep.session,m.strict_json(base64.b64decode(args[2][6])))
        self.assertEqual('ready',args[2][-1]);self.assertIsNone(result['ready'])
        self.assertEqual(2,self.recheck.call_count)
    def test_session_guards_and_transport_share_short_deadline_and_drift_is_terminal(self):
        ep=self.services.pool.endpoints['node-1']
        expected=dict(state='SUCCEEDED',sessionSha256=m.sha(m.canonical(ep.session)))
        self.recheck.side_effect=[None,ValueError('changed provider identity')]
        with patch.object(o.native.iap,'_network_exchange',return_value=m.canonical(expected)) as exchange,\
             self.assertRaises(o.native.recovery.RecoveryError) as caught:ep.begin()
        self.assertEqual('SESSION_REJECTED',caught.exception.code)
        self.assertEqual(1,exchange.call_count)
        until=exchange.call_args.args[4]
        self.assertEqual([{'deadline':until}]*2,[call.kwargs for call in self.recheck.call_args_list])
        self.assertEqual(1,len(self.source.session_recoveries[0]['events']))
    def test_native_readiness_keeps_exactly_one_pair_of_current_checks(self):
        from .test_cloud_runner_guest_setup import request
        value=request();value['binding']['node']='node-1'
        checks=[]
        disk=o.setup._VolumeEndpoint(self.source,{},value,lambda:checks.append('identity'))
        disk.started=True;disk.budget={'original':'budget'}
        self.services.pool.disks['node-1']=disk
        group=self.services.group();answer=dict(schema='gse-v51-native-volume-transport-v1',
            requestSha256=m.sha(m.canonical(value)),deadlineSha256=m.sha(m.canonical(disk.budget)),
            state='SUCCEEDED',readiness={'mount':'checked'})
        def exchange(*args,**kwargs):checks.append('remote');return m.canonical(answer)
        duplicate=Mock(side_effect=AssertionError('redundant wrapper'))
        with patch.object(o.native.iap,'_network_exchange',side_effect=exchange):
            self.assertEqual(answer['readiness'],group.mounted_readiness(1,duplicate,duplicate))
            self.assertEqual(answer['readiness'],group.mounted_readiness(1,duplicate,duplicate))
        self.assertEqual(['identity','remote','identity']*2,checks)
        disk.recheck=Mock(side_effect=[None,ValueError('post-check changed')])
        with patch.object(o.native.iap,'_network_exchange',return_value=m.canonical(answer)) as exchange,\
             self.assertRaisesRegex(ValueError,'post-check changed'):
            group.mounted_readiness(1,duplicate,duplicate)
        self.assertEqual(2,disk.recheck.call_count);exchange.assert_called_once()
        disk.recheck=Mock(side_effect=ValueError('lease changed'))
        with patch.object(o.native.iap,'_network_exchange') as exchange,self.assertRaisesRegex(ValueError,'lease changed'):
            group.mounted_readiness(1,duplicate,duplicate)
        exchange.assert_not_called()
    def test_native_readiness_rejects_wrong_endpoint_owner(self):
        group=self.services.group();self.services.pool.disks['node-1']=Mock()
        with self.assertRaisesRegex(ValueError,'original endpoint'):group.mounted_readiness(1,Mock(),Mock())
    def test_promote_requires_same_original_owner_and_keeps_session_deadlines(self):
        pool=self.services.pool;pool.started=True;before={k:deepcopy(v.session) for k,v in pool.endpoints.items()}
        owner=o._Api(self.source);owner.admit();checks={k:Mock() for k in pool.endpoints}
        pool.promote(owner,checks)
        self.assertTrue(all(ep.api is owner for ep in pool.endpoints.values()))
        self.assertEqual(before,{k:ep.session for k,ep in pool.endpoints.items()})
        with self.assertRaises(ValueError):pool.promote(owner,checks)


class LifecycleTest(unittest.TestCase):
    """The real owner/retention/cleanup controller around a deterministic probe.

    Native guest wiring is checked in BridgeTest. Real JVM history is qualified
    separately by the existing complete experiment gate, never by this probe.
    """
    setUpClass=classmethod(OwnerTest.setUpClass.__func__)
    prepare_source=OwnerTest.prepare_source
    setUp=BridgeTest.setUp

    def execute(self,fault=None,*,preparation_seconds=0,relative=False):
        import shutil
        from .remote_budget import Budget
        test=self;events=[];clock=self.f['clock']
        class Services:
            def __init__(self,provider,archive,prepared):
                self.provider=provider;self.pool=test.services.pool;self.root=None
            def prepare(self,req,facts,targets,startup,output,deadline,**checks):
                test.assertTrue(Path(output).is_absolute())
                self.root=Path(output);self.root.mkdir();events.append('prepare-services')
            def stop(self,deadline):
                events.append('stop-services')
                ep=test.services.pool.endpoints['node-1'];cfg=o.native.session.configuration(ep.value,ep.session,o.native.session.MODES[2])
                ep.client(cfg).shutdown(deadline)
                if fault=='stop':raise ValueError('service stop failure')
            def retention_files(self):yield 'services.json',b'original startup'
        class Probe:
            engineWorkloadExecuted=False
            def __init__(self,services,root):test.assertTrue(Path(root).is_absolute());self.cells=[]
            def prepare(self,req,deadline):events.append('prepare-probe')
            def cell(self,name,deadline):
                events.append(name);self.engineWorkloadExecuted=True;clock.sleep(1)
                # Cross the real API promotion and provider/lease/host guards;
                # only the remote process and its response are synthetic.
                for ep in test.services.pool.endpoints.values():
                    cfg=o.native.session.configuration(ep.value,ep.session,o.native.session.MODES[2])
                    ep.client(cfg).ready(deadline/1e9)
                if fault==name:raise ConnectionError('lost original window')
                self.cells.append(name)
            def stop(self):events.append('stop-probe')
            def collect_validate(self,root,deadline):
                test.assertTrue(Path(root).is_absolute())
                events.append('validate')
                ep=test.services.pool.endpoints['node-1'];cfg=o.native.session.configuration(ep.value,ep.session,o.native.session.MODES[2])
                ep.client(cfg).part('part-0000.bin',4096,deadline/1e9)
                if fault=='collect':raise ValueError('invalid collection')
                return dict(status='FAIL' if fault=='evidence' else 'PASS',scope=o.experiment.SCOPE,execution=n.EXECUTION,
                    paidCloud=True,fullRemoteQualification=False,engineWorkloadExecuted=self.engineWorkloadExecuted,
                    physicalHistoryQualified=True,backupRestoreQualified=True,cells=self.cells)
            def retention_files(self):yield 'part-0000.bin',b'original history'
        def prepare(root,continuation):
            shutil.copytree(self.root/'preparation',root)
            clock.sleep(preparation_seconds)
            continuation(self.source,self.archive,self.prepared)
            return self.preparation
        if fault=='upload':
            send=self.source.transport.send
            def lost(method,url,*args):
                result=send(method,url,*args)
                if method=='POST' and 'owned-experiment' in url:raise ConnectionError('upload interrupted')
                return result
            self.source.transport.send=lost
        def exchange(api,target,remote,data,deadline,**options):
            if remote[4]=='begin':
                ep=next(ep for ep in test.services.pool.endpoints.values() if ep.target==target)
                return m.canonical(dict(state='SUCCEEDED',sessionSha256=m.sha(m.canonical(ep.session))))
            return m.canonical(dict(ready=None,closed=None))
        with patch.object(o,'Budget',side_effect=lambda **kwargs:Budget(clock=clock.nanos,**kwargs)),\
             patch.object(o.time,'monotonic_ns',side_effect=clock.nanos),\
             patch.object(o.native.iap,'_network_exchange',side_effect=exchange),\
             patch.object(o.native,'Services',Services),patch.object(o.native,'Probe',Probe):
            with chdir(self.root):
                result=o._execute(Path('execution') if relative else self.root/'execution',prepare)
        return result,events
    def test_complete_controller_finishes_all_cells_validation_cleanup_and_ledger(self):
        result,events=self.execute();self.assertEqual('PASS',result['status'],result)
        self.assertEqual(['prepare-services','prepare-probe',*o.experiment.CELLS,'stop-probe','validate','stop-services'],events)
        self.assertTrue(result['leaseReleased']);self.assertEqual({},self.f['http'].resources)
    def test_relative_controller_completes_cells_validation_retention_and_cleanup(self):
        result,events=self.execute(relative=True)
        self.assertEqual('PASS',result['status'],result)
        self.assertEqual(list(o.experiment.CELLS),[v for v in events if v in o.experiment.CELLS])
        self.assertEqual('VERIFIED',result['retention']);self.assertTrue(result['leaseReleased'])
        self.assertEqual({},self.f['http'].resources)
    def test_relative_controller_keeps_failed_cell_evidence_and_cleans_once(self):
        result,events=self.execute('healthy',relative=True)
        self.assertEqual('FAIL',result['status']);self.assertEqual(1,events.count('healthy'))
        self.assertNotIn('leader-loss',events);self.assertEqual('VERIFIED',result['retention'])
        self.assertTrue(result['leaseReleased']);self.assertEqual('PASS',result['cleanup']['status'])
    def test_admitted_slow_preparation_finishes_cells_retention_cleanup_and_charge(self):
        result,events=self.execute(preparation_seconds=1500)
        self.assertEqual('PASS',result['status'],result)
        self.assertEqual(1500*10**9,result['budget']['spentNanos']['preparation'])
        self.assertEqual(1,events.count('healthy'));self.assertTrue(result['leaseReleased'])
        self.assertEqual('PASS',result['cleanup']['status']);self.assertEqual('VERIFIED',result['retention'])
        # Read the retained terminal ledger using the ordinary read-only API.
        store=g.Store(self.f['cfg']['provider'],h.Api(transport=self.f['http'],tokens=lambda _: 'offline',
            clock=self.f['clock'].seconds),authority=n)
        cost,entries=n.inspect_ledger(store.get(n.LEDGER)[1])
        self.assertEqual(q.q.COST,cost);self.assertEqual({'PASS'},{row['status'] for row in entries.values()})
    def test_failed_window_is_not_replayed_and_still_retains_then_cleans(self):
        result,events=self.execute('healthy');self.assertEqual('FAIL',result['status'],result)
        self.assertEqual(1,events.count('healthy'));self.assertNotIn('leader-loss',events)
        self.assertEqual('PASS',result['cleanup']['status']);self.assertTrue(result['leaseReleased'])
        self.assertEqual('RUNTIME_TRANSPORT',result['errors'][0]['code'])
        self.assertEqual('healthy',result['errors'][0]['cell']);self.assertNotIn('lost original window',str(result))
    def test_collection_failure_keeps_partial_history_and_cleans(self):
        result,events=self.execute('collect');self.assertEqual('FAIL',result['status'],result)
        self.assertIsNotNone(result['cleanup'],result)
        self.assertEqual('PASS',result['cleanup']['status']);self.assertTrue(result['leaseReleased'])
        self.assertTrue(any(k.endswith('/parts/part-0000.bin') for k in self.f['http'].objects))
    def test_upload_failure_does_not_skip_compute_cleanup_or_release_unverified_lease(self):
        result,events=self.execute('upload');self.assertEqual('FAIL',result['status'],result)
        self.assertEqual('PASS',result['cleanup']['status']);self.assertFalse(result['leaseReleased'])
        self.assertEqual({},self.f['http'].resources);self.assertEqual('INCOMPLETE',result['retention'])
    def test_failed_service_shutdown_still_deletes_resources_and_preserves_failure(self):
        result,events=self.execute('stop');self.assertEqual('FAIL',result['status'],result)
        self.assertEqual('PASS',result['cleanup']['status']);self.assertTrue(result['leaseReleased'])


class RuntimeIdentityTest(unittest.TestCase):
    """Real promoted API, pool, pinned endpoints and provider reads; synthetic I/O."""
    setUpClass=classmethod(OwnerTest.setUpClass.__func__)
    prepare_source=OwnerTest.prepare_source
    def setUp(self):
        BridgeTest.setUp(self)
        self.pool=self.services.pool;self.pool.started=True
        for ep in self.pool.endpoints.values():ep.started=True
        self.api=o._Api(self.source);self.store=self.api.admit()
        self.checks=o._runtime_rechecks(self.api,self.store,self.prepared,self.api.lease,self.api.lease_generation)
        self.pool.promote(self.api,self.checks)
        self.ep=self.pool.endpoints['node-1']
        cfg=o.native.session.configuration(self.ep.value,self.ep.session,o.native.session.MODES[2])
        self.client=self.ep.client(cfg)

    def test_first_submit_all_cells_and_collection_use_fresh_exact_reads_after_preparation_expires(self):
        # The runtime must not retain the consumed preparation API/deadline.
        self.f['clock'].sleep(1801);self.api.stage('healthy',self.api.clock()+300)
        original=self.api.transport.send;calls=[]
        def send(method,url,*args):
            calls.append(url);return original(method,url,*args)
        with patch.object(self.api.transport,'send',side_effect=send),\
             patch.object(o.native.iap,'_network_exchange',return_value=b'{"state":"RUNNING"}') as ssh:
            for phase in (*o.experiment.CELLS,'validation-retention'):
                if phase!='healthy':self.api.stage(phase,self.api.clock()+30)
                start=len(calls);until=self.api.clock()+10
                answer=self.client.submit({'command':'start-voter'},until)
                self.assertEqual('RUNNING',answer['state'])
                compute=[url for url in calls[start:] if url.startswith('https://compute.')]
                self.assertEqual(14,len(compute))  # seven before, seven after
                self.assertEqual(2,sum('/getGuestAttributes?' in url for url in compute))
                self.assertEqual(until,ssh.call_args.args[4]);self.assertIs(self.api,ssh.call_args.args[0])
            self.assertEqual(5,ssh.call_count)
        self.assertEqual({},self.api.resolved)

    def test_pre_command_guard_rejects_missing_authority_without_ssh(self):
        self.api.stage('healthy',self.api.clock()+30)
        for key in (n.LEASE,n.LEDGER):
            old=self.f['http'].objects.pop(key)
            try:
                with patch.object(o.native.iap,'_network_exchange') as ssh,self.assertRaisesRegex(ValueError,'authority changed'):
                    self.client.ready(self.api.clock()+10)
                ssh.assert_not_called()
            finally:self.f['http'].objects[key]=old

    def test_changed_retained_generation_rejects_before_ssh(self):
        self.api.stage('healthy',self.api.clock()+30)
        generation,raw,content=self.f['http'].objects[n.LEASE]
        self.f['http'].objects[n.LEASE]=(generation+1,raw,content)
        with patch.object(o.native.iap,'_network_exchange') as ssh,self.assertRaisesRegex(ValueError,'generation changed'):
            self.client.ready(self.api.clock()+10)
        ssh.assert_not_called()

    def test_before_and_after_command_identity_drift_is_terminal_without_replay(self):
        self.api.stage('healthy',self.api.clock()+30)
        pin=Path(self.ep.target['knownHosts']);original=pin.read_bytes()
        pin.write_bytes(original+b'\n')
        with patch.object(o.native.iap,'_network_exchange') as ssh,self.assertRaisesRegex(ValueError,'pinned host changed'):
            self.client.ready(self.api.clock()+10)
        ssh.assert_not_called();pin.write_bytes(original)
        def changed(*args,**kwargs):pin.write_bytes(original+b'\n');return b'{"state":"RUNNING"}'
        with patch.object(o.native.iap,'_network_exchange',side_effect=changed) as ssh,self.assertRaisesRegex(ValueError,'pinned host changed'):
            self.client.submit({'command':'start-voter'},self.api.clock()+10)
        ssh.assert_called_once()

    def test_replacement_between_resource_samples_is_rejected_before_ssh(self):
        self.api.stage('healthy',self.api.clock()+30)
        original=self.api.transport.send;changed=False
        def send(method,url,*args):
            nonlocal changed
            status,raw=original(method,url,*args)
            if '/getGuestAttributes?' in url:changed=True
            elif changed and '/instances/' in url:
                body=m.strict_json(raw);body['id']='99999999';raw=m.canonical(body)
            return status,raw
        with patch.object(self.api.transport,'send',side_effect=send),\
             patch.object(o.native.iap,'_network_exchange') as ssh,self.assertRaisesRegex(ValueError,'numeric lookup identity'):
            self.client.ready(self.api.clock()+10)
        self.assertTrue(changed);ssh.assert_not_called()

    def test_all_guard_reads_share_the_short_exchange_deadline(self):
        self.api.stage('healthy',self.api.clock()+30)
        until=self.api.clock()+.5;original=self.api.transport.send;timeouts=[]
        def delayed(method,url,headers,body,timeout,maximum):
            timeouts.append(timeout);self.f['clock'].sleep(.2)
            return original(method,url,headers,body,timeout,maximum)
        with patch.object(self.api.transport,'send',side_effect=delayed),\
             patch.object(o.native.iap,'_network_exchange',return_value=b'{}') as ssh,self.assertRaisesRegex(ValueError,'late response'):
            self.client.ready(until)
        ssh.assert_not_called();self.assertEqual(3,len(timeouts))
        self.assertLessEqual(max(timeouts),.5)

    def test_post_command_guard_cannot_extend_an_expired_exchange(self):
        self.api.stage('healthy',self.api.clock()+30)
        until=self.api.clock()+1
        def late(*args,**kwargs):self.f['clock'].sleep(1);return b'{"state":"RUNNING"}'
        with patch.object(o.native.iap,'_network_exchange',side_effect=late) as ssh,\
             self.assertRaisesRegex(ValueError,'runtime identity deadline'):
            self.client.submit({'command':'start-voter'},until)
        ssh.assert_called_once()

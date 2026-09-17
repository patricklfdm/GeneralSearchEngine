"""Remote protocol, process identity, admission and resealed provenance counterexamples."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch
from .cloud_common import canonical, plan, save, sha
from .cloud_remote_contract import schedule, measurement_seconds
from .cloud_remote_guest import Guest, SCHEMA, EXECUTION, alive
from .cloud_remote_probe import RemoteProbe, RemoteWorker, collection_member
from .cloud_remote_evidence import provenance, timings, validate_raw, validate_bundle, validate_set
from .cloud_workload_plan import PLAN, PLAN_SHA256
from .cloud_workload_io import inventory
from .cloud_presets import workload_request
from .cloud_preflight import admission, check_observations
from .test_cloud_runner import observations


class RemoteTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.base=self.root/'bundle';self.base.mkdir();shutil.copyfile(PLAN,self.base/'workload.json')
        save(self.base/'bundle.json',dict(schema=SCHEMA,execution=EXECUTION,workloadPlanSha256=PLAN_SHA256))
        self.owner='gse-v50-012345abcdef'

    def test_guest_rejects_local_paths_without_qualification(self):
        with self.assertRaisesRegex(ValueError,'path boundary'):Guest(self.base,self.root,self.owner)

    def test_guest_refuses_other_bundle_families(self):
        for schema in ('gse-v50-cloud-bundle-v1','gse-v50-cloud-workload-bundle-v1'):
            with self.subTest(schema=schema):
                save(self.base/'bundle.json',dict(schema=schema,execution=EXECUTION,workloadPlanSha256=PLAN_SHA256))
                with self.assertRaisesRegex(ValueError,'bundle required'):Guest(self.base,self.root,self.owner,qualification=True)

    def test_worker_generations_and_public_replacement_args(self):
        g=Guest(self.base,self.root,self.owner,qualification=True);endpoints='a:1,b:2,c:3'
        first=g.args('worker',3,endpoints,'canonical',1);second=g.args('worker',3,endpoints,'canonical',2)
        self.assertNotEqual(first,second);self.assertTrue(first[-2].endswith('streams/node-3-1'))
        replacement=g.args('replace',1,endpoints,'canonical',source=2)
        self.assertEqual(replacement[-4:],['replace','1','2','volumes'])
        self.assertIn('io.github.patricklfdm.generalsearch.admission.V50CloudWorkloadConsumer',replacement)
        for node,generation in ((0,1),(1,0),(3,33)):
            with self.assertRaises(ValueError):g.args('worker',node,endpoints,'canonical',generation)
        with self.assertRaises(ValueError):g.args('replace',3,endpoints,'canonical',source=2)

    def test_existing_generation_cannot_be_restarted(self):
        g=Guest(self.base,self.root,self.owner,qualification=True);save(g.receipt_path(1,1),{})
        with patch('os.execv') as execute,self.assertRaisesRegex(ValueError,'already used'):g.worker(1,1,'a:1,b:2,c:3','canonical')
        execute.assert_not_called()

    def test_pid_reuse_is_not_termination(self):
        raw='123 (java) S '+' '.join(['0']*18+['456'])
        with patch('pathlib.Path.exists',return_value=True),patch('pathlib.Path.read_text',return_value=raw):
            with self.assertRaisesRegex(ValueError,'reused guest PID'):alive(dict(pid=123,startTicks='999'))
            self.assertTrue(alive(dict(pid=123,startTicks='456')))

    def test_capture_labels_cannot_select_arbitrary_paths(self):
        g=Guest(self.base,self.root,self.owner,qualification=True)
        for label in ('../../escape','source','capacity-before-99'):
            with self.subTest(label=label),self.assertRaises(ValueError):g.capture(1,label)

    def test_guest_namespace_and_path_traversal(self):
        self.assertTrue(collection_member(3,'streams/node-3-2/calls/part-0000.jsonl'))
        self.assertTrue(collection_member(1,'export/gse-backup-checkpoint'))
        for node,name in ((3,'streams/node-1-2/calls/x'),(2,'export/x'),(3,'volume-3/materialization-node-3/x'),
                          (1,'workers/node-2-1.json'),(1,'cuts/other/node-1/x')):
            self.assertFalse(collection_member(node,name),(node,name))
        for name in ('../x','/x','streams/../x'):
            with self.assertRaises(ValueError):collection_member(1,name)

    def test_cloud_and_qualification_schedules_remain_distinct(self):
        self.assertEqual(schedule('canonical')['windows'],['warmup','baseline-a','instrumented-a','instrumented-b','baseline-b','sustained'])
        self.assertEqual(schedule('failure-drill')['windows'],['warmup'])
        self.assertEqual(len(schedule('failure-drill',control=True)['windows']),5)
        self.assertEqual(measurement_seconds('canonical','baseline-a'),120)
        self.assertEqual(measurement_seconds('canonical','sustained'),300)
        self.assertEqual(schedule('experiment')['healthyIntervalNanos'],100_000_000)
        self.assertEqual(schedule('local-qualification')['pacing'],'completion-paced')
        with self.assertRaises(ValueError):schedule('unreviewed')

    def catchup_probe(self, responses):
        probe=RemoteProbe.__new__(RemoteProbe);probe.deadline=120;probe.cell_deadline=110
        probe.command=Mock(side_effect=responses)
        return probe

    def catchup_failure(self, reason='QUORUM_UNAVAILABLE', **status):
        return dict(command='catchup',accepted=False,reason=reason,
                    status=dict(dict(state='READY',writeQuorum=True),**status))

    def test_catchup_retries_peer_timeout_and_capacity_until_public_success(self):
        success=dict(command='catchup',accepted=True,verifiedIndex=1131)
        probe=self.catchup_probe([self.catchup_failure('CAPACITY_EXCEEDED'),self.catchup_failure(),success])
        with patch('scripts.v50.cloud_remote_probe.time.monotonic',return_value=100), \
             patch('scripts.v50.cloud_remote_probe.time.sleep') as sleep:
            self.assertEqual(probe.catchup(3),success)
        self.assertEqual(probe.command.call_count,3);self.assertEqual(sleep.call_count,2)
        self.assertTrue(all(c.kwargs['peer']=='node-3' and c.kwargs['response_timeout']<=10 for c in probe.command.call_args_list))

    def test_catchup_does_not_retry_safety_failures_or_suspended_leader(self):
        failures=[self.catchup_failure(reason) for reason in
            ('CONFLICTING_HISTORY','STALE_EPOCH','INTEGRITY_FAILURE','PROTOCOL_MISMATCH','STORAGE_FAILURE','CLOSED')]
        failures += [dict(self.catchup_failure(),status=dict(state=state,writeQuorum=quorum)) for state,quorum in
                     [('READY',False),('UNAVAILABLE',True),('FAILED',True)]]
        for failure in failures:
            with self.subTest(failure=failure):
                probe=self.catchup_probe([failure])
                with patch('scripts.v50.cloud_remote_probe.time.monotonic',return_value=100), \
                     patch('scripts.v50.cloud_remote_probe.time.sleep') as sleep, \
                     self.assertRaisesRegex(ValueError,failure['reason']):probe.catchup(3)
                self.assertEqual(probe.command.call_count,1);sleep.assert_not_called()

    def test_catchup_persistent_timeout_exhausts_attempts_with_last_response(self):
        probe=self.catchup_probe([self.catchup_failure()]*20)
        with patch('scripts.v50.cloud_remote_probe.time.monotonic',return_value=100), \
             patch('scripts.v50.cloud_remote_probe.time.sleep') as sleep, \
             self.assertRaisesRegex(ValueError,'20 attempts.*QUORUM_UNAVAILABLE'):probe.catchup(3)
        self.assertEqual(probe.command.call_count,20);self.assertEqual(sleep.call_count,19)

    def test_catchup_respects_cell_and_run_deadlines_without_extending_waits(self):
        for cell,run in [(101.62,120),(120,101.62)]:
            with self.subTest(cell=cell,run=run):
                clock=[100.0];probe=self.catchup_probe([]);probe.cell_deadline=cell;probe.deadline=run
                def rejected(*args,**kwargs):clock[0]+=1.6;return self.catchup_failure()
                probe.command.side_effect=rejected
                with patch('scripts.v50.cloud_remote_probe.time.monotonic',side_effect=lambda:clock[0]), \
                     patch('scripts.v50.cloud_remote_probe.time.sleep') as sleep, \
                     self.assertRaisesRegex(ValueError,'deadline.*QUORUM_UNAVAILABLE'):probe.catchup(3)
                self.assertEqual(probe.command.call_count,1);sleep.assert_not_called()
                self.assertAlmostEqual(probe.command.call_args.kwargs['response_timeout'],1.62)
        probe=self.catchup_probe([]);probe.cell_deadline=100
        with patch('scripts.v50.cloud_remote_probe.time.monotonic',return_value=100),self.assertRaisesRegex(ValueError,'deadline'):
            probe.catchup(3)
        probe.command.assert_not_called()

    def test_remote_wait_budget_is_not_sent_to_the_guest(self):
        worker=RemoteWorker.__new__(RemoteWorker);worker.receipt={};worker.path=self.root/'member.json'
        worker.send=Mock(return_value=dict(outcome='indeterminate'))
        worker.receive=Mock(return_value=dict(command='catchup',accepted=False))
        worker.command('catchup',accepted=None,peer='node-3',response_timeout=.25)
        worker.send.assert_called_once_with('catchup',peer='node-3')
        worker.receive.assert_called_once_with(.25)

    def test_full_admission_requires_executed_remote_gate(self):
        p=plan();req=workload_request('a'*40,1,1,'b'*64,'experiment','c'*32)
        observed=observations(p)
        approval=dict(schema='gse-v50-paid-admission-v1',confirmed=True,requestSha256=sha(canonical(req)),
            planSha256=sha(canonical(p)),expiresAt=1900,maximumCostMicrousd=1_000_000,previousAttemptsCostMicrousd=0,
            priceSources=['reviewed-price'],pricedThroughTopologySeconds=5400,cleanupOverhangSeconds=1080,
            estimateIncludes=['three-vms','boot-disks','data-disks','control','evidence','cleanup','failed-attempts'])
        for gate in (None,'skipped','failure','success'):
            observed['github']['remoteGate']=gate;receipt=check_observations(p,observed,req['source'],1000)
            approval['preflightSha256']=sha(canonical(receipt))
            if gate=='success':admission(p,receipt,req,approval,now=1001)
            else:
                with self.assertRaisesRegex(ValueError,'remote workload gate'):admission(p,receipt,req,approval,now=1001)

    def test_incomplete_or_fake_cloud_set_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'complete experiment'):validate_set([])
        paths=[]
        for i in range(5):
            p=self.root/str(i);save(p/'completion.json',dict(schema='gse-v50-cloud-lifecycle-v1',execution='fake-owned-runner-only'))
            paths.append(p)
        with self.assertRaisesRegex(ValueError,'real complete'):validate_set(paths)

    def cloud_provenance(self):
        p=plan();req=workload_request('a'*40,1,1,'b'*64,'experiment','c'*32,nonce='012345abcdef')
        bundle=dict(schema=SCHEMA,execution=EXECUTION,workloadPlanSha256=PLAN_SHA256,inputs={},source=req['source'],dirty=False)
        save(self.root/'remote-bundle.json',bundle)
        save(self.root/'metadata.json',dict(head=req['source'],dirty=False,inputs={},javaExecutable='/opt/gse-v50/jre/bin/java'))
        save(self.root/'set.json',dict(execution='gcp-cloud-workload',preset='experiment'))
        endpoints='10.0.0.1:9700,10.0.0.2:9700,10.0.0.3:9700';hosts=[]
        for node in (1,2,3):
            observed=dict(id=str(node),labels={'gse-owner':self.owner,'gse-source':req['source']},
                zone='/zones/'+p['zone'],machineType='/machineTypes/'+p['machineType'],serviceAccounts=[],
                scheduling=dict(instanceTerminationAction='DELETE',maxRunDuration=dict(seconds='5400')),
                networkInterfaces=[dict(networkIP=f'10.0.0.{node}',accessConfigs=[])])
            vm=dict(kind='instances',node=node,name=self.owner+f'-n{node}',id=str(node),observation=observed)
            mount=dict(filesystems=[dict(fstype='ext4',target=f'/mnt/gse-v50/volume-{node}')],instanceId='1',
                diskId='d'+str(node),diskName=self.owner+f'-n{node}-data',
                attachment=dict(source='/disks/'+self.owner+f'-n{node}-data',autoDelete=True))
            host=dict(instance=vm,initialMount=mount,facts=dict(bootId=f'boot-{node}',java='21.0.12+8',bundle=bundle,qualification=False),
                distribution=dict(installed=True,manifest=bundle,bundleSha256=req['bundleSha256']))
            if node!=1:host['runtimeMount']=dict(mount,instanceId=str(node))
            hosts.append(host)
            args=['java','/mnt/gse-v50',str(node),endpoints,'/opt/gse-v50/workload.json',f'/mnt/gse-v50/streams/node-{node}-1','volumes']
            # Identical numeric PIDs on distinct VMs are legitimate.
            member=dict(generation=1,pid=123,linuxStartTicks='456',args=args,instanceId=str(node),bootId=f'boot-{node}',
                forced=False,streams=f'streams/node-{node}-1')
            receipt=dict(owner=self.owner,node=node,generation=1,pid=123,startTicks='456',args=args,bootId=f'boot-{node}')
            save(self.root/'members'/f'node-{node}-1.json',member);save(self.root/'workers'/f'node-{node}-1.json',receipt)
            save(self.root/'stops'/f'node-{node}-1.json',dict(receipt,status='EXITED',barrier=None))
        document=dict(schema='gse-v50-remote-workload-hosts-v1',qualification=False,request=req,plan=p,endpoints=endpoints,hosts=hosts)
        save(self.root/'hosts.json',document);return document

    def test_same_pid_on_distinct_cloud_hosts_is_valid(self):
        self.cloud_provenance();provenance(self.root,False)

    def test_cloud_provenance_rejects_vm_boot_endpoint_and_disk_changes(self):
        document=self.cloud_provenance()
        mutations=[lambda d:d['hosts'][2]['instance']['observation'].update(machineType='/machineTypes/other'),
            lambda d:d['hosts'][2]['facts'].update(bootId='boot-1'),
            lambda d:d['hosts'][2]['instance']['observation']['networkInterfaces'][0].update(networkIP='127.0.0.1'),
            lambda d:d['hosts'][2]['runtimeMount'].update(diskName='foreign'),
            lambda d:d['hosts'][2]['runtimeMount'].update(diskId='foreign'),
            lambda d:d['hosts'][2].pop('runtimeMount'),
            lambda d:d['hosts'][2]['instance']['observation'].update(serviceAccounts=[dict(email='unexpected')])]
        for i,mutate in enumerate(mutations):
            with self.subTest(case=i):
                candidate=copy.deepcopy(document);mutate(candidate);save(self.root/'hosts.json',candidate)
                with self.assertRaises(ValueError):provenance(self.root,False)

    def test_control_overhead_uses_existing_reservation_without_shortening_windows(self):
        second=10**9;start=225*second;cells=[]
        p=json.loads(PLAN.read_bytes())
        for spec in p['profiles']['experiment']['cells']:
            cell=dict(name=spec['name'],startedNanos=start,finishedNanos=start+spec['seconds']*second)
            if spec['name']=='healthy':
                cell.update(measurementNanos=120*second,controlOverheadNanos=3*second,
                    details=dict(windows=[dict(calls=300,intervalNanos=100_000_000)]*4))
                cell['finishedNanos']+=3*second
            start=cell['finishedNanos'];cells.append(cell)
        save(self.root/'set.json',dict(startedNanos=0,finishedNanos=start+30*second))
        save(self.root/'timing.json',dict(warmupStartedNanos=200*second,warmupFinishedNanos=225*second))
        save(self.root/'control.json',dict(process=dict(startedNanos=10*second,finishedNanos=160*second)))
        save(self.root/'restore.json',dict(process=dict(startedNanos=start,finishedNanos=start+10*second)))
        save(self.root/'cells.json',cells);timings(self.root,'experiment')
        cells[0]['details']['windows'][0]=dict(calls=299,intervalNanos=100_000_000)
        save(self.root/'cells.json',cells)
        with self.assertRaisesRegex(ValueError,'measurement/control'):timings(self.root,'experiment')
        cells[0]['details']['windows'][0]=dict(calls=300,intervalNanos=100_000_000)
        cells[0]['controlOverheadNanos']=40*second;cells[0]['finishedNanos']+=37*second
        for cell in cells[1:]:cell['startedNanos']+=37*second;cell['finishedNanos']+=37*second
        save(self.root/'cells.json',cells)
        with self.assertRaisesRegex(ValueError,'warmup/control'):timings(self.root,'experiment')

    def test_full_profiles_execute_unchanged_windows_with_separate_control_time(self):
        # Drive the actual cloud orchestration with a virtual controller clock.
        # Qualification alone cannot cover the longer paid-profile timing branch.
        for profile in ('experiment','failure-drill','canonical'):
            with self.subTest(profile=profile):
                clock=[1.0];windows=[]
                def now():
                    clock[0]+=.000001
                    return int(clock[0]*10**9)
                def sleep(seconds):clock[0]+=seconds
                def measure(name):
                    spec=schedule(profile);sustained=name=='sustained'
                    calls=(spec['sustainedCalls'] if sustained else spec['warmupCycles']*10 if name=='warmup' else spec['cyclesPerWindow']*10)
                    interval=spec['sustainedIntervalNanos'] if sustained else spec['healthyIntervalNanos']
                    clock[0]+=calls*interval/1e9+.1;windows.append(name)
                    return dict(calls=calls,intervalNanos=interval)
                probe=RemoteProbe.__new__(RemoteProbe)
                probe.root=self.root/profile;probe.plan=json.loads(PLAN.read_bytes());probe.profile=profile
                probe.qualification=False;probe.cells=[]
                probe.command=lambda *a,**k:sleep(.1)
                probe.measure=measure;probe.configure=lambda name:sleep(.05)
                probe.fault_cell=lambda name:(sleep(1) or {})
                probe.quiesce=lambda:None;probe.control=lambda name:None
                with patch('scripts.v50.cloud_remote_probe.now',side_effect=now),patch('scripts.v50.cloud_remote_probe.time.sleep',side_effect=sleep),patch('builtins.print'):
                    probe.exercise()
                self.assertTrue(probe.completed)
                self.assertEqual(windows,schedule(profile)['windows'])
                self.assertEqual([c['name'] for c in probe.cells],[c['name'] for c in probe.plan['profiles'][profile]['cells']])
                for cell,spec in zip(probe.cells,probe.plan['profiles'][profile]['cells']):
                    self.assertEqual(cell['status'],'PASS')
                    self.assertGreaterEqual(cell['finishedNanos']-cell['startedNanos'],spec['seconds']*10**9)
                    if cell['name'] in ('healthy','sustained'):
                        self.assertEqual(cell['measurementNanos'],spec['seconds']*10**9)
                        self.assertGreater(cell['controlOverheadNanos'],0)


def negatives(root,output):
    root=Path(root);raw=root/'runtime';validate_raw(raw,qualification=True)
    results=[]
    def change(p,fn):
        value=json.loads(p.read_text());fn(value);save(p,value)
    cases={
        'cloud-relabel':lambda r:change(r/'hosts.json',lambda v:v.update(qualification=False)),
        'wrong-source':lambda r:change(r/'metadata.json',lambda v:v.update(head='0'*40)),
        'changed-VM-id':lambda r:change(r/'hosts.json',lambda v:v['hosts'][1]['instance'].update(id=v['hosts'][0]['instance']['id'])),
        'wrong-bundle':lambda r:change(r/'hosts.json',lambda v:v['hosts'][0]['distribution'].update(bundleSha256='0'*64)),
        'wrong-endpoints':lambda r:change(r/'hosts.json',lambda v:v.update(endpoints='10.0.0.1:9700,10.0.0.2:9700,10.0.0.3:9700')),
        'wrong-PID':lambda r:change(r/'workers/node-1-1.json',lambda v:v.update(pid=999999)),
        'wrong-start-ticks':lambda r:change(r/'workers/node-1-1.json',lambda v:v.update(startTicks='0')),
        'wrong-boot':lambda r:change(r/'workers/node-1-1.json',lambda v:v.update(bootId='different')),
        'missing-worker-generation':lambda r:(r/'workers/node-1-2.json').unlink(),
        'missing-stop-proof':lambda r:(r/'stops/node-1-1.json').unlink(),
        'false-normal-stop':lambda r:change(r/'stops/node-1-1.json',lambda v:v.update(status='EXITED')),
        'forged-guest-args':lambda r:change(r/'workers/node-2-1.json',lambda v:v['args'].__setitem__(-4,'foreign-peers')),
        'wrong-preset':lambda r:change(r/'set.json',lambda v:v.update(preset='canonical')),
        'omitted-cell':lambda r:change(r/'cells.json',lambda v:v.pop(0)),
    }
    for name,mutate in cases.items():
        with tempfile.TemporaryDirectory(prefix='gse-remote-negative-') as tmp:
            candidate=Path(tmp)/'raw';shutil.copytree(raw,candidate);mutate(candidate)
            env=json.loads((candidate/'set.json').read_text());env['files']=inventory(candidate,exclude=('set.json',),logical=True);save(candidate/'set.json',env)
            try:validate_raw(candidate,qualification=True)
            except (ValueError,KeyError,TypeError,FileNotFoundError) as error:results.append(dict(case=name,status='REJECTED',reason=str(error)))
            else:raise AssertionError('remote semantic negative accepted: '+name)
    try:validate_bundle(root/'workload-evidence')
    except ValueError:results.append(dict(case='local-bundle-as-cloud',status='REJECTED'))
    else:raise AssertionError('local remote evidence admitted as cloud')
    save(output,results);print(json.dumps(dict(status='PASS',remoteNegatives=len(results))),flush=True)


if __name__=='__main__':
    import sys
    if '--evidence' in sys.argv:
        p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
        a=p.parse_args();negatives(a.evidence,a.output)
    else:unittest.main()

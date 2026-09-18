"""Remote protocol, process identity, admission and resealed provenance counterexamples."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
import unittest
import warnings
import zipfile
from unittest.mock import Mock, patch
from .cloud_common import canonical, plan, save, sha
from .cloud_collection import ARCHIVE_LIMIT, archive_parts, extract_parts
from .cloud_remote_contract import schedule, measurement_seconds
from .cloud_remote_guest import Guest, SCHEMA, EXECUTION, alive
from .cloud_remote_probe import RemoteProbe, RemoteWorker, collection_member
from .cloud_remote_evidence import provenance, timings, validate_raw, validate_bundle, validate_set
from .cloud_workload_plan import PLAN, PLAN_SHA256
from .cloud_workload_io import inventory, pack, sha_file, unpack
from .cloud_presets import ORDER, workload_request
from .cloud_preflight import admission, check_observations
from .test_cloud_runner import observations


class RemoteTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.base=self.root/'bundle';self.base.mkdir();shutil.copyfile(PLAN,self.base/'workload.json')
        save(self.base/'bundle.json',dict(schema=SCHEMA,execution=EXECUTION,workloadPlanSha256=PLAN_SHA256))
        self.owner='gse-v50-012345abcdef'

    def test_set_budget_accepts_new_headroom_and_rejects_excess(self):
        roots=[];states=[]
        for ordinal,(profile,repetition) in enumerate(ORDER,1):
            root=self.root/f'member-{ordinal}';roots.append(root)
            req=workload_request('a'*40,ordinal,1,'b'*64,profile,'c'*32,repetition,nonce=f'{ordinal:012x}')
            state=dict(request=req,startedAt=ordinal*10,finishedAt=ordinal*10+5,
                plan=dict(maximumSequenceCostMicrousd=1_000_000_000),budgetReservation=dict(reservations=[]))
            states.append(state);save(root/'completion.json',state)
        # Isolate the aggregate check from member provenance validation. Even a
        # claimed higher limit in a receipt cannot override the pinned local plan.
        with patch('scripts.v50.cloud_remote_evidence.validate',return_value=dict(artifactSha256='d'*64)):
            for total in (44_480_000,100_000_000,100_000_001):
                with self.subTest(total=total):
                    states[-1]['budgetReservation']['reservations']=[dict(maximumCostMicrousd=22_080_000),
                        dict(maximumCostMicrousd=total-22_080_000)]
                    save(roots[-1]/'completion.json',states[-1])
                    if total<=100_000_000:self.assertEqual(validate_set(roots)['status'],'PASS')
                    else:
                        with self.assertRaisesRegex(ValueError,'cloud set cost ceiling'):validate_set(roots)

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

    def test_collection_downloads_many_parts_in_one_verified_transfer(self):
        guest_root=self.root/'guest';streams=guest_root/'streams/node-1-1/calls';streams.mkdir(parents=True)
        for i in range(100):(streams/f'part-{i:04d}.jsonl').write_bytes(canonical(dict(sequence=i))+b'\n')
        (streams/'empty').touch()
        guest=Guest(self.base,guest_root,self.owner,qualification=True)
        receipt=guest.collect(1,guest_root/'collection-1')
        self.assertEqual(len(receipt['manifest']['files']),101)
        self.assertEqual(sum(len(v['parts']) for v in receipt['manifest']['files'].values()),100)
        probe=RemoteProbe.__new__(RemoteProbe);probe.root=self.root/'runtime';probe.guest_root=guest_root
        probe.guest=Mock(return_value=receipt);probe.hosts={1:{}};probe.backend=Mock()
        def copy(instance,source,target,download):
            self.assertTrue(download);shutil.copyfile(source,target)
        probe.backend.copy.side_effect=copy
        probe.collect(dict(node=1),self.root/'downloads/node-1')
        probe.backend.copy.assert_called_once()
        self.assertEqual(probe.backend.copy.call_args.args[1],str(guest_root/'collection-1.zip'))
        self.assertEqual(inventory(probe.root/'streams'),inventory(guest_root/'streams'))
        self.assertEqual(probe.hosts[1]['collection']['transfers'],1)
        self.assertGreater(probe.hosts[1]['collection']['finishedNanos'],probe.hosts[1]['collection']['startedNanos'])

    def collection_archive(self):
        source=self.root/'source';source.mkdir();(source/'evidence').write_bytes(b'evidence')
        parts=self.root/'parts';manifest=pack(source,parts)
        archive=self.root/'collection.zip';archive_parts(parts,archive)
        return archive,manifest,sha_file(parts/'parts.json')

    def test_collection_archive_preserves_multi_part_reassembly(self):
        source=self.root/'large-source';source.mkdir()
        with (source/'authority').open('wb') as stream:
            for _ in range(33):stream.write(b'x'*(1<<20))
        parts=self.root/'large-parts';manifest=pack(source,parts)
        self.assertEqual(len(manifest['files']['authority']['parts']),2)
        archive=self.root/'large.zip';archive_parts(parts,archive)
        received=self.root/'received';extract_parts(archive,received,manifest,sha_file(parts/'parts.json'))
        restored=self.root/'restored';unpack(received,restored)
        self.assertEqual(inventory(source,logical=True),inventory(restored,logical=True))

    def test_collection_archive_rejects_resealed_invalid_members(self):
        archive,manifest,digest=self.collection_archive()
        with zipfile.ZipFile(archive) as original:
            values={v.filename:original.read(v) for v in original.infolist()}
        for case in ('traversal','missing','extra','duplicate','symlink','compressed','wrong-size','corrupt','manifest'):
            with self.subTest(case=case):
                forged=self.root/(case+'.zip')
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore',UserWarning)
                    with zipfile.ZipFile(forged,'w') as out:
                        for name,raw in values.items():
                            if case=='missing' and name!='parts.json':continue
                            info=zipfile.ZipInfo(name)
                            if name!='parts.json':
                                if case=='traversal':info.filename='../escape'
                                if case=='symlink':info.external_attr=(stat.S_IFLNK|0o777)<<16
                                if case=='compressed':info.compress_type=zipfile.ZIP_DEFLATED
                                if case=='wrong-size':raw+=b'x'
                                if case=='corrupt':raw=b'X'+raw[1:]
                            elif case=='manifest':raw=raw.replace(b'files',b'FILES')
                            out.writestr(info,raw)
                        if case=='extra':out.writestr('unlisted',b'bad')
                        if case=='duplicate':out.writestr('parts.json',values['parts.json'])
                with self.assertRaises(ValueError):extract_parts(forged,self.root/(case+'-parts'),manifest,digest)
        self.assertFalse((self.root/'escape').exists())

    def test_collection_archive_requires_the_exact_chunk_descriptors(self):
        archive,manifest,digest=self.collection_archive()
        for case in ('duplicate','oversized','total','checksum'):
            changed=copy.deepcopy(manifest);item=changed['files']['evidence']
            if case=='duplicate':item['parts'].append(dict(item['parts'][0]))
            elif case=='oversized':item['parts'][0]['bytes']=(32<<20)+1
            elif case=='total':changed['bytes']+=1
            else:item['parts'][0]['sha256']='0'*64
            with self.subTest(case=case),self.assertRaises(ValueError):
                extract_parts(archive,self.root/(case+'-parts'),changed,digest)

    def test_collection_rejects_wrong_archive_identity_before_transfer(self):
        for descriptor in (dict(path='/foreign.zip',bytes=1,sha256='a'*64),
                           dict(path='/guest/collection-1.zip',bytes=ARCHIVE_LIMIT+1,sha256='a'*64)):
            probe=RemoteProbe.__new__(RemoteProbe);probe.guest_root=Path('/guest');probe.backend=Mock()
            probe.guest=Mock(return_value=dict(directory='/guest/collection-1',manifest=dict(bytes=0,files={}),archive=descriptor))
            with self.assertRaisesRegex(ValueError,'collection archive descriptor'):
                probe.collect(dict(node=1),self.root/'invalid-download')
            probe.backend.copy.assert_not_called()

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

    def disconnected_worker(self):
        worker=RemoteWorker.__new__(RemoteWorker);worker.node=2;worker.generation=1
        worker.probe=Mock(root=self.root,deadline=time.monotonic()+5)
        worker.path=self.root/'members/node-2-1.json';worker.buffer=b''
        worker.receipt=dict(exchanges=[])
        worker.process=Mock();worker.process.poll.return_value=255
        return worker

    def test_broken_send_retains_node_command_and_indeterminate_exchange(self):
        worker=self.disconnected_worker()
        read_fd,write_fd=os.pipe();os.close(read_fd)
        worker.process.stdin=os.fdopen(write_fd,'wb',buffering=0);self.addCleanup(worker.process.stdin.close)
        with self.assertRaisesRegex(ValueError,'node-2.*configure.*send.*255'):
            worker.command('configure',window='instrumented-a',enabled=True)
        saved=json.loads(worker.path.read_text())
        self.assertEqual(len(saved['exchanges']),1)
        self.assertEqual(saved['exchanges'][0]['outcome'],'indeterminate')
        self.assertNotIn('response',saved['exchanges'][0])
        self.assertEqual(saved['transportFailure']['errorType'],'BrokenPipeError')
        self.assertEqual(saved['transportFailure']['stderr'],'members/node-2-1.stderr')
        worker.process.wait.assert_not_called()

    def test_lost_response_is_not_retried_or_changed_to_success(self):
        worker=self.disconnected_worker()
        read_fd,write_fd=os.pipe();os.close(write_fd)
        worker.process.stdout=os.fdopen(read_fd,'rb');self.addCleanup(worker.process.stdout.close)
        with self.assertRaisesRegex(ValueError,'node-2.*measure.*receive.*255'):
            worker.command('measure',calls=1200,intervalNanos=100_000_000)
        saved=json.loads(worker.path.read_text())
        self.assertEqual(saved['transportFailure']['phase'],'receive')
        self.assertEqual(len(saved['exchanges']),1)
        self.assertEqual(saved['exchanges'][0]['outcome'],'indeterminate')
        self.assertNotIn('response',saved['exchanges'][0])
        worker.process.stdin.write.assert_called_once()

    def test_broken_pipe_flush_does_not_mask_owned_process_cleanup(self):
        worker=self.disconnected_worker();worker.stderr=Mock()
        worker.receipt.update(pid=1953,linuxStartTicks='93298')
        worker.probe.guest.side_effect=[dict(pid=1953,startTicks='93298',status='EXITED'),dict(status='EXITED')]
        worker.process.stdin.close.side_effect=BrokenPipeError(32,'Broken pipe')
        worker.process.returncode=255
        worker.close(killed=True)
        saved=json.loads(worker.path.read_text())
        self.assertEqual(saved['cleanup'],'reaped')
        self.assertEqual(saved['transportExitCode'],255)
        worker.process.stdout.close.assert_called_once();worker.stderr.close.assert_called_once()

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
        env=json.loads((self.root/'set.json').read_text())
        save(self.root/'set.json',dict(env,finishedNanos=env['finishedNanos']+900*second))
        with self.assertRaisesRegex(ValueError,'collection/cleanup reservation: elapsed=.*limit=900s'):
            timings(self.root,'experiment')
        save(self.root/'set.json',env)
        for difference in (-second,2*second):
            changed=copy.deepcopy(cells)
            changed[5]['finishedNanos']+=difference
            save(self.root/'cells.json',changed)
            with self.assertRaisesRegex(ValueError,'elapsed cloud cell budget'):timings(self.root,'experiment')
        save(self.root/'cells.json',cells)
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
                def fault(name):
                    # Paid run 35284962814 completed restart/fencing correctly in
                    # 30.685 s, including serial SSH and guest identity checks.
                    # Maintenance has two restart rounds plus backup/kill work.
                    sleep({'restart':30.685196299,'fencing':30.685196299,'maintenance':75}.get(name,1))
                    return {}
                probe=RemoteProbe.__new__(RemoteProbe)
                probe.root=self.root/profile;probe.plan=json.loads(PLAN.read_bytes());probe.profile=profile
                probe.qualification=False;probe.cells=[]
                probe.command=lambda *a,**k:sleep(.1)
                probe.measure=measure;probe.configure=lambda name:sleep(.05)
                probe.fault_cell=fault
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

    def test_recovery_overrun_still_fails_and_retains_elapsed_diagnostics(self):
        for profile,name in (('experiment','restart'),('experiment','maintenance'),('failure-drill','maintenance')):
            with self.subTest(profile=profile,cell=name):
                clock=[1.0]
                def sleep(seconds):clock[0]+=seconds
                def now():return round(clock[0]*10**9)
                p=json.loads(PLAN.read_bytes());spec=next(c for c in p['profiles'][profile]['cells'] if c['name']==name)
                probe=RemoteProbe.__new__(RemoteProbe)
                probe.root=self.root/profile/name;probe.plan=p;probe.profile=profile
                probe.qualification=False;probe.cells=[];probe.completed=False
                probe.command=lambda *a,**k:None;probe.configure=lambda *a:None
                probe.measure=lambda *a:sleep(20)
                probe.fault_cell=lambda *a:(sleep(spec['seconds']+.25) or {})
                probe.quiesce=Mock();probe.control=Mock()
                with patch('scripts.v50.cloud_remote_probe.preset',return_value=dict(cells=[spec])), \
                     patch('scripts.v50.cloud_remote_probe.now',side_effect=now), \
                     patch('scripts.v50.cloud_remote_probe.time.sleep',side_effect=sleep), \
                     self.assertRaisesRegex(ValueError,f'cloud cell overrun: {name}; elapsed=.*limit={spec["seconds"]}s'):
                    probe.exercise()
                cell=json.loads((probe.root/'cells.json').read_text())[0]
                self.assertEqual(cell['status'],'FAIL')
                self.assertEqual(cell['budgetNanos'],spec['seconds']*10**9)
                self.assertEqual(cell['workNanos'],cell['budgetNanos']+250_000_000)
                self.assertFalse(probe.completed);probe.control.assert_not_called()


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

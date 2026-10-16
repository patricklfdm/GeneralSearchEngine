import copy
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import textwrap
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch
from . import hosted_measurements as h, hosted_measurement_contract as c
from . import measurement_bundle as bundle
from .test_measurement_machine import fixture as local_fixture


def fixture():
    local, actual, expected, results = copy.deepcopy(local_fixture())
    manifest = dict(schema=c.machine.build.SCHEMA, binding=actual, archiveSha256='d'*64,
        files=[dict(path=p, sha256=local['compiled']['candidate']['artifacts'][Path(p).name], size=1)
               for p in c.machine.build.layout(c.ROOT)[:2]])
    plan = dict(schema=c.SCHEMA, status='FROZEN_BEFORE_MEASUREMENTS', paidCloud=False, binding=actual,
                identity=dict(run='12345', attempt=1), contract=c.contract(), compiled=local['compiled'],
                buildManifestSha256=c.hash_value(manifest), buildArchiveSha256=manifest['archiveSha256'])
    records = {}
    for index, (shard, names) in enumerate(c.shards().items()):
        freeze = dict(schema=c.SCHEMA, status='FROZEN_BEFORE_MEASUREMENTS', paidCloud=False, shard=shard,
                      planSha256=c.hash_value(plan), identity=plan['identity'], binding=actual,
                      createdUnixNs=1, storageRoot='/runner/'+shard,
                      environment=dict(bootId='boot-'+shard, storage=dict(fstype='ext4'), cpuModels=['fixture'],
                        logicalCpus=4, affinity=[0,1,2,3], memTotal='16000000 kB', javaExecutable=dict(sha256='e'*64),
                        javacExecutable=dict(sha256='f'*64)))
        members = {}
        for number, name in enumerate(names):
            binding = expected[name]; binding.update(plan['identity']); binding['origin'] = '/runner/'+shard+'/histories/'+name
            result = results[name]; result['binding'] = copy.deepcopy(binding)
            result['manifestSha256'] = c.hash_value([shard, number])
            result.update(inventorySha256='b'*64, archiveSha256='c'*64, archiveBytes=100)
            members[name] = result
        records[shard] = dict(schema=c.SCHEMA, kind='independent-replay', status='PARTIAL', paidCloud=False,
                              qualifiedMeasurement=False, identity=plan['identity'], planSha256=c.hash_value(plan),
                              shard=shard, freeze=freeze, producerReceiptSha256='e'*64, members=members)
    return plan, manifest, records


def disk_package(root):
    plan, manifest, records = fixture(); shard='capacity'; value=records[shard]
    source=root/'input'; source.mkdir(); (source/'packages').mkdir()
    producer=dict(schema=c.SCHEMA, kind='execution', status='PARTIAL', qualifiedMeasurement=False, paidCloud=False,
        shard=shard, planSha256=c.hash_value(plan), freezeSha256=c.hash_value(value['freeze']), identity=plan['identity'], members={})
    for name, result in value['members'].items():
        raw=root/name; raw.mkdir(); (raw/'evidence.txt').write_text(name)
        archive=source/'packages'/(name+'.tar.gz'); index=bundle.pack(raw, archive)
        producer['members'][name]=dict(binding=result['binding'], result=result['result'], domain=result['domain'],
            manifestSha256=result['manifestSha256'], startedUnixNs=2, finishedUnixNs=3,
            archiveBytes=archive.stat().st_size, archiveSha256=bundle.sha_file(archive), inventorySha256=c.hash_value(index))
    h.save(source/'frozen-runner.json', value['freeze']); h.save(source/'receipt.json', producer)
    return plan, shard, source, producer


class HostedMeasurementsTest(unittest.TestCase):
    def test_whole_history_partition_and_all_28_counts(self):
        parts=c.shards(); names=[n for group in parts.values() for n in group]
        self.assertEqual([5,5,5,9,2,2], list(map(len, parts.values())))
        self.assertEqual(28,len(set(names))); self.assertEqual(set(c.machine.members()),set(names))
        for rep in (1,2,3):
            self.assertEqual([c.m01_set.name(mode,rep) for mode in c.model.MODES], parts[f'm01-r{rep}'])
        plan,manifest,records=fixture(); c.validate_plan(plan,plan['binding'],plan['identity'],manifest)
        result=h.aggregate_records(plan,records)
        self.assertEqual((28,27373,2745,878), tuple(result[k] for k in ('histories','originalReads','originalUpdates','negativeRejections')))
        self.assertTrue(result['hostedAcceptance']); self.assertTrue(result['qualifiedMeasurement'])
        for field in ('cloudAcceptance','localMachineAcceptance','protectedFullCI','paidCloud'):
            self.assertFalse(result[field])

    def test_event_guard_rejects_master_pr_and_other_repo(self):
        env=dict(GITHUB_ACTIONS='true', GITHUB_EVENT_NAME='push', GITHUB_REF='refs/heads/'+c.BRANCH,
                 GITHUB_REPOSITORY='patricklfdm/GeneralSearchEngine', GITHUB_RUN_ID='12345', GITHUB_RUN_ATTEMPT='1', GITHUB_SHA='a'*40)
        with patch.dict(os.environ,env,clear=True): self.assertEqual(dict(run='12345',attempt=1),c.context())
        for key,value in [('GITHUB_EVENT_NAME','pull_request'),('GITHUB_REF','refs/heads/master'),
                          ('GITHUB_REPOSITORY','someone/other'),('GITHUB_RUN_ATTEMPT','0'),('GITHUB_SHA','bad')]:
            with self.subTest(key=key),patch.dict(os.environ,dict(env,**{key:value}),clear=True),self.assertRaises(ValueError):c.context()

    def test_plan_rejects_shortening_retries_and_build_or_compiler_drift(self):
        changes=[lambda p:p['contract']['execution'].__setitem__('workloadRetries',1),
                 lambda p:p['contract']['execution']['shards']['m01-r1'].pop(),
                 lambda p:p['contract']['members']['candidate-minimum-r1']['profile'].__setitem__('changed',True),
                 lambda p:p.__setitem__('buildArchiveSha256','0'*64),
                 lambda p:p['compiled']['published']['artifacts'].__setitem__('general-search-engine-5.1.0.jar','0'*64),
                 lambda p:p['compiled']['candidate']['artifacts'].__setitem__('general-search-engine-5.2.0-SNAPSHOT.jar','0'*64),
                 lambda p:p['compiled']['candidate'].__setitem__('classes',{})]
        for change in changes:
            plan,manifest,_=fixture(); change(plan)
            with self.assertRaises(ValueError):c.validate_plan(plan,plan['binding'],plan['identity'],manifest)

    def test_plan_rejects_mixed_attempt_and_source_before_execution(self):
        plan,manifest,_=fixture()
        with self.assertRaisesRegex(ValueError,'source/run/attempt'):
            c.validate_plan(plan,plan['binding'],dict(run='12345',attempt=2),manifest)
        with self.assertRaisesRegex(ValueError,'source/run/attempt'):
            c.validate_plan(plan,dict(plan['binding'],source='f'*40),plan['identity'],manifest)

    def test_aggregate_rejects_missing_shard_and_self_attested_execution(self):
        plan,_,records=fixture(); records.pop('capacity')
        with self.assertRaisesRegex(ValueError,'verifier set'):h.aggregate_records(plan,records)
        plan,_,records=fixture(); records['capacity']['kind']='execution'
        with self.assertRaisesRegex(ValueError,'source/attempt/status'):h.aggregate_records(plan,records)

    def test_aggregate_rejects_partial_retries_and_wrong_sources_classes_origin(self):
        for field,value in [('source','f'*40),('run','222'),('attempt',2),('classes',{}),('origin','/other'),('measurementProfile',{})]:
            plan,_,records=fixture(); binding=records['capacity']['members']['m03-p4']['binding']; binding[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):h.aggregate_records(plan,records)
        plan,_,records=fixture(); records['capacity']['identity']=dict(run='12345',attempt=2)
        with self.assertRaisesRegex(ValueError,'source/attempt/status'):h.aggregate_records(plan,records)

    def test_aggregate_rejects_missing_calls_negatives_and_unfinished_histories(self):
        for fault in ('missing','negative','count','status','fakeExecution'):
            plan,_,records=fixture(); members=records['capacity']['members']; result=members['m03-p4']
            if fault=='missing':members.pop('m03-p4')
            if fault=='negative':result['result']['negatives'].pop()
            if fault=='count':result['result']['ledger']['outcomes']['read']['SUCCESS']-=1
            if fault=='status':result['status']='PARTIAL'
            if fault=='fakeExecution':result['result']['execution']='synthetic-fixture'
            with self.subTest(fault=fault),self.assertRaises(ValueError):h.aggregate_records(plan,records)

    def test_reused_histories_and_shared_machine_cannot_be_accepted(self):
        for fault in ('groupId','historyId','manifestSha256','machine'):
            plan,_,records=fixture(); first,second=records['capacity']['members'].values()
            if fault=='machine':records['recovery']['freeze']['environment']['bootId']=records['capacity']['freeze']['environment']['bootId']
            elif fault=='manifestSha256':second[fault]=first[fault]
            else:second['domain'][fault]=first['domain'][fault]
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'reused'):h.aggregate_records(plan,records)

    def test_aggregate_cannot_publish_pass_when_a_matrix_job_failed(self):
        for measured,verified in [('failure','success'),('success','failure'),('success','skipped')]:
            with patch.dict(os.environ,dict(MEASURE_RESULT=measured,VERIFY_RESULT=verified)),\
                 patch.object(h,'load_plan') as load:
                with self.assertRaisesRegex(ValueError,'jobs incomplete or failed'):
                    h.aggregate(Path('/build'),Path('/inputs'),Path('/output'),Mock())
                load.assert_not_called()

    def test_m01_cannot_move_to_another_repetition_runner(self):
        plan,_,records=fixture(); first=next(iter(records['m01-r1']['members'])); second=next(iter(records['m01-r2']['members']))
        records['m01-r1']['members'][second]=records['m01-r2']['members'].pop(second)
        with self.assertRaisesRegex(ValueError,'incomplete shard'):h.aggregate_records(plan,records)

    def test_downloaded_package_binding_hash_and_freeze_precede_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); plan,shard,source,producer=disk_package(root)
            h.validate_input(plan,source,shard)
            path=source/'packages/m03-p4.tar.gz'; path.write_bytes(path.read_bytes()+b'changed')
            with self.assertRaisesRegex(ValueError,'archive changed'):h.validate_input(plan,source,shard)

    def test_freeze_and_member_set_are_not_optional(self):
        for fault in ('clock','missing','failure','freeze','environment'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory); plan,shard,source,producer=disk_package(root)
                if fault=='clock':producer['members']['m03-p4']['startedUnixNs']=0
                if fault=='missing':producer['members'].pop('m03-p4')
                if fault=='failure':producer['status']='FAIL'
                if fault=='freeze':producer['freezeSha256']='0'*64
                if fault=='environment':
                    frozen=h.read(source/'frozen-runner.json');frozen['environment']['bootId']=None;h.save(source/'frozen-runner.json',frozen)
                h.save(source/'receipt.json',producer)
                with self.subTest(fault=fault),self.assertRaises(ValueError):h.validate_input(plan,source,shard)

    def test_independent_verifier_replays_bytes_and_compares_original_result(self):
        for fault in (None,'replay-failure','changed-result'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory); plan,shard,source,producer=disk_package(root); output=root/'verified';output.mkdir()
                def replay(case,binding,spec,out):
                    self.assertEqual(case.name,(case/'evidence.txt').read_text())
                    if fault=='replay-failure':raise ValueError('real evidence invalid')
                    result=copy.deepcopy(producer['members'][case.name]['result'])
                    if fault=='changed-result':result['ledger']['outcomes']['read']['SUCCESS']+=1
                    return result
                def identity(case):return {k:producer['members'][case.name][k] for k in ('domain','manifestSha256')}
                with patch.object(h,'load_plan',return_value=plan),patch.object(h,'source',return_value=plan['binding']),\
                     patch.object(h,'member_identity',side_effect=identity),patch.object(h,'replay',side_effect=replay) as call:
                    if fault:
                        with self.assertRaises(ValueError):h.verify_shard(root/'build',source,output,shard,Mock())
                        self.assertEqual(1,call.call_count)
                        self.assertEqual('FAIL',h.read(output/'receipt.json')['status'])
                        self.assertTrue((output/'downloaded/m03-p4/evidence.txt').exists())
                    else:
                        result=h.verify_shard(root/'build',source,output,shard,Mock())
                        self.assertEqual(2,call.call_count);self.assertEqual('PARTIAL',result['status'])
                        self.assertFalse(result['qualifiedMeasurement']);self.assertFalse((output/'downloaded/m03-p4').exists())
                        self.assertTrue((source/'packages/m03-p4.tar.gz').exists())

    def test_runtime_failure_is_not_retried_and_keeps_raw_evidence(self):
        plan,_,records=fixture(); freeze=records['capacity']['freeze']; started=[]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); output=root/'measure';output.mkdir()
            def prepare(case,name,spec):
                case.mkdir(parents=True);(case/'failure.txt').write_text('retained')
                binding=copy.deepcopy(records['capacity']['members'][name]['binding']);binding['origin']=str(case)
                owner=Mock()
                def fail(*args):started.append(name);raise ValueError('workload failed')
                owner.execute_prepared.side_effect=fail
                return binding,'cp',owner
            with patch.object(h,'load_plan',return_value=plan),patch.object(h,'prime_controls'),\
                 patch.object(h,'current_environment',return_value=freeze['environment']),patch.object(h,'check_machine'),\
                 patch.object(h.shutil,'disk_usage',return_value=type('Disk',(),{'free':100<<30})()),\
                 patch.object(h,'prepare_member',side_effect=prepare),patch.object(h,'replay') as replay:
                with self.assertRaisesRegex(ValueError,'workload failed'):h.run_shard(root/'build',output,'capacity',Mock())
            replay.assert_not_called();self.assertEqual(['m03-p4'],started)
            self.assertEqual('FAIL',h.read(output/'receipt.json')['status'])
            self.assertTrue((output/'histories/m03-p4/failure.txt').exists())

    def test_successful_producer_archives_all_bytes_before_removing_raw_copy(self):
        plan,_,records=fixture(); freeze=records['capacity']['freeze']
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'measure';output.mkdir()
            def prepare(case,name,spec):
                case.mkdir(parents=True);(case/'evidence.txt').write_text(name)
                binding=copy.deepcopy(records['capacity']['members'][name]['binding']);binding['origin']=str(case)
                return binding,'cp',Mock()
            def replay(case,*args):return records['capacity']['members'][case.name]['result']
            def identity(case):return {k:records['capacity']['members'][case.name][k] for k in ('domain','manifestSha256')}
            with patch.object(h,'load_plan',return_value=plan),patch.object(h,'prime_controls'),\
                 patch.object(h,'current_environment',return_value=freeze['environment']),patch.object(h,'check_machine'),\
                 patch.object(h.shutil,'disk_usage',return_value=type('Disk',(),{'free':100<<30})()),\
                 patch.object(h,'prepare_member',side_effect=prepare),patch.object(h,'replay',side_effect=replay),\
                 patch.object(h,'member_identity',side_effect=identity):
                result=h.run_shard(Path(directory)/'build',output,'capacity',Mock())
            self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['qualifiedMeasurement'])
            h.validate_input(plan,output,'capacity')
            for name in c.shards()['capacity']:
                self.assertFalse((output/'histories'/name).exists())
                restored=bundle.unpack(output/'packages'/(name+'.tar.gz'),Path(directory)/name)
                self.assertEqual(name,(restored/'evidence.txt').read_text())

    def test_low_space_fails_before_unpack_and_retains_failure_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan,shard,source,_=disk_package(root);output=root/'verified';output.mkdir()
            with patch.object(h,'load_plan',return_value=plan),\
                 patch.object(h.shutil,'disk_usage',return_value=type('Disk',(),{'free':1})()),patch.object(h,'replay') as replay:
                with self.assertRaisesRegex(ValueError,'insufficient free storage'):
                    h.verify_shard(root/'build',source,output,shard,Mock())
            replay.assert_not_called();self.assertEqual('FAIL',h.read(output/'receipt.json')['status'])
            self.assertFalse((output/'downloaded').exists())

    def test_published_controls_are_hash_checked_before_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);build=root/'build';(build/'published-controls').mkdir(parents=True)
            raw=b'fixture jar';name='fixture.jar';(build/'published-controls'/name).write_bytes(raw)
            plan=dict(compiled=dict(published=dict(artifacts={name:c.digest(raw)})))
            with patch.object(h,'ROOT',root):h.prime_controls(build,plan)
            self.assertEqual(raw,(root/'target/v52-controls'/name).read_bytes())
            with patch.object(h,'ROOT',root),self.assertRaisesRegex(ValueError,'existing published control'):h.prime_controls(build,plan)
            (build/'published-controls'/name).write_bytes(b'changed')
            with patch.object(h,'ROOT',root),self.assertRaisesRegex(ValueError,'published control changed'):h.prime_controls(build,plan)

    def test_environment_drift_rejected(self):
        plan,_,records=fixture();freeze=records['capacity']['freeze']
        with patch.object(h,'source',return_value=plan['binding']),patch.object(c,'context',return_value=plan['identity']),\
             patch.object(h,'current_environment',return_value=dict(freeze['environment'],bootId='other')):
            with self.assertRaisesRegex(ValueError,'runner changed'):h.check_machine(plan,freeze,Path('/fixture'))

    def test_quiet_stage_emits_progress_without_workload_poll_or_retry(self):
        with tempfile.TemporaryDirectory() as directory,redirect_stdout(io.StringIO()) as stream:
            root=Path(directory)
            with h.Progress(root,interval=.01) as progress:
                progress.stage('original-workload','fixture',2);time.sleep(.045)
            values=[json.loads(line) for line in stream.getvalue().splitlines()]
            self.assertGreaterEqual(len(values),4)
            self.assertTrue(any(v['member']=='fixture' and v['phaseSeconds']>=0 for v in values))
            self.assertEqual('finished',h.read(root/'progress.json')['stage'])

    def test_disk_reclamation_refuses_local_or_wrong_branch_before_any_cleanup(self):
        action=(c.ROOT/'.github/actions/v52-hosted-setup/action.yml').read_text()
        script=textwrap.dedent(action.split('      run: |\n')[1].split('    - name: Set up Java')[0])
        for env in ({},dict(RUNNER_ENVIRONMENT='self-hosted'),dict(RUNNER_ENVIRONMENT='github-hosted',
                     GITHUB_EVENT_NAME='push',GITHUB_REF='refs/heads/master')):
            result=subprocess.run(['bash','-c',script],env=env,capture_output=True,text=True)
            self.assertNotEqual(0,result.returncode)
            self.assertEqual('',result.stdout)
        self.assertIn('/usr/share/dotnet /usr/local/lib/android /opt/ghc /usr/local/.ghcup',script)
        self.assertIn('rm -rf --one-file-system -- "$unused"',script)
        self.assertIn('available < 17179869184',script)

    def test_workflow_branch_only_and_attempt_names_are_explicit(self):
        workflow=(c.ROOT/'.github/workflows/v52-hosted-measurements.yml').read_text()
        trigger=workflow.split('\non:\n')[1].split('\npermissions:')[0]
        self.assertEqual('  push:\n    branches: [experiment/v52-hosted-measurements]\n',trigger)
        self.assertNotIn('pull_request:',trigger);self.assertNotIn('workflow_dispatch:',trigger)
        self.assertEqual(2,workflow.count('fail-fast: false'))
        self.assertEqual(2,workflow.count('shard: [m01-r1, m01-r2, m01-r3, minimum-waits, capacity, recovery]'))
        self.assertNotIn('continue-on-error',workflow);self.assertNotIn('id-token:',workflow)
        self.assertNotIn('run-id:',workflow) # Downloads are scoped to this workflow run.
        self.assertIn('needs: [build, measure, verify]',workflow)
        for line in workflow.splitlines():
            if 'name: v52-hosted-' in line or 'pattern: v52-hosted-' in line:
                for identity in ('github.run_id','github.run_attempt','github.sha'):self.assertIn(identity,line)
        self.assertEqual(4,workflow.count('timeout-minutes: 360'))


if __name__=='__main__':unittest.main()

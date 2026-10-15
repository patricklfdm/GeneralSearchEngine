import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import measurement_recovery as r,measurement_model as model,token


class World:
    def __init__(self,case,problem=None):
        self.case=case;self.problem=problem;self.now=10_000_000_000;self.history=[];self.leader='node-2';self.index=1;self.sequence=1
        self.blocked=None;self.killed=[];self.restarted=[];self.partitions=[];self.workers={f'node-{i}':Consumer(self,f'node-{i}') for i in (1,2,3)}
    def clock(self):self.now+=1;return self.now
    def sleep(self,seconds):self.now+=round(seconds*1e9)
    def advance(self):
        for node,w in self.workers.items():
            if node!=self.blocked:w.index=self.index;w.sequence=self.sequence
    def minimum(self,index):
        return base64.b64encode(token.encode(dict(version=1,groupId='00000000-0000-0000-0000-000000000001',
            historyId='00000000-0000-0000-0000-000000000002',manifestDigest='ab'*32,index=index))).decode()
    def crash(self,node):
        self.killed.append(node);self.workers.pop(node);self.leader='node-1';return dict(node=node,exitCode=-9)
    def restart(self,node):
        self.restarted.append(node);self.workers[node]=Consumer(self,node,2);self.advance()
    def partition(self,root,node=None):
        old=self.blocked;self.blocked=node;self.partitions.append(node)
        if node is None:
            self.advance()
            if old is not None:
                self.workers[old].installed=0 if self.problem=='incremental-only' else self.index
                if self.problem=='target-leader':self.leader=old
    def run(self,root):
        with patch.object(r,'partition',side_effect=self.partition):
            return r.observe(root,self.workers,self.history,self.case,self.crash,self.restart,clock=self.clock,sleep=self.sleep)


class Consumer:
    def __init__(self,world,node,generation=1):
        self.world=world;self.node=node;self.generation=generation;self.serial=0;self.index=world.index;self.sequence=world.sequence;self.installed=0
    def call(self,kind,**values):
        w=self.world;self.serial+=1;identity=f'{self.node}-g{self.generation}-{self.serial}'
        call=dict(opId=identity,node=self.node,pid=self.generation*10+int(self.node[-1]),generation=self.generation,
                  kind=kind,startNanos=w.clock(),**values);w.history.append(call)
        if w.problem=='write-failure' and kind=='update' and w.sequence==4:raise OSError('uncertain original write')
        if w.problem=='minimum-failure' and kind=='read' and not values.get('setupToken'):raise OSError('original read failed')
        result=dict(opId=identity,kind=kind,outcome='SUCCESS')
        if kind=='update':w.index+=1;w.sequence+=1;w.advance()
        if kind=='read':
            if values.get('setupToken'):w.index+=1;w.advance()
            else:assert token.decode(base64.b64decode(values['minimum']))['index']<=self.index
            result.update(token=w.minimum(self.index),sequence=self.sequence)
        if kind=='status':result.update(state='LEADER_READY' if self.node==w.leader else 'FOLLOWER',publishedIndex=self.index,sequence=self.sequence,epoch=2)
        if kind=='probe':result['queues']=dict(recoveryFloorObserved=0 if w.problem=='missing-floor' else self.index,
            selectedVotersObserved=3,selectedEpochObserved=3 if w.problem=='stale-selection' else 2,snapshotInstalledIndexObserved=self.installed)
        call.update(endNanos=w.clock(),response=result,outcome='SUCCESS');return result


class MeasurementRecoveryTest(unittest.TestCase):
    def test_m01_m02_and_m03_reject_recovery_controls_before_starting_processes(self):
        from . import measurement_m01 as m01,measurement_minimum as minimum
        for case in ('M01','m02-above-1000','m03-p65'):
            for fault in ('binding','file'):
                with self.subTest(case=case,fault=fault),tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);module=m01 if case=='M01' else minimum
                    plan=m01.profile('candidate-minimum',1) if case=='M01' else minimum.profile(case)
                    parameters=r.options.parameters() if case=='M01' else plan['parameters']
                    binding=dict(mode='candidate-minimum',measurementProfile=plan,readParameters=parameters)
                    if case!='M01':r.runtime.save(root/r.options.FILE,parameters)
                    if fault=='binding':binding['faultParameters']=r.fault_parameters(r.CASES[1])
                    else:r.runtime.save(root/r.FILE,r.fault_parameters(r.CASES[1]))
                    r.runtime.save(root/'binding.json',binding)
                    with patch.object(r.runtime,'execute_observer') as owner,self.assertRaisesRegex(ValueError,'preparation parameters|undeclared fault'):
                        module.execute_prepared(root,binding,'unused')
                    owner.assert_not_called()

    def test_mixed_preparation_profiles_fail_before_creating_workspace(self):
        for args in (dict(mode='candidate-stale'),dict(mode='candidate-minimum',exercise_load=True),
                     dict(mode='candidate-minimum',m01_repetition=1),
                     dict(mode='candidate-minimum',read_profile=r.options.parameters('M02',wait=0))):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)/'unused'
                with self.assertRaisesRegex(ValueError,'recovery preparation profile mismatch'):
                    r.runtime.prepare(root,recovery_case=r.CASES[1],**args)
                self.assertFalse(root.exists())

    def test_retained_restart_keeps_original_carried_token_and_four_unique_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            w=World(r.CASES[0]);result=w.run(directory);s=json.loads((Path(directory)/'scenario.json').read_text())
            self.assertEqual('OBSERVED',result['status']);self.assertFalse(result['qualifiedMeasurement'])
            self.assertEqual(['node-2'],w.killed);self.assertEqual(w.killed,w.restarted);self.assertEqual([],w.partitions)
            self.assertEqual(4,sum(c['kind']=='update' for c in w.history));reads=[c for c in w.history if c['kind']=='read']
            self.assertEqual([model.query(i) for i in range(4)],[c['query'] for c in reads])
            self.assertEqual(['node-2','node-1','node-1','node-2'],[c['node'] for c in reads])
            self.assertEqual([s['carriedToken']]*2,[c['minimum'] for c in reads if 'minimum' in c])
            keys=('killIssuedNanos','exitObservedNanos','readyObservedNanos','writeObservedNanos','strongObservedNanos',
                  'minimumObservedNanos','restartIssuedNanos','restartStartedNanos','restartedReadObservedNanos')
            self.assertEqual(sorted(s[k] for k in keys),[s[k] for k in keys])

    def test_snapshot_requires_actual_install_hint_and_both_old_and_later_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            w=World(r.CASES[1]);w.run(directory);s=json.loads((Path(directory)/'scenario.json').read_text())
            self.assertEqual(['node-3',None],w.partitions);self.assertEqual([],w.killed);self.assertEqual([],w.restarted)
            self.assertEqual('node-3',s['target']);reads=[c for c in w.history if c['kind']=='read']
            self.assertEqual([model.query(i) for i in range(4)],[c['query'] for c in reads]);self.assertEqual(4,sum(c['kind']=='update' for c in w.history))
            self.assertEqual(reads[0]['response']['token'],reads[2]['minimum']);self.assertEqual(reads[1]['response']['token'],reads[3]['minimum'])
            self.assertLess(s['heldStatus']['publishedIndex'],s['installed']['probe']['queues']['snapshotInstalledIndexObserved'])

    def test_stale_selection_missing_floor_incremental_substitution_and_leader_substitution_fail(self):
        for problem,reason in [('stale-selection','selected pair changed'),('missing-floor','baseline floor'),
                               ('incremental-only','snapshot install/publication'),('target-leader','target became leader')]:
            with self.subTest(problem=problem),tempfile.TemporaryDirectory() as directory:
                w=World(r.CASES[1],problem)
                with self.assertRaisesRegex(ValueError,reason):w.run(directory)
                self.assertEqual('FAIL',json.loads((Path(directory)/'controller.json').read_text())['status'])
                self.assertLess(max(sum(c['node']==n for c in w.history) for n in w.workers),4096)

    def test_failed_original_write_or_read_is_not_retried(self):
        for problem,kind,count in [('write-failure','update',4),('minimum-failure','read',3)]:
            for case in r.CASES:
                with self.subTest(problem=problem,case=case),tempfile.TemporaryDirectory() as directory:
                    w=World(case,problem)
                    with self.assertRaisesRegex(OSError,'original'):w.run(directory)
                    self.assertEqual(count,sum(c['kind']==kind for c in w.history))

    def test_closed_profiles_and_atomic_single_voter_partition(self):
        for case in (None,'other','leader-sigkill'):
            with self.assertRaisesRegex(ValueError,'recovery case'):r.profile(case)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for node in ('node-1','node-2','node-3'):
                r.partition(root,node);lines=(root/'network-blocks.txt').read_text().splitlines();self.assertEqual(4,len(set(lines)))
                self.assertTrue(all(node in line.split() and len(set(line.split()))==2 for line in lines));self.assertFalse((root/'network-blocks.pending').exists())
            r.partition(root);self.assertEqual('',(root/'network-blocks.txt').read_text())
            with self.assertRaisesRegex(ValueError,'blocked voter'):r.partition(root,'foreign')

    def test_cleanup_failures_do_not_replace_original_execution_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'artifacts').mkdir();jar=root/'artifacts/runtime.jar';jar.write_bytes(b'fixture');plan=r.profile(r.CASES[1])
            binding=dict(mode='candidate-minimum',measurementProfile=plan,readParameters=r.options.parameters(),faultParameters=plan['faultParameters'],
                         artifacts={'runtime.jar':r.runtime.digest(jar.read_bytes())})
            r.runtime.save(root/'binding.json',binding);r.runtime.save(root/r.FILE,plan['faultParameters']);closed=[]
            class Worker:
                def __init__(self,root,node,cp,mode,history,generation):
                    self.node=node;self.generation=generation;self.proc=type('Proc',(),dict(pid=int(node[-1]),returncode=None))()
                    self.identity=dict(coreSource=str(jar),replicationSource=str(jar),readParameters=r.options.parameters())
                def stop(self):self.proc.returncode=0;closed.append(self.node)
            with patch.object(r,'observe',side_effect=OSError('original failure')),patch.object(r,'partition',side_effect=ValueError('cleanup failure')):
                with self.assertRaisesRegex(OSError,'original failure'):r.execute_prepared(root,binding,'unused',worker_factory=Worker)
            self.assertEqual(['node-1','node-2','node-3'],closed);result=json.loads((root/'execution.json').read_text())
            self.assertEqual('OSError',result['failure']['type']);self.assertEqual('cleanup failure',result['closeErrors'][0]['message'])


if __name__=='__main__':unittest.main()

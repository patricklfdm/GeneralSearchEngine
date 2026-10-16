from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock,patch
from . import remote_history as h,measurement_identity as identity,measurement_recovery_retained as retained
from . import measurement_options as options,measurement_recovery as recovery
from .evidence import encoded


class ReceiverHistoryTest(unittest.TestCase):
    def test_all_33_closed_histories_have_one_exact_member(self):
        plan=h.suite.load()
        for name,spec in plan['histories'].items():
            self.assertEqual(spec,h.specification(name))
            self.assertIn(name,plan['members'][h.member_for(name)]['histories'])
        for name in ('../canonical','candidate-minimum-r4','m02-above-2000',None):
            with self.assertRaisesRegex(ValueError,'undeclared history'):h.specification(name)
        self.assertEqual([180_000_000_000]*15,[v['profile']['durationNanos'] for v in plan['histories'].values() if v['family']=='M01'])

    def test_observers_receive_original_profiles_and_owned_fault_functions(self):
        for name,module in [('candidate-minimum-r2',h.m01),('m02-above-1000',h.minimum),('m03-p65',h.minimum),
                            ('leader-sigkill-retained-restart',h.recovery),('follower-snapshot-carried-token',h.recovery)]:
            with tempfile.TemporaryDirectory() as directory:
                own=h.Receivers(Path(directory)/'run',name,{})
                with patch.object(own,'start') as start,patch.object(module,'observe',return_value='observed') as observe:
                    self.assertEqual('observed',own.observe())
                self.assertEqual(3,start.call_count);args=observe.call_args
                self.assertEqual((own.collected,own.workers,own.history),args.args[:3])
                if module is h.m01:self.assertEqual(('candidate-minimum',2),args.args[3:])
                else:self.assertEqual(name,args.args[3])
                if module is h.recovery:
                    self.assertEqual(own.crash,args.args[4]);self.assertEqual(own.partition,args.kwargs['partition_control'])
                    with patch.object(own,'start') as reopen:args.args[5]('node-2');reopen.assert_called_once_with('node-2',2)

    def test_only_declared_crashed_voter_can_reopen_and_no_duplicate_start(self):
        with tempfile.TemporaryDirectory() as directory:
            own=h.Receivers(Path(directory)/'run','leader-sigkill-retained-restart',{})
            own.roots={'node-1':Path(directory)};own.classpath={'node-1':'test-classpath'};own.prepared=True
            with patch.object(h,'Worker',side_effect=AssertionError('unexpected process')):
                for generation in (0,True,2,3):
                    with self.assertRaisesRegex(ValueError,'generation'):own.start('node-1',generation)
                own.generations['node-1']=1;own.workers['node-1']=object()
                with self.assertRaisesRegex(ValueError,'ownership'):own.start('node-1')
                own.workers.clear()
                with self.assertRaisesRegex(ValueError,'generation'):own.start('node-1',2)
            own.processes=[dict(node='node-1',exitCode=-9)]
            with patch.object(h,'Worker',side_effect=OSError('admitted generation reached launch')):
                with self.assertRaisesRegex(OSError,'admitted generation'):own.start('node-1',2)
            own.name='m03-p4'
            with patch.object(h,'Worker',side_effect=AssertionError('unexpected process')):
                with self.assertRaisesRegex(ValueError,'generation'):own.start('node-1',2)

    def test_distributed_partition_and_failure_cleanup_heal_every_remaining_receiver(self):
        with tempfile.TemporaryDirectory() as directory:
            own=h.Receivers(Path(directory)/'run',recovery.CASES[1],{})
            for node in h.topology.NODES:
                p=own.root/node;p.mkdir();own.roots[node]=p
            own.partition('node-2')
            for p in (*own.roots.values(),own.collected):self.assertEqual(4,len((p/'network-blocks.txt').read_text().splitlines()))
            original=recovery.partition;calls=[]
            def heal(root,node=None):
                calls.append(root)
                if root==own.roots['node-1']:raise OSError('one receiver lost')
                original(root,node)
            failure=dict(type='ValueError',message='original execution failure')
            with patch.object(h.recovery,'partition',side_effect=heal):own.finish(failure)
            self.assertEqual([*own.roots.values(),own.collected],calls)
            for p in (own.roots['node-2'],own.roots['node-3'],own.collected):self.assertEqual(b'',(p/'network-blocks.txt').read_bytes())
            result=json.loads((own.collected/'execution.json').read_text())
            self.assertEqual('FAIL',result['status']);self.assertEqual(failure,result['failure'])
            self.assertEqual('one receiver lost',result['closeErrors'][0]['message'])

    def test_partial_preparation_closes_ports_and_retains_failure_without_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            own=h.Receivers(Path(directory)/'run','candidate-minimum-r1',{})
            sock=Mock();own.sockets.append(sock)
            def fail():raise OSError('partial preparation')
            with patch.object(h,'Receivers',return_value=own),patch.object(own,'prepare',side_effect=fail),patch.object(own,'observe') as observe:
                with self.assertRaisesRegex(OSError,'partial preparation'):h.run(own.root,own.name,{})
            observe.assert_not_called();sock.close.assert_called_once()
            result=json.loads((own.collected/'execution.json').read_text());self.assertEqual('FAIL',result['status'])
            self.assertEqual('partial preparation',result['failure']['message'])
            with self.assertRaisesRegex(ValueError,'already finished'):own.finish(None)

    def test_original_execution_failure_survives_close_error_and_other_workers_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            own=h.Receivers(Path(directory)/'run','m03-p4',{})
            workers=[]
            for n in (1,2):
                worker=Mock(node=f'node-{n}',generation=1,identity={});worker.proc.pid=n;worker.proc.returncode=0
                workers.append(worker);own.workers[worker.node]=worker
            workers[0].stop.side_effect=OSError('close failure')
            with patch.object(h,'Receivers',return_value=own),patch.object(own,'prepare'),patch.object(h,'source',return_value={}),\
                 patch.object(own,'observe',side_effect=ValueError('original call failed')):
                with self.assertRaisesRegex(ValueError,'original call failed'):h.run(own.root,own.name,{})
            for worker in workers:worker.stop.assert_called_once()
            receipt=json.loads((own.collected/'execution.json').read_text())
            self.assertEqual('original call failed',receipt['failure']['message']);self.assertEqual('close failure',receipt['closeErrors'][0]['message'])

    def test_changed_source_before_execution_cannot_offer_a_history(self):
        with tempfile.TemporaryDirectory() as directory:
            own=h.Receivers(Path(directory)/'run','m03-p4',{})
            with patch.object(h,'Receivers',return_value=own),patch.object(own,'prepare'),patch.object(h,'source',return_value={'changed':True}),\
                 patch.object(own,'observe') as observe:
                with self.assertRaisesRegex(ValueError,'before execution'):h.run(own.root,own.name,{})
            observe.assert_not_called()

    def test_partial_remote_identity_never_falls_back_to_single_origin(self):
        for binding in ({'origin':'/local','remoteReceivers':{}},{'origin':'/local','remoteTopology':{}}):
            with self.assertRaisesRegex(ValueError,'binding fields'):identity.original_root(binding,'node-1')
            with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(ValueError,'binding fields'):
                identity.evidence_location(Path(directory),binding)
        self.assertEqual(Path('/local'),identity.original_root({'origin':'/local'},'node-1'))
        binding=dict(origin='/collected',remoteTopology={},remoteReceivers={'node-1':dict(originalRoot='/receiver-1')})
        self.assertEqual(Path('/receiver-1'),identity.original_root(binding,'node-1'))

    def test_retained_restart_inspects_the_original_receiver_seal_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);before=root/'pre-reopen/node-2';before.mkdir(parents=True);(before/'sentinel').write_bytes(b'original')
            scenario=dict(leader='node-2',crash=dict(preReopen=h.bundle.members(before)))
            binding=dict(origin='/collected',remoteTopology={},remoteReceivers={'node-2':dict(originalRoot='/actual/receiver')})
            with patch.object(retained.storage,'_inspect',side_effect=ValueError('stop at physical inspection')) as inspect:
                with self.assertRaisesRegex(ValueError,'physical inspection'):retained.validate(root,binding,scenario,{},None,None,None)
            self.assertEqual(Path('/actual/receiver/node-2'),inspect.call_args.args[-1])

    def test_whole_formal_counts_include_failed_original_outcomes(self):
        result=dict(ledger=dict(outcomes=dict(read={'SUCCESS':2,'TIMEOUT':1},update={'INDETERMINATE':2})))
        self.assertEqual((3,2),h.original_counts(result,{'family':'M01'}))


if __name__=='__main__':unittest.main()

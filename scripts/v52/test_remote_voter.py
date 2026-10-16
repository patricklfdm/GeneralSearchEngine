from concurrent.futures import Future
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from . import remote_voter as v,remote_voter_evidence as e,remote_voter_qualification as q


def request(n=1):return dict(opId=f'node-1-g1-{n}',kind='status')
def response(n=1):return dict(request(n),outcome='SUCCESS',receivedNanos=2,apiStartNanos=3,apiEndNanos=4)


class FakeWorker:
    node='node-1'
    def __init__(self):self.calls=[];self.futures=[];self.proc=SimpleNamespace(returncode=None)
    def submit(self,kind,**values):
        self.calls.append(dict(kind=kind,**values));future=Future();self.futures.append(future)
        return f'node-1-g1-{len(self.calls)}',future
    def stop(self):self.proc.returncode=0


class VoterServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.worker=FakeWorker();self.engine=v.Engine(self.worker,self.root,'a'*64,{'original':'identity'})
    def tearDown(self):self.engine.journal.close();self.temp.cleanup()

    def test_completed_reply_retained_once_and_duplicate_or_changed_payload_never_dispatched(self):
        self.engine.submit(request());self.worker.futures[0].set_result(response())
        for value in (request(),dict(request(),kind='probe')):
            with self.assertRaisesRegex(ValueError,'consumed/out-of-order'):self.engine.submit(value)
        self.assertEqual(1,len(self.worker.calls));self.assertEqual(['SUBMIT','RESULT'],[r['kind'] for r in self.engine.events])
        self.assertEqual(response(),self.engine.events[1]['response'])

    def test_pending_reply_never_reissued_and_next_sequence_still_works(self):
        self.engine.submit(request())
        with self.assertRaisesRegex(ValueError,'consumed/out-of-order'):self.engine.submit(request())
        self.engine.submit(request(2));self.worker.futures[1].set_result(response(2));self.worker.futures[0].set_result(response())
        self.assertEqual([request(2)['opId'],request()['opId']],[r['response']['opId'] for r in self.engine.events if r['kind']=='RESULT'])

    def test_unknown_fields_and_oversize_fail_before_api(self):
        for value in (dict(request(),argv=['sh']),dict(request(),pid=20),dict(request(),kind='undeclared')):
            with self.assertRaises(ValueError):self.engine.submit(value)
        with self.assertRaisesRegex(ValueError,'public request bound'):
            self.engine.submit(dict(request(),kind='read',query={'huge':'x'*16384}))
        self.assertEqual([],self.worker.calls)

    def test_pending_call_and_total_journal_bounds_precede_api(self):
        with patch.object(v,'MAX_PENDING',1):
            self.engine.submit(request())
            with self.assertRaisesRegex(ValueError,'operation bound'):self.engine.submit(request(2))
        self.worker.futures[0].set_result(response())
        with patch.object(v,'MAX_BYTES',self.engine.bytes+v.FRAME):
            with self.assertRaisesRegex(ValueError,'admission bound'):self.engine.submit(request(2))
        with patch.object(v,'MAX_CALLS',1):
            with self.assertRaisesRegex(ValueError,'operation bound'):self.engine.submit(request(2))
        self.assertEqual(1,len(self.worker.calls))

    def test_dispatch_exception_consumes_original_identity_and_rejects_further_operations(self):
        with patch.object(self.worker,'submit',side_effect=OSError('pipe interrupted')):
            with self.assertRaises(OSError):self.engine.submit(request())
        self.assertEqual('DISPATCH_UNCERTAIN',self.engine.failure)
        for value in (request(),request(2)):
            with self.assertRaisesRegex(ValueError,'stopping/failed'):self.engine.submit(value)
        self.assertEqual(1,len(self.engine.events))

    def test_journal_write_failure_cannot_dispatch_public_operation(self):
        with patch.object(self.engine,'event',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.engine.submit(request())
        self.assertEqual([],self.worker.calls)

    def test_pipe_submit_never_holds_the_callback_journal_lock(self):
        original=self.worker.submit
        def submit(*args,**kwargs):
            acquired=threading.Event()
            def callback():
                with self.engine.condition:acquired.set()
            thread=threading.Thread(target=callback,daemon=True);thread.start()
            try:self.assertTrue(acquired.wait(1),'pipe submit holds callback lock')
            finally:thread.join(.05)
            return original(*args,**kwargs)
        with patch.object(self.worker,'submit',side_effect=submit):self.engine.submit(request())
        self.worker.futures[0].set_result(response())

    def test_missing_response_cannot_become_successful_shutdown(self):
        self.engine.submit(request());self.worker.futures[0].set_result(None);self.engine.close()
        self.assertIsNotNone(v.c.read(self.root/'stopped.json')['failure'])
        self.assertEqual('STOPPED',self.engine.events[-1]['kind'])

    def test_shutdown_is_idempotent_and_binds_forced_journal(self):
        self.engine.submit(request());self.worker.futures[0].set_result(response());self.engine.close()
        original=(self.root/'stopped.json').read_bytes();self.engine.close()
        self.assertEqual(original,(self.root/'stopped.json').read_bytes())
        receipt=json.loads(original);self.assertIsNone(receipt['failure'])
        self.assertEqual(v.h.bundle.sha_file(self.root/'events.jsonl'),receipt['journalSha256'])
        with self.assertRaisesRegex(ValueError,'stopping/failed'):self.engine.submit(request(2))

    def test_close_failure_retains_original_ledger(self):
        self.engine.submit(request());self.worker.futures[0].set_result(response())
        with patch.object(self.worker,'stop',side_effect=OSError('close failed')):self.engine.close()
        self.assertIn('close failed',v.c.read(self.root/'stopped.json')['failure'])
        self.assertEqual(response(),self.engine.events[1]['response'])

    def test_started_or_partial_launch_claim_cannot_spawn_again(self):
        # Actual atomic helper, including its crash-left .writing file.
        for name in ('started.json','started.json.writing'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);(root/name).write_text('{}')
                with patch.object(v.c,'read',side_effect=[{},dict(configSha256=v.digest(v.encoded({})))]),\
                     patch.object(v,'validate_config',return_value=root),patch.object(v.h,'Worker') as worker:
                    with self.assertRaises(FileExistsError):v.serve(root)
                worker.assert_not_called()

    def test_socket_protocol_is_bounded_strict_json_not_pickle_or_partial_lines(self):
        self.assertEqual(request(),v.receive(io.BytesIO(v.encoded(request())+b'\n')))
        for data in (b'{}',b'[]\n',b'{"a":1,"a":2}\n',b'x'*(v.FRAME+1)):
            with self.assertRaises(ValueError):v.receive(io.BytesIO(data))
        self.assertIsNone(v.receive(io.BytesIO()))
        channel=Mock()
        with self.assertRaisesRegex(ValueError,'frame bound'):v.send(channel,{'big':'x'*v.FRAME})
        channel.sendall.assert_not_called()

    def test_service_scope_rejects_private_topology_and_formal_windows(self):
        value=dict(schema=v.SCHEMA,execution='local-persistent-voters-only',node='node-1',root=str(self.root),
                   host={},binding={'mode':'candidate-minimum','driverExercise':True,'remoteVoterControl':'local-persistent-voters-v1',
                                    'remoteTopology':{'placement':'owned-private-hosts'}},
                   socket=str(self.root/'channel'),session='a'*32)
        with patch.object(v.host,'observe',return_value={}):
            with self.assertRaisesRegex(ValueError,'local topology'):v.validate_config(value,self.root/'node-1-control')
            value['binding']['measurementProfile']={}
            with self.assertRaisesRegex(ValueError,'only untimed'):v.validate_config(value,self.root/'node-1-control')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'whole smoke only'):q.Receivers(Path(directory)/'run','candidate-minimum-r1',{})


class ClockEdgesTest(unittest.TestCase):
    def fixture(self):
        call=dict(request(),node='node-1',pid=123,generation=1,startNanos=9_000_000_000,endNanos=9_000_000_001,
                  outcome='SUCCESS',response=response())
        events=[dict(seq=1,kind='SUBMIT',localNanos=100,request=request()),
                dict(seq=2,kind='RESULT',localNanos=101,response=response()),
                dict(seq=3,kind='STOPPED',localNanos=102,exitCode=0,failure=None)]
        return events,[call]

    def test_independent_clock_offsets_need_message_edges_not_global_timestamp_sort(self):
        events,calls=self.fixture();self.assertEqual({'operations':1,'messageEdges':2},e.edges(events,calls,'node-1'))
        for row in events:row['localNanos']+=10**15
        self.assertEqual({'operations':1,'messageEdges':2},e.edges(events,calls,'node-1'))

    def test_reject_clock_regression_in_each_own_domain(self):
        changes=[lambda rows,calls:rows[1].update(localNanos=99),
                 lambda rows,calls:calls[0].update(endNanos=calls[0]['startNanos']),
                 lambda rows,calls:(calls[0]['response'].update(apiEndNanos=1),rows[1]['response'].update(apiEndNanos=1))]
        for change in changes:
            rows,calls=self.fixture();change(rows,calls)
            with self.assertRaisesRegex(ValueError,'clock order'):e.edges(rows,calls,'node-1')

    def test_reject_missing_duplicate_reordered_and_foreign_edges(self):
        rows,calls=self.fixture()
        for wrong in (rows[1:],rows[:1]+rows,rows[::-1],rows[:-1]):
            with self.assertRaises(ValueError):e.edges(deepcopy(wrong),calls,'node-1')
        with self.assertRaises(ValueError):e.edges(rows,calls,'node-2')
        with self.assertRaises(ValueError):e.edges(rows,calls+calls,'node-1')

    def test_reject_altered_original_requests_responses_and_failed_stop(self):
        changes=[lambda rows:rows[0]['request'].update(kind='probe'),
                 lambda rows:rows[1]['response'].update(outcome='REJECTED'),
                 lambda rows:rows[2].update(exitCode=-9),lambda rows:rows[2].update(failure='incomplete'),
                 lambda rows:rows[1].update(extra='unbound')]
        for change in changes:
            rows,calls=self.fixture();change(rows)
            with self.assertRaises(ValueError):e.edges(rows,calls,'node-1')

    def test_accept_original_non_success_response_without_fabricating_success(self):
        rows,calls=self.fixture()
        result=dict(response(),outcome='NOT_APPLICABLE',reasonCode='QUORUM_UNAVAILABLE')
        rows[1]['response']=result;calls[0].update(response=result,outcome=result['outcome'])
        self.assertEqual(1,e.edges(rows,calls,'node-1')['operations'])




class RetainedVoterTest(unittest.TestCase):
    def write(self,path,value):path.write_bytes(v.encoded(value)+b'\n')
    def fixture(self,root):
        boot='a5fd609f-a0db-4143-98a7-77beab61bb4e'
        binding=dict(remoteTopology={'placement':'local-no-gcp'},remoteVoterControl='local-persistent-voters-v1',
                     remoteReceivers={n:dict(originalRoot='/original/'+n) for n in v.h.topology.NODES})
        self.write(root/'binding.json',binding)
        self.write(root/'controller-domain.json',dict(clock='python-monotonic-ns',process=dict(bootId=boot,pid=1,startTicks=1),session='c'*32))
        processes=[];history=[]
        for i,node in enumerate(v.h.topology.NODES):
            control=root/(node+'-control');control.mkdir()
            pin=dict(bootId=boot,uid=1000,parentDevice=1,parentInode=i+1)
            config=dict(schema=v.SCHEMA,execution='local-persistent-voters-only',node=node,root='/original/'+node,
                        host=pin,binding=binding,socket='/private/channel',session=str(i)*32)
            sha=v.digest(v.encoded(config));consumer=dict(node=node,pid=11+i*2)
            identity=dict(service=dict(bootId=boot,pid=10+i*2,startTicks=2),jvm=dict(bootId=boot,pid=11+i*2,startTicks=3),
                          consumer=consumer,host=pin,session=config['session'])
            self.write(control/'config.json',config);self.write(control/'identity.json',identity)
            self.write(control/'launch.json',dict(configSha256=sha))
            self.write(control/'started.json',dict(configSha256=sha,service=identity['service']))
            processes.append(dict(node=node,generation=1,pid=consumer['pid'],exitCode=0,identity=consumer))
            rows,calls=ClockEdgesTest().fixture()
            for row in rows:
                for key in ('request','response'):
                    if key in row:row[key]['opId']=node+'-g1-1'
            calls[0].update(opId=node+'-g1-1',node=node,pid=consumer['pid'])
            calls[0]['response']['opId']=node+'-g1-1';history+=calls
            (control/'events.jsonl').write_bytes(b''.join(v.encoded(row)+b'\n' for row in rows))
            self.write(control/'stopped.json',dict(schema=v.SCHEMA,configSha256=sha,identity=identity,lastSequence=3,
                journalSha256=v.h.bundle.sha_file(control/'events.jsonl'),exitCode=0,failure=None))
        self.write(root/'history.json',history);self.write(root/'processes.json',processes)
        self.index(root);return binding

    def index(self,root):self.write(root/v.h.bundle.INDEX,v.h.bundle.members(root))

    def test_retained_identity_and_edges_replay_after_relocation(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'original';root.mkdir();binding=self.fixture(root)
            expected=e.validate(root,binding);relocated=Path(directory)/'relocated';shutil.copytree(root,relocated)
            self.assertEqual(expected,e.validate(relocated,binding))
            self.assertEqual(3,sum(n['operations'] for n in expected['nodes'].values()))

    def test_reject_retained_identity_corruption_even_with_refreshed_inventory(self):
        mutations=[
            ('node-1-control/config.json',lambda x:x.update(node='node-2'),'config binding'),
            ('node-1-control/launch.json',lambda x:x.update(configSha256='0'*64),'retained launch'),
            ('node-1-control/started.json',lambda x:x['service'].update(startTicks=999),'retained start'),
            ('node-1-control/identity.json',lambda x:x.update(session='f'*32),'retained identity'),
            ('node-1-control/stopped.json',lambda x:x.update(lastSequence=100),'terminal binding'),
            ('node-1-control/stopped.json',lambda x:x.update(failure='failed'),'terminal binding'),
            ('node-1-control/stopped.json',lambda x:x.update(journalSha256='0'*64),'terminal binding'),
            ('controller-domain.json',lambda x:x['process'].update(bootId='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),'local-only boot'),
            ('controller-domain.json',lambda x:x.update(clock='wall-clock'),'controller domain'),
            ('processes.json',lambda x:x[0].update(pid=99),'physical binding'),
            ('history.json',lambda x:x[0]['response'].update(outcome='NOT_APPLICABLE'),'original response changed'),
            ('history.json',lambda x:x[0].update(pid=99),'controller process binding'),
        ]
        for name,change,reason in mutations:
            with self.subTest(name=name,reason=reason),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);binding=self.fixture(root);e.validate(root,binding)
                path=root/name;value=v.c.read(path);change(value);self.write(path,value);self.index(root)
                with self.assertRaisesRegex(ValueError,reason):e.validate(root,binding)

    def test_missing_service_evidence_and_downgrade_do_not_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);binding=self.fixture(root)
            path=root/'node-1-control/identity.json';path.unlink();self.index(root)
            with self.assertRaises(FileNotFoundError):e.validate(root,binding)
            binding.pop('remoteVoterControl')
            with self.assertRaisesRegex(ValueError,'control binding'):e.validate(root,binding)

    def test_inventory_detects_unbound_edits_before_edge_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);binding=self.fixture(root)
            (root/'node-1-control/events.jsonl').write_bytes(b'{}\n')
            with self.assertRaisesRegex(ValueError,'inventory/hash'):e.validate(root,binding)


if __name__=='__main__':unittest.main()

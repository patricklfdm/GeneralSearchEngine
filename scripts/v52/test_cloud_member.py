"""Whole-member orchestration models, not provider or workload acceptance."""
from concurrent.futures import Future
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from . import cloud_member as m,cloud_native_runner as native,cloud_staging as staging
from . import remote_restart as restart,remote_voter as voter
from . import remote_voter_lifecycle_qualification as lifecycle,remote_formal_qualification as formal
from . import remote_restart_qualification as restart_owner,remote_history as history


class MemberTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        # These concrete-type objects only exercise orchestration boundaries. The
        # real native admission/resource factories have separate integration tests.
        self.session=object.__new__(native.Session);self.session.api=object.__new__(native.NativeRunnerApi)
        self.session.staged=object.__new__(staging.Staged);self.session.staged.files={};self.proof={'source':{'source':'a'*40}}
        self.session.api.admission=SimpleNamespace(proof=self.proof);self.session.staged.check=Mock(return_value=self.proof)
        self.session.member_lock=threading.Lock()
        self.session.java=dict(descriptor={'fixture':'java'},archive='original-java');self.session.member_started=False
        self.selection=dict(member=dict(name='experiment',histories=['first','second'],reads=22,updates=6))
        self.session.owner=SimpleNamespace(request=dict(selection=self.selection))
        self.session.checkpoint=Mock(return_value={'originalClaim':True})
        self.guests=Mock();self.storage=Mock();self.storage.java={'installations':{}}
        self.guests.prepare_storage.return_value=self.storage;self.session.open_guests=Mock(return_value=self.guests)
        self.rows=[];self.failure=None
        self.valid=patch.object(m.suite,'validate_selection');self.valid.start();self.addCleanup(self.valid.stop)
        self.run=patch.object(m.history,'run',side_effect=self.execute).start();self.addCleanup(patch.stopall)
        patch.object(m,'correlate',side_effect=lambda root,result,name,*args:dict(history=name,reads=11,updates=3)).start()
    def execute(self,root,name,expected,**kwargs):
        self.rows.append(name);Path(root).mkdir()
        if self.failure==name:raise ValueError('original work failed')
        return {'original':'modeled history'}
    def test_complete_selected_member_once_and_no_cloud_qualification(self):
        answer=m.run(self.session,'key',self.root/'run')
        self.assertEqual('MEMBER_EXECUTED_NOT_QUALIFIED',answer['status']);self.assertFalse(answer['fullRemoteQualification'])
        self.assertEqual(['first','second'],self.rows);self.guests.close.assert_called_once()
        self.storage.install_java.assert_called_once_with(self.guests,{'fixture':'java'},'original-java')
        with self.assertRaisesRegex(ValueError,'already consumed'):m.run(self.session,'key',self.root/'retry')
        self.assertFalse((self.root/'retry').exists());self.assertEqual(2,self.run.call_count)
    def test_concurrent_entries_cannot_both_consume_the_original_member(self):
        from concurrent.futures import ThreadPoolExecutor
        entered=threading.Event();release=threading.Event();second=threading.Event();original=Path.mkdir
        paths=[self.root/'first-entry',self.root/'second-entry']
        class ClaimLock:
            def __init__(self):self.lock=threading.Lock();self.count=0;self.count_lock=threading.Lock()
            def __enter__(self):
                with self.count_lock:
                    self.count+=1
                    if self.count==2:second.set()
                self.lock.acquire()
            def __exit__(self,*args):self.lock.release()
        self.session.member_lock=ClaimLock()
        def mkdir(path,*args,**kwargs):
            if path==paths[0]:entered.set();self.assertTrue(release.wait(5))
            if path==paths[1]:second.set()
            return original(path,*args,**kwargs)
        def run_second():
            return m.run(self.session,'key',paths[1])
        with patch.object(Path,'mkdir',new=mkdir),ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(m.run,self.session,'key',paths[0])
            try:
                self.assertTrue(entered.wait(5));other=pool.submit(run_second);self.assertTrue(second.wait(5))
            finally:release.set()
            self.assertEqual('MEMBER_EXECUTED_NOT_QUALIFIED',first.result(timeout=5)['status'])
            with self.assertRaisesRegex(ValueError,'already consumed'):other.result(timeout=5)
        self.assertFalse(paths[1].exists());self.assertEqual(['first','second'],self.rows)
    def test_original_failure_stops_later_histories_and_remains_after_cleanup_failure(self):
        self.failure='first';self.guests.close.side_effect=OSError('cleanup failed')
        with self.assertRaisesRegex(ValueError,'original work failed'):m.run(self.session,'key',self.root/'run')
        self.assertEqual(['first'],self.rows);self.guests.close.assert_called_once()
        receipt=m.native.strict((self.root/'run/receipt.json').read_bytes())
        self.assertEqual('FAIL',receipt['status']);self.assertEqual('OSError',receipt['guestCloseFailure'])
        with self.assertRaisesRegex(ValueError,'already consumed'):m.run(self.session,'key',self.root/'retry')
    def test_java_failure_prevents_every_history_and_closes_original_guest_scope(self):
        self.storage.install_java.side_effect=ValueError('partial Java')
        with self.assertRaisesRegex(ValueError,'partial Java'):m.run(self.session,'key',self.root/'run')
        self.run.assert_not_called();self.guests.close.assert_called_once()
    def test_mid_member_input_drift_cannot_continue(self):
        calls=0
        def check():
            nonlocal calls
            calls+=1
            if calls==3:raise ValueError('original input changed')
            return self.proof
        self.session.staged.check.side_effect=check
        with self.assertRaisesRegex(ValueError,'input changed'):m.run(self.session,'key',self.root/'run')
        self.assertEqual(['first'],self.rows);self.assertTrue((self.root/'run/first/result.json').is_file())
    def test_resource_only_session_cannot_start_work(self):
        self.session.staged=None
        with self.assertRaisesRegex(ValueError,'native preparation'):m.run(self.session,'key',self.root/'run')
        self.assertFalse((self.root/'run').exists());self.run.assert_not_called()
    def test_missing_final_history_or_counts_cannot_complete(self):
        self.selection['member']['reads']=100
        with self.assertRaisesRegex(ValueError,'counts incomplete'):m.run(self.session,'key',self.root/'run')
        self.assertEqual('FAIL',m.native.strict((self.root/'run/receipt.json').read_bytes())['status'])
    def test_close_failure_after_all_histories_cannot_be_success(self):
        self.guests.close.side_effect=OSError('close failed')
        with self.assertRaisesRegex(OSError,'close failed'):m.run(self.session,'key',self.root/'run')
        self.assertEqual('FAIL',m.native.strict((self.root/'run/receipt.json').read_bytes())['status'])


class CorrelationTest(unittest.TestCase):
    def setUp(self):
        from .test_remote_bound_receivers import fixture,transport
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)/'history';self.root.mkdir()
        self.name='candidate-minimum-untimed-smoke';self.source=dict(source='a'*40,checkoutSha256='b'*64)
        self.binding=transport(fixture());self.placement=SimpleNamespace(binding=deepcopy(self.binding))
        self.binding.update(remoteVoterControl=m.domains.EXECUTIONS['local-persistent-voters-v1'],
            remoteVoterLifecycle=m.domains.EXECUTIONS['loopback-ssh-voter-lifecycle-only'],remoteDelivery={},remotePython={})
        self.java=dict(descriptor={'original':'Java'},installations={'three':'hosts'})
        self.binding['remoteJava']=dict(nodes=self.java['installations'],descriptorSha256=m.digest(m.encoded(self.java['descriptor'])))
        self.files={n:('original-'+n).encode() for n in staging.paths()}
        names={'general-search-engine-5.2.0-SNAPSHOT.jar','general-search-engine-replication-5.2.0-SNAPSHOT.jar','general-search-engine-4.4.0.jar'}
        self.binding['artifacts']={Path(n).name:m.digest(raw) for n,raw in self.files.items() if Path(n).name in names}
        raw=b'original archive';(self.root/'history.tar.gz').write_bytes(raw)
        self.result=dict(status='PASS',history=self.name,family='UNTIMED',mode='candidate-minimum',binding=self.binding,
            paidCloud=False,qualifiedMeasurement=False,fullRemoteQualification=False,archiveSha256=m.digest(raw),originalReads=11,originalUpdates=3)
    def check(self):return m.correlate(self.root,self.result,self.name,self.placement,self.source,self.java,self.files)
    def test_original_binding_and_archive_correlate_without_promoting_pass(self):
        self.assertEqual(11,self.check()['reads']);self.assertFalse(self.result['fullRemoteQualification'])
    def test_other_source_host_artifact_or_java_cannot_substitute_original(self):
        original=deepcopy(self.result)
        mutations=[lambda r:r['binding'].update(source='f'*40),
            lambda r:r['binding']['remoteHostDomains'].update(leaseSha256='f'*64),
            lambda r:r['binding']['artifacts'].update({'general-search-engine-5.2.0-SNAPSHOT.jar':'f'*64}),
            lambda r:r['binding']['remoteJava'].update(descriptorSha256='f'*64),
            lambda r:r.update(qualifiedMeasurement=True)]
        for mutate in mutations:
            self.result=deepcopy(original);mutate(self.result)
            with self.assertRaises(ValueError):self.check()
    def test_copied_result_cannot_hide_missing_or_changed_archive(self):
        (self.root/'history.tar.gz').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'archive changed'):self.check()


class ProgressTest(unittest.TestCase):
    def test_long_stage_emits_heartbeat_until_closed(self):
        event=threading.Event();rows=[]
        def emit(row):
            rows.append(row)
            if len(rows)>=2:event.set()
        progress=m.Progress('experiment',emit=emit,interval=.01)
        try:
            progress.update('physical-replay',name='first');progress.thread.start()
            self.assertTrue(event.wait(2))
        finally:progress.close()
        self.assertFalse(progress.thread.is_alive());self.assertEqual('physical-replay',rows[-1]['stage'])
        self.assertEqual('first',rows[-1]['history']);self.assertEqual(0,rows[-1]['completed'])


class NativeTransportTest(unittest.TestCase):
    def test_bound_lifecycle_and_formal_launches_never_inject_lost_results(self):
        for cls in (lifecycle.Receivers,formal.Receivers):
            owner=object.__new__(cls);owner.qualify_transport=False;owner.binding={};owner.clients=[];owner.targets={'node-1':{}}
            owner.python_context=Mock(return_value={})
            with patch.object(lifecycle.lifecycle,'Client') as normal,patch.object(lifecycle,'LostResultClient') as loss:
                owner.start_service('/guest','node-1','cp','mode',[],1)
                loss.assert_not_called();normal.assert_called_once();self.assertFalse(normal.call_args.kwargs['discard_launch'])
    def test_normal_crash_terminal_is_not_dropped_or_replayed(self):
        self.crash(lost=False)
    def test_spontaneously_lost_terminal_queries_original_only(self):
        self.crash(lost=True)
    def crash(self,*,lost):
        obj=object.__new__(restart.Client);obj.generation=1;obj.pending={};obj.crash_submissions=0;obj.final=None
        obj.sha='a'*64;obj.owner_identity={'original':True};obj.channel=Mock();obj.reader=Mock();obj.disconnect=Mock()
        obj.lock=threading.RLock();obj.proc=SimpleNamespace(returncode=None);obj.terminal=Future();obj.events=[];obj.cursor=0
        obj.discard_terminal=False;obj.terminal_lost=False;obj.terminal_query=None;obj.close_transport=Mock();obj.recorded=[{}]
        event=dict(seq=1,kind='STOPPED',exitCode=-9,failure=None)
        answer=dict(crash=dict(configSha256=obj.sha,identity=obj.owner_identity,generation=1,exitCode=-9),event=event)
        obj.control_call=Mock(side_effect=[{'state':'CRASHED'},answer]);obj.await_state=Mock(return_value={'identity':obj.owner_identity})
        if not lost:obj.receive_event(event)
        with patch.object(voter,'send') as send:
            self.assertEqual(answer,obj.crash());send.assert_called_once_with(obj.channel,{'crash':True})
        self.assertEqual([event],obj.events);self.assertEqual(lost,obj.terminal_lost)
        self.assertEqual(lost,obj.terminal_query is not None);self.assertEqual(1,obj.cursor)
        if not lost:self.assertTrue(obj.recorded[0]['terminal'])
        with self.assertRaisesRegex(ValueError,'already consumed'):obj.crash()


if __name__=='__main__':unittest.main()

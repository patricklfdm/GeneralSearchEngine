from copy import deepcopy
from pathlib import Path
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from . import remote_voter as v,remote_voter_scope as scope,remote_restart_guest as guest
from . import remote_restart as client,remote_voter_evidence as evidence,remote_voter_ssh_evidence as ssh
from . import remote_voter_lifecycle_evidence as lifecycle,remote_voter_guest as service
from . import test_remote_voter as fixtures


def binding():
    return dict(remoteRestart=scope.RESTART_EXECUTION,measurementProfile=scope.partition.recovery.profile(scope.RESTART_CASE),
        faultParameters=scope.partition.recovery.profile(scope.RESTART_CASE)['faultParameters'],
        mode='candidate-minimum',readParameters=scope.partition.options.parameters(),programSha256=scope.partition.model.PLAN_SHA)


class ScopeTest(unittest.TestCase):
    def test_explicit_generation_requires_exact_retained_restart(self):
        good=dict(binding=binding(),generation=2)
        self.assertEqual(2,scope.generation(good));self.assertEqual(1,scope.generation({}))
        for gen in (True,0,3,'2'):
            with self.assertRaises(ValueError):scope.generation(dict(good,generation=gen))
        for mutate in (lambda r:r['binding'].pop('remoteRestart'),
                       lambda r:r['binding']['measurementProfile'].update(recoverySeconds=999),
                       lambda r:r['binding'].update(driverExercise=True),
                       lambda r:r['binding'].update(mode='candidate-local')):
            bad=deepcopy(good);mutate(bad)
            with self.assertRaises(ValueError):scope.generation(bad)

    def test_second_generation_ids_cannot_be_mixed_with_original_calls(self):
        rows,calls=fixtures.ClockEdgesTest().fixture()
        for row in rows:
            for key in ('request','response'):
                if key in row:row[key]['opId']='node-1-g2-1'
        calls[0].update(opId='node-1-g2-1',generation=2);calls[0]['response']['opId']='node-1-g2-1'
        self.assertEqual(1,evidence.edges(rows,calls,'node-1',generation=2)['operations'])
        with self.assertRaises(ValueError):evidence.edges(rows,calls,'node-1')
        rows[-1]['exitCode']=-9
        with self.assertRaises(ValueError):evidence.edges(rows,calls,'node-1',generation=2)


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.node='node-1';self.control=self.root/(self.node+'-control');self.control.mkdir(mode=0o700)
        self.authority=self.root/self.node;self.authority.mkdir(mode=0o700);(self.authority/'authority').write_bytes(b'retained authority')
        self.config=dict(root=str(self.root),node=self.node,generation=1,binding=binding(),host=v.host.observe(self.control))
        self.sha=v.digest(v.encoded(self.config));self.identity=dict(service=v.process(os.getpid()),jvm=v.process(os.getpid()))
        self.worker=SimpleNamespace(root=self.root,node=self.node,generation=1,proc=SimpleNamespace(returncode=-9),reader=Mock())
        self.worker.reader.is_alive.return_value=False
        v.c.write_once(self.control/'config.json',self.config);v.c.write_once(self.control/'identity.json',self.identity)
        v.c.write_once(self.control/'crash-request.json',dict(configSha256=self.sha,identity=self.identity))
    def capture(self):return guest.capture(self.worker,self.control,self.sha,self.identity)

    def test_capture_is_exact_and_duplicate_capture_never_overwrites(self):
        original=guest.inventory(self.authority);receipt=self.capture()
        self.assertEqual(original,receipt['preReopen']);self.assertEqual(receipt,guest.crash_receipt(self.root,self.config,self.sha))
        with self.assertRaises(FileExistsError):self.capture()
        self.assertEqual(receipt,guest.crash_receipt(self.root,self.config,self.sha))

    def test_partial_or_live_generation_cannot_publish_crash(self):
        for changes in ({'generation':2},{'proc':SimpleNamespace(returncode=0)},{'reader':Mock(is_alive=lambda:True)}):
            worker=SimpleNamespace(**dict(vars(self.worker),**changes))
            with self.assertRaisesRegex(ValueError,'original SIGKILL'):guest.capture(worker,self.control,self.sha,self.identity)
        self.assertFalse((self.control/'crash.json').exists())

    def test_link_and_oversized_file_reject_before_copy(self):
        linked=self.authority/'linked';linked.symlink_to(self.authority/'authority')
        with self.assertRaisesRegex(ValueError,'symlink'):self.capture()
        linked.unlink();os.link(self.authority/'authority',linked)
        with self.assertRaisesRegex(ValueError,'file type'):self.capture()
        linked.unlink()
        with (self.authority/'large').open('wb') as stream:stream.truncate((8<<20)+1)
        with self.assertRaisesRegex(ValueError,'bound'):self.capture()

    def test_changed_snapshot_and_claim_rejected(self):
        self.capture();snapshot=self.root/(self.node+'-pre-reopen')/'authority';snapshot.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'retained bytes changed'):guest.crash_receipt(self.root,self.config,self.sha)
        snapshot.write_bytes(b'retained authority');(self.control/'crash-request.json').unlink()
        v.c.write_once(self.control/'crash-request.json',dict(configSha256='0'*64,identity=self.identity))
        with self.assertRaisesRegex(ValueError,'original crash claim'):guest.crash_receipt(self.root,self.config,self.sha)

    def test_reopen_requires_dead_original_and_unchanged_authority(self):
        self.capture();observed=dict(state='CRASHED',serviceAlive=False,jvmAlive=False)
        with patch.object(service,'inspection',return_value=observed):
            guest.predecessor(self.root,self.node,self.config['binding'],check_live=True)
            (self.authority/'authority').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'authority changed'):guest.predecessor(self.root,self.node,self.config['binding'],check_live=True)
            guest.predecessor(self.root,self.node,self.config['binding'],check_live=False)
            for changed in ({'serviceAlive':True},{'jvmAlive':True},{'state':'FAILED'},{'state':'UNCERTAIN'}):
                observed.update(changed)
                with self.assertRaisesRegex(ValueError,'owners not stopped'):guest.predecessor(self.root,self.node,self.config['binding'],check_live=False)
                observed.update(state='CRASHED',serviceAlive=False,jvmAlive=False)


class CrashDispatchTest(unittest.TestCase):
    def test_pending_or_undeclared_crash_cannot_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            worker=Mock();engine=v.Engine(worker,Path(directory),'a'*64,{},crash_allowed=False)
            self.addCleanup(engine.journal.close)
            with self.assertRaisesRegex(ValueError,'undeclared/nonquiescent'):engine.close(kill=True)
            engine.crash_allowed=True;engine.pending.add('operation')
            with self.assertRaisesRegex(ValueError,'undeclared/nonquiescent'):engine.close(kill=True)
            worker.stop.assert_not_called();self.assertFalse(engine.closing)

    def test_partial_claim_prevents_signal_and_original_stop_only_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);worker=Mock();worker.proc.returncode=-9
            engine=v.Engine(worker,root,'a'*64,{},crash_allowed=True);self.addCleanup(engine.journal.close)
            (root/'crash-request.json.writing').write_text('partial')
            with self.assertRaises(FileExistsError):engine.close(kill=True)
            worker.stop.assert_not_called();(root/'crash-request.json.writing').unlink()
            with patch.object(guest,'capture') as capture:
                engine.close(kill=True);engine.close(kill=True);engine.close()
                worker.stop.assert_called_once_with(kill=True);capture.assert_called_once()
            self.assertEqual(-9,v.c.read(root/'stopped.json')['exitCode'])

    def test_failed_capture_stays_failure_and_never_retries_kill(self):
        with tempfile.TemporaryDirectory() as directory:
            worker=Mock();worker.proc.returncode=-9
            engine=v.Engine(worker,Path(directory),'a'*64,{},crash_allowed=True);self.addCleanup(engine.journal.close)
            with patch.object(guest,'capture',side_effect=OSError('disk full')):
                engine.close(kill=True);engine.close(kill=True)
            self.assertIn('disk full',v.c.read(Path(directory)/'stopped.json')['failure']);worker.stop.assert_called_once()

    def test_uncertain_original_send_is_not_retried(self):
        obj=object.__new__(client.Client);obj.generation=1;obj.pending={};obj.crash_submissions=0;obj.final=None
        obj.channel=Mock();obj.reader=Mock();obj.disconnect=Mock();obj.control_call=Mock(return_value={'state':'READY'})
        obj.await_state=Mock(side_effect=ValueError('original not crashed'))
        with patch.object(v,'send',side_effect=ConnectionError('lost')) as send:
            with self.assertRaisesRegex(ValueError,'original not crashed'):obj.crash()
            with self.assertRaisesRegex(ValueError,'already consumed'):obj.crash()
            send.assert_called_once_with(obj.channel,{'crash':True})


class TerminalTest(unittest.TestCase):
    def test_terminal_query_proves_last_event_without_inventing_stream_receipt(self):
        rows,_=fixtures.ClockEdgesTest().fixture();rows[-1]['exitCode']=-9;sha='a'*64
        value=dict(schema='gse-v52-voter-ssh-streams-v1',target={},configSha256=sha,
            channels=[dict(configSha256=sha,after=0,through=2,terminal=False)],
            terminalQuery=dict(configSha256=sha,after=2,through=3,eventSha256=v.digest(v.encoded(rows[-1]))))
        self.assertEqual(1,ssh.channels(value,{},sha,rows,crashed=True))
        with self.assertRaises(ValueError):ssh.channels(value,{},sha,rows)
        for mutate in (lambda r:r['channels'][0].update(through=1),lambda r:r['channels'][0].update(terminal=True),
                       lambda r:r['terminalQuery'].update(eventSha256='0'*64),lambda r:r['terminalQuery'].update(after=1),
                       lambda r:r.pop('terminalQuery')):
            bad=deepcopy(value);mutate(bad)
            with self.assertRaises(ValueError):ssh.channels(bad,{},sha,rows,crashed=True)


if __name__=='__main__':unittest.main()

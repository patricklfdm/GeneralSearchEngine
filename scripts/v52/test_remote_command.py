import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from . import remote_command as c
from .test_cloud_suite import binding as suite_binding


class RemoteCommandTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        selection=c.suite.selection(suite_binding(),'experiment','d'*32)
        self.owner=c.binding(selection,selection['member']['histories'][0],'node-1',c.boot_id(),'e'*32)
        self.store=c.CommandStore(Path(self.temp.name)/'guest',self.owner,create=True)
        self.req=c.request(self.owner,'f'*32,'execute-history',{})

    def test_completed_request_reopens_without_reexecution_or_mutating_payload(self):
        calls=[]
        value=dict(self.req,payload={'setting':'original'})
        def handler(kind,payload,checkpoint):calls.append(kind);payload['setting']='changed';return {'original':'retained'}
        result=self.store.execute(value,handler)
        self.assertEqual('SUCCEEDED',result['state']);self.assertEqual({'setting':'original'},value['payload'])
        self.assertEqual(result,c.CommandStore(self.store.root,self.owner).execute(value,lambda *a:self.fail('replayed')))
        self.assertEqual(['execute-history'],calls)

    def test_every_selected_history_fits_whole_owner_bound_without_cross_member_substitution(self):
        count=0
        for name in c.suite.MEMBERS:
            selection=c.suite.selection(suite_binding(),name,'d'*32)
            for history in selection['member']['histories']:
                owner=c.binding(selection,history,'node-3',c.boot_id(),'e'*32)
                self.assertLessEqual(len(c.encoded(owner))+1,c.REQUEST_BYTES);count+=1
                c.request(owner,'f'*32,'execute-history',{})
        self.assertEqual(33,count)

    def test_changed_request_and_owner_cannot_reuse_claim(self):
        self.store.execute(self.req,lambda *a:{})
        for changed in (dict(self.req,payload={'other':True}),dict(self.req,command='collect'),
                        dict(self.req,bindingSha256='0'*64),dict(self.req,commandId='../outside')):
            with self.subTest(changed=changed),self.assertRaises(ValueError):self.store.execute(changed,lambda *a:self.fail('entered'))
        with self.assertRaisesRegex(ValueError,'ownership'):c.CommandStore(self.store.root,dict(self.owner,session='1'*32))

    def test_binding_keeps_complete_member_history_source_attempt_and_session(self):
        for change in ({'history':'not-selected'},{'node':'node-4'},{'bootId':'0'*36},{'session':'bad'},{'extra':True}):
            with self.subTest(change=change),self.assertRaises(ValueError):c.validate_binding(dict(self.owner,**change))
        changed=copy.deepcopy(self.owner);changed['selection']['member']['profiles'].clear()
        with self.assertRaises(ValueError):c.validate_binding(changed)
        # Offline inspection can read the former boot; a new command cannot execute there.
        with patch.object(c,'boot_id',return_value='11111111-1111-1111-1111-111111111111'):
            self.assertEqual('NOT_FOUND',self.store.query(self.req)['state'])
            with self.assertRaisesRegex(ValueError,'foreign boot'):self.store.execute(self.req,lambda *a:self.fail('entered'))

    def test_crash_at_each_claim_publication_boundary_never_reenters(self):
        for boundary in ('claim','request','started'):
            with self.subTest(boundary=boundary):
                req=dict(self.req,commandId={'claim':'1','request':'2','started':'3'}[boundary]*32)
                path=self.store.command_path(req);path.mkdir()
                if boundary!='claim':c.write_once(path/'request.json',req)
                if boundary=='started':c.write_once(path/'started.json',c.envelope(req,'RUNNING',process=c.process_identity(),startedNanos=1))
                result=self.store.execute(req,lambda *a:self.fail('replayed'))
                self.assertEqual('RUNNING' if boundary=='started' else 'UNCERTAIN',result['state'])

    def test_absent_reused_or_foreign_boot_executor_becomes_uncertain_without_replay(self):
        path=self.store.command_path(self.req);path.mkdir();c.write_once(path/'request.json',self.req)
        process=c.process_identity();c.write_once(path/'started.json',c.envelope(self.req,'RUNNING',process=process,startedNanos=1))
        for changed in (dict(process,startTicks=process['startTicks']+1),dict(process,pid=2147483646)):
            (path/'started.json').write_bytes(c.encoded(c.envelope(self.req,'RUNNING',process=changed,startedNanos=1)))
            result=self.store.execute(self.req,lambda *a:self.fail('replayed'))
            self.assertEqual('UNCERTAIN',result['state']);self.assertIn('absent',result['reason'])
        (path/'started.json').write_bytes(c.encoded(c.envelope(self.req,'RUNNING',process=process,startedNanos=1)))
        with patch.object(c,'boot_id',return_value='11111111-1111-1111-1111-111111111111'):
            self.assertEqual('UNCERTAIN',self.store.query(self.req)['state'])

    def test_lost_terminal_write_preserves_consumed_handler(self):
        original=c.write_once;calls=[]
        def write(path,*args,**kwargs):
            if Path(path).name=='terminal.json':raise OSError('disk publication failed')
            return original(path,*args,**kwargs)
        with patch.object(c,'write_once',side_effect=write),self.assertRaises(OSError):
            self.store.execute(self.req,lambda *a:calls.append(1) or {})
        self.assertEqual('RUNNING',self.store.execute(self.req,lambda *a:self.fail('replayed'))['state'])
        self.assertEqual([1],calls)

    def test_atomic_publication_has_no_partial_json_visible(self):
        from scripts.v51 import remote_command as io
        original=io.os.link;states=[]
        def link(source,target,**kwargs):
            if Path(target).name=='request.json':
                states.append(self.store.query(self.req)['state']);self.assertEqual(self.req,c.read(source))
            return original(source,target,**kwargs)
        with patch.object(io.os,'link',side_effect=link):self.store.execute(self.req,lambda *a:{})
        self.assertEqual(['UNCERTAIN'],states)

    def test_busy_executor_and_duplicate_query_do_not_enter_another_handler(self):
        entered=threading.Event();release=threading.Event();errors=[]
        def handler(*args):entered.set();self.assertTrue(release.wait(3));return {}
        def execute():
            try:self.store.execute(self.req,handler)
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=execute);thread.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertEqual('RUNNING',self.store.execute(self.req,lambda *a:self.fail('duplicate'))['state'])
            other=dict(self.req,commandId='1'*32)
            self.assertEqual('BUSY',self.store.execute(other,lambda *a:self.fail('second'))['state'])
            self.assertEqual('NOT_FOUND',self.store.query(other)['state'])
        finally:release.set();thread.join(4)
        self.assertFalse(thread.is_alive());self.assertEqual([],errors)

    def test_cancellation_retains_original_result_and_failure(self):
        def handler(*args):self.store.cancel(self.req);return {'outcome':'INDETERMINATE'}
        result=self.store.execute(self.req,handler)
        self.assertEqual('CANCELLED',result['state']);self.assertEqual('INDETERMINATE',result['result']['outcome'])
        self.assertEqual(result,self.store.cancel(self.req))
        other=dict(self.req,commandId='1'*32)
        def checkpoint(kind,payload,check):self.store.cancel(other);check();self.fail('continued')
        self.assertEqual('CANCELLED',self.store.execute(other,checkpoint)['state'])
        with self.assertRaisesRegex(ValueError,'unknown'):self.store.cancel(dict(self.req,commandId='2'*32))

    def test_command_and_receipt_limits_preserve_failure_without_replay(self):
        with self.assertRaisesRegex(ValueError,'byte limit'):self.store.execute(dict(self.req,payload={'x':'x'*c.REQUEST_BYTES}),lambda *a:self.fail('entered'))
        answer=self.store.execute(self.req,lambda *a:{'x':'x'*c.RESPONSE_BYTES})
        self.assertEqual('FAILED',answer['state']);self.assertIn('byte',answer['error']['message'])
        self.assertEqual(answer,self.store.query(self.req))
        with patch.object(c,'COMMAND_LIMIT',1),self.assertRaisesRegex(ValueError,'count bound'):
            self.store.execute(dict(self.req,commandId='1'*32),lambda *a:self.fail('entered'))

    def test_nonfinite_values_are_rejected_before_claim_or_retained_as_handler_failure(self):
        for number in (float('nan'),float('inf'),float('-inf')):
            with self.assertRaises(ValueError):self.store.execute(dict(self.req,payload={'value':number}),lambda *a:self.fail('entered'))
        self.assertFalse(self.store.command_path(self.req).exists())
        answer=self.store.execute(self.req,lambda *a:{'value':float('nan')})
        self.assertEqual('FAILED',answer['state']);self.assertEqual(answer,self.store.query(self.req))

    def test_corrupt_terminal_state_process_or_partial_json_fails_closed(self):
        result=self.store.execute(self.req,lambda *a:{})
        path=self.store.command_path(self.req)/'terminal.json'
        for patching in ({'state':'RUNNING'},{'commandId':'0'*32},{'process':dict(result['process'],bootId='x')},
                         {'process':dict(result['process'],pid=True)},{'endedNanos':0},{'extra':True}):
            path.write_bytes(c.encoded(dict(result,**patching)))
            with self.subTest(patching=patching),self.assertRaises(ValueError):self.store.query(self.req)
        path.write_text('{"state":')
        with self.assertRaises(json.JSONDecodeError):self.store.query(self.req)

    def test_symlinks_fifo_and_duplicate_json_are_not_read_as_receipts(self):
        self.store.execute(self.req,lambda *a:{})
        path=self.store.command_path(self.req)/'terminal.json';path.unlink();os.mkfifo(path)
        with self.assertRaises(ValueError):self.store.query(self.req)
        path.unlink();path.symlink_to(self.store.root/'binding.json')
        with self.assertRaises(OSError):self.store.query(self.req)
        path.unlink();path.write_text('{"state":"SUCCEEDED","state":"FAILED"}')
        with self.assertRaisesRegex(ValueError,'duplicate'):self.store.query(self.req)
        alias=Path(self.temp.name)/'alias';alias.symlink_to(self.store.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):c.CommandStore(alias,self.owner)

    def transport(self,submit,query):
        class Transport:
            submits=0;queries=0
            def submit(self,value,deadline):self.submits+=1;return submit(value,deadline)
            def query(self,value,deadline):self.queries+=1;return query(value,deadline)
        return Transport()

    def observe(self,transport,**kwargs):
        now=[0.]
        return c.submit_and_observe(transport,self.req,self.owner,clock=lambda:now[0],sleep=lambda n:now.__setitem__(0,now[0]+n),**kwargs)

    def test_lost_submit_response_only_queries_original_receipt(self):
        def submit(*args):self.store.execute(self.req,lambda *a:{'original':True});raise ConnectionError('lost')
        transport=self.transport(submit,lambda *a:self.store.query(self.req))
        self.assertEqual('SUCCEEDED',self.observe(transport)['state']);self.assertEqual((1,1),(transport.submits,transport.queries))

    def test_soft_budget_warns_but_does_not_abort_healthy_running_command(self):
        terminal=self.store.execute(self.req,lambda *a:{})
        running=c.read(self.store.command_path(self.req)/'started.json');queries=[];warnings=[]
        def query(*args):queries.append(1);return running if len(queries)<8 else terminal
        transport=self.transport(lambda *a:running,query)
        self.assertEqual(terminal,self.observe(transport,warn_after=2,warn=lambda:warnings.append(1)))
        self.assertEqual([1],warnings);self.assertEqual((1,8),(transport.submits,transport.queries))

    def test_transient_and_uncertain_thresholds_stop_without_resubmit(self):
        def failed(*args):raise ConnectionError('lost')
        for response in (failed,lambda *a:c.envelope(self.req,'NOT_FOUND'),lambda *a:c.envelope(self.req,'UNCERTAIN',reason='incomplete')):
            transport=self.transport(failed,response)
            with self.assertRaisesRegex(ValueError,'exhausted; never resubmit'):self.observe(transport)
            self.assertEqual(1,transport.submits);self.assertLessEqual(transport.queries,3)

    def test_permanent_error_and_wrong_response_fail_immediately(self):
        error=ConnectionError('forbidden');error.retryable=False
        def permanent(*args):raise error
        transport=self.transport(permanent,lambda *a:self.fail('queried'))
        with self.assertRaises(ConnectionError):self.observe(transport)
        self.assertEqual((1,0),(transport.submits,transport.queries))
        transport=self.transport(lambda *a:dict(c.envelope(self.req,'NOT_FOUND'),schema='gse-v51-command-receipt-v1'),lambda *a:self.fail('queried'))
        with self.assertRaisesRegex(ValueError,'identity'):self.observe(transport)

    def test_late_exchange_only_queries_never_resubmits(self):
        now=[0.];terminal=self.store.execute(self.req,lambda *a:{})
        def late(*args):now[0]=31;return terminal
        transport=self.transport(late,lambda *a:terminal)
        result=c.submit_and_observe(transport,self.req,self.owner,clock=lambda:now[0],sleep=lambda n:now.__setitem__(0,now[0]+n))
        self.assertEqual(terminal,result);self.assertEqual((1,1),(transport.submits,transport.queries))

    def test_missing_transport_response_fails_instead_of_polling_forever(self):
        transport=self.transport(lambda *a:None,lambda *a:self.fail('queried'))
        with self.assertRaisesRegex(ValueError,'missing response'):self.observe(transport)
        self.assertEqual((1,0),(transport.submits,transport.queries))

    def test_invalid_limits_and_unclosed_commands_never_enter_transport(self):
        for changes in ({'request_seconds':0},{'warn_after':float('inf')},{'failures_limit':0},{'uncertain_limit':True}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.observe(self.transport(lambda *a:self.fail('submit'),None),**changes)
        for command in ('read','update','shell','window','observe-voter'):
            with self.subTest(command=command),self.assertRaises(ValueError):c.request(self.owner,'1'*32,command,{})


if __name__=='__main__':unittest.main()

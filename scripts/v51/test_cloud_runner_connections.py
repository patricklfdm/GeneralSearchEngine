import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import cloud_runner_iap as iap, cloud_http as h, guest_setup as setup, guest_ssh_master as ssh


class PreparationConnectionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        access=setup.generate(self.root/'keys','a'*32);setup.pin(self.root/'known','123',access['publicKey'])
        self.target=dict(project='test-project',zone='us-west4-a',instance='gse-v51-test',instanceId='123',
            user=access['user'],key=str(self.root/'keys/identity'),knownHosts=str(self.root/'known'))
        self.now=time.monotonic();self.end=self.now+30
        self.api=SimpleNamespace(offline=False,clock=lambda:self.now,deadline=self.end,gate_open=True,state='done',failed=False,
            lease=dict(resources=[dict(id=str(i),spec=dict(kind='instance')) for i in (123,456,789)]),
            tokens=lambda _:h.AccessToken('private-token-sentinel',self.end+100))
        self.masters=[];self.fail=False;owner=self
        class Master:
            def __init__(self,args,root,deadline,env,*,connect_deadline):
                self.args,self.root,self.deadline,self.env=args,root,deadline,env;self.closed=False;self.calls=[]
                owner.assertLessEqual(connect_deadline,deadline)
                owner.masters.append(self)
            def exchange(self,remote,data,deadline,**options):
                self.calls.append((remote,data,deadline,options))
                if owner.fail:
                    owner.fail=False;error=ConnectionError('private-token-sentinel');error.partial_output=b'prefix';raise error
                return b'answer'
            def close(self):self.closed=True
        self.enterContext(patch.object(ssh,'Master',Master))
    def call(self,action='part',**options):
        return iap._network_exchange(self.api,self.target,['python3',action],b'data',self.end,maximum=4096,**options)
    def scope(self):return iap.preparation_connections(self.api,self.root/'connections.json')

    def test_many_parts_share_one_private_connection_and_credentials(self):
        with patch.object(self.api,'tokens',wraps=self.api.tokens) as tokens,self.scope():
            for _ in range(21):self.assertEqual(b'answer',self.call())
            self.assertEqual(1,tokens.call_count);self.assertEqual(1,len(self.masters))
            master=self.masters[0];self.assertEqual(21,len(master.calls));self.assertEqual(self.end,master.deadline)
            self.assertIn('StrictHostKeyChecking=yes',master.args);self.assertIn('HostKeyAlias=gse-v51-123',master.args)
            self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS',master.env)
            self.assertNotIn('private-token-sentinel',str(master.args)+str(master.env))
        self.assertTrue(master.closed);self.assertFalse(master.root.parent.exists())
        self.assertFalse(hasattr(self.api,'_preparation_connections'))
        receipt=json.loads((self.root/'connections.json').read_text())
        self.assertEqual([dict(instanceId='123',connections=1,commands=21,failures=0)],receipt['guests'])
        self.assertNotIn('private-token-sentinel',str(receipt))

    def test_lost_reply_is_not_replayed_and_only_explicit_query_reconnects(self):
        with self.scope():
            self.fail=True
            with self.assertRaises(ConnectionError) as caught:self.call(retain_partial=True)
            self.assertNotIn('private-token-sentinel',str(caught.exception));self.assertEqual(b'prefix',caught.exception.partial_output)
            self.assertEqual(1,len(self.masters));self.assertTrue(self.masters[0].closed)
            self.assertEqual(b'answer',self.call('query'))
            self.assertEqual(2,len(self.masters))
            self.assertEqual(['part','query'],[v.calls[0][0][-1] for v in self.masters])
            self.assertTrue(all(v.deadline==self.end for v in self.masters))

    def test_three_members_have_distinct_connections_all_closed_before_failure_returns(self):
        public=Path(self.target['knownHosts']).read_text().split(' ',1)[1].strip()
        with self.assertRaisesRegex(RuntimeError,'stop'),self.scope():
            for index,identity in enumerate(('123','456','789'),1):
                path=self.root/f'known-{index}';setup.pin(path,identity,public)
                self.target.update(instance='gse-v51-node-'+str(index),instanceId=identity,knownHosts=str(path))
                self.call();self.call('query')
            self.assertEqual(3,len(self.masters));self.assertEqual(3,len({m.root for m in self.masters}))
            raise RuntimeError('stop')
        self.assertTrue(all(m.closed and not m.root.parent.exists() for m in self.masters))
        record=json.loads((self.root/'connections.json').read_text())
        self.assertEqual(['123','456','789'],[r['instanceId'] for r in record['guests']])

    def test_changed_host_pin_key_target_or_unadmitted_id_cannot_reuse_connection(self):
        with self.scope():
            self.call();original=dict(self.target)
            for field,value in (('instance','gse-v51-replaced'),('instanceId','999')):
                self.target[field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):self.call()
                self.target=original.copy()
            path=Path(self.target['knownHosts']);raw=path.read_bytes()
            setup.pin(self.root/'other','123',setup.generate(self.root/'other-keys','b'*32)['publicKey'])
            path.write_bytes((self.root/'other').read_bytes())
            with self.assertRaisesRegex(ValueError,'pinned identity'):self.call()
            path.write_bytes(raw)
            key=Path(self.target['key']);key.write_bytes(key.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'pinned identity'):self.call()
            self.assertEqual(1,len(self.masters[0].calls))

    def test_expiry_extension_and_exception_close_without_new_submission(self):
        with self.assertRaisesRegex(RuntimeError,'synthetic'),self.scope():
            self.call();self.api.deadline+=1
            with self.assertRaises(ValueError):self.call()
            self.api.deadline=self.end;self.now=self.end
            with self.assertRaises(ValueError):self.call()
            self.assertEqual(1,len(self.masters[0].calls))
            raise RuntimeError('synthetic')
        self.assertTrue(self.masters[0].closed);self.assertFalse(self.masters[0].root.parent.exists())

    def test_unadmitted_or_nested_scope_cannot_allocate_credentials(self):
        self.api.gate_open=False
        with self.assertRaises(ValueError),self.scope():pass
        self.api.gate_open=True
        with self.scope():
            with self.assertRaises(ValueError),self.scope():pass
        self.assertEqual([],self.masters)


if __name__=='__main__':unittest.main()

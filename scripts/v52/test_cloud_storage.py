"""Original-result protocols and actual native factory with modeled external I/O."""
from copy import deepcopy
from contextlib import ExitStack
import os
from pathlib import Path
import shlex
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from . import cloud_storage as s,cloud_volume_guest as v
from . import test_cloud_volume as volume_fixture,test_cloud_iap as iap_fixture


class EndpointTest(unittest.TestCase):
    def setUp(self):
        self.base=volume_fixture.VolumeTest('test_original_blank_device_and_independent_retained_and_current_replay')
        self.base.setUp();self.addCleanup(self.base.doCleanups);self.value=self.base.value;self.events=[]
        self.fault=lambda action,result:result
        self.parent=SimpleNamespace(exchange=self.exchange,note=Mock())
        self.guests=SimpleNamespace(session=SimpleNamespace(owner=SimpleNamespace(checkpoint=lambda:dict(
            expiresAt=int(time.time())+600,graceSeconds=60))))
        with patch.object(s,'request',return_value=self.value):self.endpoint=s.VolumeEndpoint(self.parent,self.guests,'node-1')
        self.endpoint.checkpoint=Mock()
    def exchange(self,guests,node,kind,action,data,end):
        self.events.append(action)
        result=v._perform(action,data['request'],data['token'],self.base.block)
        return self.fault(action,result)
    def test_original_initialization_and_readonly_check_with_different_monotonic_domains(self):
        monotonic,ns=time.monotonic,time.monotonic_ns
        self.base.block.clock=lambda:monotonic()+1000
        with patch.object(v,'time',SimpleNamespace(monotonic=lambda:monotonic()+1000,monotonic_ns=lambda:ns()+10**12)):
            checked=self.endpoint.prepare()
        self.assertEqual('SUCCEEDED',checked['state']);self.assertEqual(['clock','prepare','clock','check'],self.events)
        self.assertEqual(1,self.base.block.formats)
        with self.assertRaisesRegex(ValueError,'already submitted'):self.endpoint.prepare()
    def test_lost_successful_prepare_reply_queries_original_once_without_reformat(self):
        def lose(action,result):
            if action=='prepare':raise ConnectionError('lost original reply')
            return result
        self.fault=lose;self.endpoint.prepare()
        self.assertEqual(['clock','prepare','query','clock','check'],self.events);self.assertEqual(1,self.base.block.formats)
    def test_uncertain_or_failed_original_receipt_fails_fast_without_prepare_retry(self):
        for state in ('NOT_FOUND','UNCERTAIN','FAILED'):
            with self.subTest(state=state):
                self.endpoint.started=False;self.events.clear()
                with patch.object(self.endpoint,'exchange',return_value=dict(state=state)) as call:
                    with self.assertRaisesRegex(ValueError,'unresolved/failed'):self.endpoint.prepare()
                self.assertEqual(1,call.call_count);self.assertEqual('prepare',call.call_args.args[0])
    def test_three_query_failures_are_terminal_and_terminal_permissions_never_retry(self):
        count=0
        def disconnect(action,result):
            nonlocal count
            if action in ('prepare','query'):count+=1;raise ConnectionError('connection lost')
            return result
        self.fault=disconnect
        with self.assertRaisesRegex(ValueError,'failures exhausted'):self.endpoint.prepare()
        self.assertEqual(4,count);self.assertEqual(1,self.events.count('prepare'));self.assertEqual(1,self.base.block.formats)
        error=s.iap.transport.ProcessError('IAP_PERMISSION');calls=Mock(side_effect=error)
        with self.assertRaises(s.iap.transport.ProcessError):s.readonly(calls,time.monotonic()+30)
        self.assertEqual(1,calls.call_count)
    def test_clock_read_can_retry_with_same_nonce_but_wrong_clock_or_startup_cannot(self):
        tokens=[];original=self.parent.exchange
        def lost(guests,node,kind,action,data,end):
            if action=='clock':
                tokens.append(data['token'])
                if len(tokens)==1:raise ConnectionError('clock reply lost')
            return original(guests,node,kind,action,data,end)
        self.parent.exchange=lost;self.endpoint.prepare();self.assertEqual(tokens[0],tokens[1]);self.assertEqual(1,self.base.block.formats)
        changed=deepcopy(self.base.call('query',self.endpoint.original)['startup']);changed['volume']['uid']=0
        with self.assertRaises(ValueError):self.endpoint.check(changed)
    def test_clock_nonce_change_stops_before_initialization(self):
        self.fault=lambda action,result:dict(result,nonce='0'*32) if action=='clock' else result
        with self.assertRaisesRegex(ValueError,'clock identity'):self.endpoint.prepare()
        self.assertEqual(['clock'],self.events);self.assertEqual(0,self.base.block.formats)
    def test_changed_identity_response_cannot_be_a_successful_original_result(self):
        self.fault=lambda action,result:dict(result,requestSha256='0'*64) if action=='prepare' else result
        with self.assertRaisesRegex(ValueError,'reply identity'):self.endpoint.prepare()
        self.assertEqual(['clock','prepare'],self.events);self.assertEqual(1,self.base.block.formats)
    def test_readonly_retry_has_original_deadline_and_bounded_attempt_count(self):
        attempts=[]
        def failed():attempts.append(1);raise TimeoutError('original exchange')
        with patch.object(s.time,'sleep'),self.assertRaises(TimeoutError):s.readonly(failed,time.monotonic()+1)
        self.assertEqual(3,len(attempts))
        with self.assertRaisesRegex(ValueError,'query deadline'):s.readonly(lambda:self.fail('late call'),time.monotonic()-1)

    def test_late_readonly_success_is_rejected_without_retry(self):
        call=Mock(return_value={'state':'SUCCEEDED'})
        with patch.object(s.time,'monotonic',side_effect=[10,31]),self.assertRaisesRegex(ValueError,'late query'):
            s.readonly(call,30)
        self.assertEqual(1,call.call_count)


class NativeStorageTest(unittest.TestCase):
    def setUp(self):
        self.base=iap_fixture.NativeGuestFactoryTest('test_native_identity_scoped_token_environment_binding_and_close_order')
        self.base.setUp();self.addCleanup(self.base.doCleanups);self.root=self.base.root;self.session=self.base.session
        self.group=self.base.open();self.models={};self.installs={};self.installers=[];self.actions=[];self.parents={}
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.lose_prepare=True;self.lose_install=True;self.changed_install=False;self.change_reply=lambda *args:None
        self.stack.enter_context(patch.object(v,'account'))
        def directory(path,private=False):
            path=Path(path);self.assertTrue(path.is_dir());self.assertFalse(path.is_symlink());return path
        self.stack.enter_context(patch.object(v,'directory',side_effect=directory))
        self.stack.enter_context(patch.object(s.iap.transport,'process',side_effect=self.exchange))
        outer=self
        class Installer(s.install.Installer):
            def __init__(self,target,descriptor):
                super().__init__(target,descriptor);self.node='node-'+str(target['port']-21000);outer.installers.append(self)
            def exchange(self,action,parent,payload):
                self.calls.append(action);outer.actions.append((self.node,'python',action))
                if action=='install':
                    s.python.payload(payload.encode(),self.descriptor)
                    outer.installs[self.node]=dict(schema=s.python.RECEIPT,descriptorSha256=s.digest(s.encoded(self.descriptor)),
                        filesSha256=s.digest(s.encoded(self.descriptor['files'])),root=v.MOUNT+'/python-'+self.descriptor['sha256'],
                        host=dict(bootId=outer.group.guests[self.node]['bootId'],uid=1001,parentDevice=os.makedev(8,16),parentInode=100+int(self.node[-1])))
                    if outer.lose_install:outer.lose_install=False;raise ConnectionError('lost original installation reply')
                result=deepcopy(outer.installs[self.node])
                if outer.changed_install:result['host']['parentInode']+=1
                return result
        self.stack.enter_context(patch.object(s.install,'Installer',Installer))
    def exchange(self,args,data,end,**kwargs):
        remote=shlex.split(args[-1]);request=s.strict(data)
        if remote[0]=='python3':return self.base.exchange(args,data,end,**kwargs)
        node='node-'+str(int(args[args.index('-p')+1])-21000);action=remote[-1]
        if remote[0]=='sudo':
            self.assertEqual(remote[:9],['sudo','-n','-u','root','-g','root','--','/usr/bin/python3','-I'])
            self.assertEqual(s.trusted_source('volume'),remote[remote.index('-c')+1]);self.actions.append((node,'volume',action))
            model=self.models.setdefault(node,volume_fixture.Block(request['request']))
            model.uuid='00000000-0000-4000-8000-'+str(int(node[-1])).zfill(12)
            parent=self.root/('model-'+node);parent.mkdir(exist_ok=True)
            with patch.object(v,'PARENT',str(parent/'claims')):
                result=v._perform(action,request['request'],request['token'],model)
            if action=='prepare' and self.lose_prepare:self.lose_prepare=False;raise ConnectionError('lost original volume reply')
        else:
            self.assertEqual(s.trusted_source('paths'),remote[remote.index('-c')+1]);self.actions.append((node,'paths',action))
            req=request['request'];history=request['history'];claim=dict(requestSha256=v.digest(req),historySha256=history,volume=request['volume'])
            result=dict(schema='gse-v52-history-parent-v1',claimSha256=v.digest(claim),state='SUCCEEDED',
                root=v.MOUNT+'/history-'+history+'/'+node,host=dict(bootId=req['guest']['bootId'],uid=req['guest']['uid'],
                    parentDevice=os.makedev(8,16),parentInode=1000+int(node[-1])))
        self.change_reply(node,action,result)
        return s.encoded(result)
    def prepare(self):return self.group.prepare_storage(self.root/'storage')

    def test_actual_factory_original_mount_install_and_complete_history_placement(self):
        storage=self.prepare();self.assertTrue(storage.ready);self.assertTrue(all(m.formats==1 for m in self.models.values()))
        self.assertEqual(1,sum(i.reply_lost for i in self.installers));self.assertTrue(all(i.closed for i in self.installers))
        self.assertEqual(3,sum(action=='prepare' and kind=='volume' for _,kind,action in self.actions))
        self.assertEqual(1,sum(action=='query' and kind=='volume' for _,kind,action in self.actions))
        name=self.session.owner.request['selection']['member']['histories'][0]
        placement=storage.placement(self.group,name)
        self.assertEqual(self.session.api.admission.proof['source']['java'],placement.binding['java'])
        self.assertEqual(self.session.api.admission.proof['source'],placement.descriptor['source'])
        factory=placement.factory(name);receiver=factory(self.root/'whole-history',name,storage.source)
        receiver.binding={};self.assertEqual('owned-private-hosts',receiver.topology_plan()['placement'])
        self.assertEqual('node-1',receiver.receiver_root('node-1').name)
        with self.assertRaisesRegex(ValueError,'already claimed'):storage.placement(self.group,name)
        with self.assertRaisesRegex(ValueError,'already consumed'):self.group.prepare_storage(self.root/'second-storage')
        receipt=s.strict((storage.output/'receipt.json').read_bytes());self.assertEqual('STORAGE_READY_NOT_QUALIFIED',receipt['status'])
        self.assertFalse(receipt['engineWorkloadExecuted']);self.assertFalse(receipt['fullRemoteQualification'])
        self.session.close();self.assertEqual({},self.base.base.case.server.resources)

    def test_failed_initialization_is_consumed_retained_and_original_owner_cleans(self):
        def fail(node,action,result):
            if node=='node-2' and action=='prepare':result['state']='FAILED';result['startup']['status']='FAIL'
        self.change_reply=fail
        with self.assertRaisesRegex(ValueError,'unresolved/failed'):self.prepare()
        self.assertFalse(self.session.storage.ready);self.assertTrue((self.root/'storage/failure.json').exists())
        report=s.diagnostic.project(s.strict((self.root/'storage/diagnostic.json').read_bytes()))
        self.assertEqual(('node-2','volume-initialize','prepare','reply'),
            tuple(report[k] for k in ('node','operation','action','stage')))
        self.assertEqual(['node-1'],report['initializedNodes']);self.assertEqual(['node-1'],report['pythonInstalledNodes'])
        self.assertEqual('V52_STORAGE_VALIDATION_REJECTED',report['reasonCode'])
        self.assertEqual('cloud_storage',report['origin']['module'])
        exchanges=s.strict((self.root/'storage/node-2-exchanges.json').read_bytes())['exchanges']
        self.assertEqual('FAILED',exchanges[-1]['answer']['state'])
        with self.assertRaisesRegex(ValueError,'already consumed'):self.group.prepare_storage(self.root/'second')
        self.assertNotIn('node-3',self.models);self.assertTrue(all(m.formats==1 for m in self.models.values()))
        self.session.close();self.assertEqual({},self.base.base.case.server.resources)

    def test_python_failure_retains_operation_and_cleans_without_private_exception(self):
        class Installer:
            def __init__(self,*args):pass
            def install(self,*args):raise TimeoutError('secret raw command and private key')
            def close(self):pass
        with patch.object(s.install,'Installer',Installer),self.assertRaises(TimeoutError):self.prepare()
        report=s.diagnostic.project(s.strict((self.root/'storage/diagnostic.json').read_bytes()))
        self.assertEqual(('node-1','python-install','V52_STORAGE_EXCHANGE_TIMEOUT'),
            tuple(report[k] for k in ('node','operation','reasonCode')))
        self.assertEqual(['node-1'],report['initializedNodes']);self.assertEqual([],report['pythonInstalledNodes'])
        self.assertNotIn('secret',str(report));self.assertIsNone(report['action'])
        self.session.close();self.assertEqual({},self.base.base.case.server.resources)

    def test_diagnostic_write_failure_cannot_mask_original_or_skip_cleanup(self):
        self.change_reply=lambda node,action,result:result.update(state='FAILED') if action=='prepare' else None
        with patch.object(s.Storage,'retain_failure',side_effect=OSError('diagnostic disk full')), \
             self.assertRaisesRegex(ValueError,'unresolved/failed'):self.prepare()
        self.session.close();self.assertEqual({},self.base.base.case.server.resources)

    def test_final_receipt_failure_cannot_grant_placement_or_bypass_cleanup(self):
        save=s.runner.artifacts.save
        def fail(path,value):
            if path==self.root/'storage/receipt.json':raise OSError('synthetic full evidence volume')
            return save(path,value)
        with patch.object(s.runner.artifacts,'save',side_effect=fail),self.assertRaisesRegex(OSError,'evidence volume'):
            self.prepare()
        storage=self.session.storage;self.assertFalse(storage.ready)
        name=self.session.owner.request['selection']['member']['histories'][0]
        with self.assertRaisesRegex(ValueError,'not ready'):storage.placement(self.group,name)
        self.assertFalse(any(kind=='paths' for _,kind,_ in self.actions))
        for node in s.iap.topology.NODES:
            self.assertTrue((self.root/('storage/'+node+'-exchanges.json')).is_file())
        self.assertEqual(1,s.strict((self.root/'storage/node-1-exchanges.json').read_bytes())['exchanges'].count(
            dict(action='prepare',errorType='ConnectionError')))
        self.session.close();self.assertEqual({},self.base.base.case.server.resources)

    def test_installed_capsule_replacement_blocks_history_before_any_parent_or_measurement(self):
        storage=self.prepare();self.changed_install=True
        name=self.session.owner.request['selection']['member']['histories'][0]
        with self.assertRaisesRegex(ValueError,'installed capsule changed'):storage.placement(self.group,name)
        report=s.diagnostic.project(s.strict((self.root/'storage/diagnostic.json').read_bytes()))
        self.assertEqual('placement-python',report['operation'])
        self.assertFalse(any(kind=='paths' for _,kind,_ in self.actions));self.assertTrue(all(m.formats==1 for m in self.models.values()))
        self.session.close();self.assertEqual({},self.base.base.case.server.resources)


if __name__=='__main__':unittest.main()

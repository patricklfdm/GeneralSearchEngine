"""Real consumed producer/download protocol with explicitly synthetic source bytes."""
import base64
from copy import deepcopy
import io
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
from . import guest_source_producer as producer, guest_producer_source as controller, guest_source_transfer as wire
from . import guest_source_delivery as delivery, guest_bootstrap as boot, guest_package_receiver as receiver
from . import guest_package_delivery as package, guest_transport as transport, guest_delivery_receiver as helper
from . import performance_model as m, remote_command as c
from . import test_guest_owned_bootstrap as fixtures


class ProducerTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ReceiverTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.base=receiver.installed(f.fixture.parent,f.fixture.value)
        self.configs=[deepcopy(f.cfg) for _ in range(3)]
        for i,cfg in enumerate(self.configs,1):cfg['binding']['node']='node-'+str(i)
        self.request=dict(schema=producer.SCHEMA,configs=self.configs);self.generated=0;self.fault=None;self.calls=[];test=self
        self.seed=os.urandom((1<<20)+1024)
        class Service:
            def __init__(_,base,cfg):_.config=cfg;_.cell=Path(cfg['root']);_.deadline=time.monotonic()+5400
            def prepare_source(service):
                test.generated+=1
                if test.fault=='generation':raise ValueError('seed generation failed')
                for name,text in zip(boot.TOPOLOGY,('\n'.join(service.config['hosts'])+'\n','\n'.join(map(str,service.config['ports']))+'\n',service.config['groupId']+'\n')):
                    (service.cell/name).write_text(text)
                (service.cell/'source').mkdir()
                for i,name in enumerate(boot.SOURCE):(service.cell/'source'/name).write_bytes(test.seed if i==0 else name.encode())
        mocked=patch.object(producer.guest,'Service',Service);mocked.start();self.addCleanup(mocked.stop)
        class Endpoint:
            offline=True;value=f.fixture.value
            def producer(_,action,request,deadline,*,node=None,index=None):
                test.calls.append((action,node,index))
                if test.fault=='no-receipt':
                    if action=='prepare':raise ConnectionError('uncertain write')
                    return producer.envelope(request,'NOT_FOUND')
                answer=test.call(action,request=request,node=node,index=index)
                if action=='prepare' and test.fault=='lost-replies':raise ConnectionError('lost completed prepare')
                if action=='chunk' and (test.fault=='read-exhausted' or test.fault=='lost-replies' and test.calls.count((action,node,index))==1):
                    error=ConnectionError('interrupted read');error.partial_output=answer[:100];raise error
                if test.fault=='bad-chunk' and action=='chunk':return answer[:-1]
                if test.fault=='bad-manifest' and action=='manifest':answer['config']['groupId']='00000000-0000-0000-0000-000000000000'
                return answer
        self.endpoint=Endpoint()
    def call(self,action,*,request=None,node=None,index=None,budget=None):
        f=self.fixture;tail=[action,base64.b64encode(m.canonical(request or self.request)).decode()]
        if node is not None:tail.append(node)
        if index is not None:tail.append(str(index))
        answer=receiver.producer(f.fixture.parent,f.fixture.value,budget or f.budget,tail)
        return answer if isinstance(answer,bytes) else answer['receipt']
    def download(self):
        self.source=controller.RemoteSource();return self.source.prepare(self.configs,time.monotonic()+50,
            endpoint=self.endpoint,output=self.fixture.fixture.root/'download')
    def test_prepare_is_consumed_and_original_terminal_revalidates_exports(self):
        result=self.call('prepare');self.assertEqual(result['state'],'SUCCEEDED');self.assertEqual(len(result['exports']),3)
        self.assertEqual(self.call('query'),result);self.assertEqual(self.call('prepare'),result);self.assertEqual(self.generated,1)
        self.assertFalse(self.fixture.root.exists())
        value=self.call('manifest',node='node-2');self.assertGreater(len(value['chunks']),1)
        for row in value['chunks']:
            raw=self.call('chunk',node='node-2',index=row['index']);self.assertEqual(m.sha(raw),row['sha256'])
        path=producer.location(self.base)/'exports/node-2/parts'/value['parts']['parts'][0]['name'];path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.call('query')
    def test_remote_download_survives_lost_reply_and_interrupted_reads_without_prepare_replay(self):
        self.fault='lost-replies';exports=self.download();self.assertEqual(self.generated,1)
        self.assertEqual(sum(a=='prepare' for a,_,_ in self.calls),1);self.assertEqual(sum(a=='query' for a,_,_ in self.calls),2)
        root=self.fixture.fixture.root/'download';record=c.read(root/'receipt.json')
        self.assertEqual(record['status'],'PASS');self.assertEqual(record['readFailures'],6)
        self.assertEqual(len(list((root/'failures').glob('*.bin'))),6)
        (producer.location(self.base)/'exports').rename(producer.location(self.base)/'hidden-exports')
        for cfg,row in zip(self.configs,exports):
            self.assertEqual(boot.descriptor(Path(row['folder']),row['descriptorSha256'],cfg)['files'],
                             c.read(root/'node-1-descriptor.json')['bootstrap']['files'])
        # Feed the real downloaded node-1 archive into the real receiver.
        row=exports[0];value=wire.describe(Path(row['folder']),row['descriptorSha256'],self.configs[0])
        wire.begin(self.base,value,lambda:None)
        for chunk in value['chunks']:
            with (Path(row['folder'])/'parts'/chunk['part']).open('rb') as stream:
                stream.seek(chunk['offset']);wire.put(self.base,value,chunk['index'],io.BytesIO(stream.read(chunk['bytes'])),lambda:None)
        self.assertEqual(wire.finish(self.base,value,lambda:None)['state'],'SUCCEEDED')
        Path(row['folder']).rename(root/'hidden-cache')
        request=dict(config=self.configs[0],descriptorSha256=row['descriptorSha256'],sourceTransferSha256=m.sha(m.canonical(value)))
        self.assertEqual(self.fixture.call('install',request)['receipt']['result']['files'],6)
    def test_partial_prepare_claim_is_uncertain_and_never_regenerates(self):
        with patch.object(producer,'produce',side_effect=SystemExit('crash')):
            with self.assertRaises(SystemExit):self.call('prepare')
        self.assertEqual(self.call('query')['state'],'UNCERTAIN')
        self.assertEqual(self.call('prepare')['state'],'UNCERTAIN');self.assertEqual(self.generated,0)
        with self.assertRaisesRegex(ValueError,'not complete'):self.call('manifest',node='node-1')
    def test_generation_failure_is_retained_and_consumes_the_command(self):
        self.fault='generation';result=self.call('prepare');self.assertEqual(result['state'],'FAILED')
        self.assertEqual(self.call('prepare'),result);self.assertEqual(self.generated,1)
        with self.assertRaisesRegex(ValueError,'preparation failed|consumed'):self.download()
    def test_controller_unknown_write_stops_at_original_deadline(self):
        from .cloud_fake import Clock
        clock=Clock();self.fault='no-receipt';source=controller.RemoteSource(clock=clock.seconds,sleep=clock.sleep)
        with self.assertRaisesRegex(ValueError,'deadline|no prepare replay'):
            source.prepare(self.configs,clock.seconds()+.2,endpoint=self.endpoint,output=self.fixture.fixture.root/'unknown')
        self.assertEqual(sum(a=='prepare' for a,_,_ in self.calls),1)
        self.assertTrue(all(a in ('prepare','query') for a,_,_ in self.calls))
    def test_read_retry_exhaustion_is_bounded_and_preserves_every_partial(self):
        self.fault='read-exhausted'
        with self.assertRaisesRegex(ConnectionError,'interrupted'):self.download()
        self.assertEqual(sum(a=='chunk' for a,_,_ in self.calls),3);self.assertEqual(self.generated,1)
        root=self.fixture.fixture.root/'download';self.assertEqual(len(list((root/'failures').glob('*.bin'))),3)
        self.assertEqual((root/'node-1/parts/part-0000.bin.partial').read_bytes(),b'')
        self.assertEqual(c.read(root/'receipt.json')['status'],'FAIL');self.assertFalse(self.fixture.root.exists())
    def test_digest_failure_does_not_retry_or_admit_import(self):
        self.fault='bad-chunk'
        with self.assertRaisesRegex(ValueError,'digest/size'):self.download()
        self.assertEqual(sum(a=='chunk' for a,_,_ in self.calls),1);self.assertFalse(self.fixture.root.exists())
        self.assertEqual(len(list((self.fixture.fixture.root/'download/failures').glob('*.bin'))),1)
    def test_changed_manifest_is_rejected_before_first_download_chunk(self):
        self.fault='bad-manifest'
        with self.assertRaises(ValueError):self.download()
        self.assertFalse(any(a=='chunk' for a,_,_ in self.calls));self.assertFalse(self.fixture.root.exists())
    def test_foreign_config_duplicate_member_and_renewed_deadline_fail_before_prepare(self):
        for key,value in (('root','/foreign'),('packageManifestSha256','0'*64)):
            changed=deepcopy(self.request)
            for cfg in changed['configs']:cfg[key]=value
            with self.assertRaisesRegex(ValueError,'binding'):self.call('prepare',request=changed)
        changed=deepcopy(self.request);changed['configs'][1]['binding']['node']='node-1'
        with self.assertRaisesRegex(ValueError,'member configurations'):self.call('prepare',request=changed)
        with self.assertRaisesRegex(ValueError,'deadline changed'):
            self.call('prepare',budget=dict(self.fixture.budget,expiresNanos=self.fixture.budget['expiresNanos']+1))
        self.assertFalse(producer.location(self.base).exists())
    def test_reboot_expiry_and_package_tampering_fail_closed(self):
        with patch.object(helper,'boot_identity',return_value='22222222-2222-4222-8222-222222222222'):
            with self.assertRaises(ValueError):self.call('prepare')
        with patch.object(helper.time,'monotonic_ns',return_value=self.fixture.budget['expiresNanos']+1):
            with self.assertRaises(ValueError):self.call('prepare')
        (self.base/'padding').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.call('prepare')
        self.assertFalse(producer.location(self.base).exists())
    def test_invalid_chunk_selection_and_symlink_cannot_read_arbitrary_files(self):
        self.call('prepare')
        for node,index in (('../secret',0),('node-1',65),('node-1',-1)):
            with self.assertRaises(ValueError):self.call('chunk',node=node,index=index)
        path=producer.location(self.base)/'node-1-descriptor.json';path.rename(path.with_suffix('.old'));path.symlink_to(path.with_suffix('.old'))
        with self.assertRaises(ValueError):self.call('query')
    def test_controller_retention_rejects_unexpected_and_linked_files(self):
        self.download();rows=dict(self.source.retention_files());self.assertEqual(len(rows),6)
        (self.source.root/'extra').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'retention inventory'):list(self.source.retention_files())
    def test_export_rebinding_cannot_change_source_or_topology(self):
        self.call('prepare');root=producer.location(self.base)/'cell'
        local=deepcopy(self.configs[0]);local['root']=str(root);changed=deepcopy(self.configs[1]);changed['hosts'][0]='127.0.0.9'
        with self.assertRaisesRegex(ValueError,'configuration binding'):boot.export(root,self.fixture.fixture.root/'foreign-export',changed,producer_config=local)
    def test_endpoint_requires_original_deadline_and_response_identity(self):
        class Local(package.Endpoint):
            offline=True
            def argv(_,remote):return remote
        ep=Local(dict(instanceId='123'),self.fixture.fixture.parent,self.fixture.fixture.value);ep.budget=self.fixture.budget;ep.deadline=time.monotonic()+10
        answer=dict(schema='gse-v51-package-producer-v1',action='query',requestSha256=m.sha(m.canonical(self.request)),
            deadlineSha256=m.sha(m.canonical(ep.budget)),receipt=producer.envelope(self.request,'NOT_FOUND'))
        with patch.object(package.transport,'process',return_value=m.canonical(answer)):
            self.assertEqual(ep.producer('query',self.request,ep.deadline)['state'],'NOT_FOUND')
            with self.assertRaises(ValueError):ep.producer('prepare',self.request,ep.deadline+1)
        for key in ('action','requestSha256','deadlineSha256'):
            with patch.object(package.transport,'process',return_value=m.canonical(dict(answer,**{key:'bad'}))):
                with self.assertRaisesRegex(ValueError,'identity'):ep.producer('query',self.request,ep.deadline)
        ep.offline=False
        with self.assertRaisesRegex(ValueError,'scope'):ep.producer('prepare',self.request,ep.deadline)


class PartialOutputTest(unittest.TestCase):
    def test_failed_binary_connection_retains_only_bounded_received_bytes(self):
        command=[sys.executable,'-c','import sys;sys.stdout.buffer.write(b"original-partial");sys.stdout.flush();sys.exit(3)']
        with self.assertRaises(ConnectionError) as result:transport.process(command,b'',time.monotonic()+10,maximum=32,retain_partial=True)
        self.assertEqual(result.exception.partial_output,b'original-partial')
        with self.assertRaises(ConnectionError) as result:transport.process(command,b'',time.monotonic()+10,maximum=32)
        self.assertFalse(hasattr(result.exception,'partial_output'))


class OwnedProducerFailureTest(unittest.TestCase):
    def test_source_failure_before_service_launch_still_charges_retains_and_cleans(self):
        fixture=fixtures.OwnedBootstrapLifecycleTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        mount=fixture.root/'common';mount.mkdir(mode=0o700);fixture.services.mounts={n:str(mount) for n in (1,2,3)}
        test=self
        class FailedSource(controller.RemoteSource):
            def prepare(source,configs,deadline,*,endpoint,output):
                test.assertTrue(all((n,'finish') in fixture.events for n in (1,2,3)))
                test.assertEqual(endpoint.value['binding']['node'],'node-1')
                source.root=Path(output);source.root.mkdir(mode=0o700)
                c.write_once(source.root/'receipt.json',dict(status='FAIL',reason='producer SSH unavailable'))
                raise ValueError('producer SSH unavailable')
        from .guest_owned_bootstrap import Bootstrap
        fixture.services.bootstrap=Bootstrap(FailedSource(),delivery=delivery.Delivery(),clock=fixture.clock.seconds,sleep=fixture.clock.sleep)
        result=fixture.run_owned();self.assertEqual(result['status'],'FAIL');fixture.assert_clean(result)
        self.assertFalse(fixture.clients)
        self.assertTrue(any(k.endswith('/bootstrap/producer/receipt.json') for k in fixture.http.objects))

"""Binary transfer/admission regressions; synthetic seed bytes, no Java claims."""
import base64
from copy import deepcopy
import io
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from . import guest_source_transfer as wire, guest_source_delivery as delivery, guest_bootstrap as boot
from . import guest_package_receiver as receiver, guest_package_delivery as package, guest_delivery_receiver as helper
from . import performance_model as m, remote_command as c, remote_collection as parts
from . import test_guest_owned_bootstrap as fixtures


class SourceTransferTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ReceiverTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.base=receiver.installed(f.fixture.parent,f.fixture.value)
        # Incompressible >1 MiB input forces a real multi-chunk archive.
        producer=f.fixture.root/'producer'
        (producer/'source'/boot.SOURCE[0]).write_bytes(os.urandom((1<<20)+4096))
        producer.rename(f.root)
        self.folder=f.fixture.root/'binary-export';row=boot.export(f.root,self.folder,f.cfg)
        f.root.rename(producer)
        self.digest=row['descriptorSha256'];self.value=wire.describe(self.folder,self.digest,f.cfg)
        self.assertGreater(len(self.value['chunks']),1)
    def call(self,action,data=b'',index=None,value=None,budget=None):
        f=self.fixture;value=value or self.value
        tail=[action,base64.b64encode(m.canonical(value)).decode()]
        if index is not None:tail.append(str(index))
        return receiver.source_transfer(f.fixture.parent,f.fixture.value,budget or f.budget,tail,io.BytesIO(data))['receipt']
    def chunk(self,row):
        with (self.folder/'parts'/row['part']).open('rb') as stream:
            stream.seek(row['offset']);return stream.read(row['bytes'])
    def send(self):
        self.assertEqual(self.call('begin')['state'],'RECEIVING')
        for row in self.value['chunks']:self.call('chunk',self.chunk(row),row['index'])
        return self.call('finish')
    def request(self):
        return dict(config=self.fixture.cfg,descriptorSha256=self.digest,sourceTransferSha256=m.sha(m.canonical(self.value)))
    def test_mode_scoped_claim_does_not_replace_an_uncertain_previous_mode(self):
        self.call('begin');first=wire.location(self.base,self.value['config'])
        (first/'chunk-0000').mkdir(mode=0o700)
        self.assertEqual(self.call('query')['state'],'UNCERTAIN')
        second=deepcopy(self.value);cfg=second['config'];cfg['mode']='published-v4.4-local'
        cfg['root']=str(Path(cfg['root']).parent/cfg['mode']);second['bootstrap']['config']=cfg
        second['parts']['bindingSha256']=m.sha(m.canonical(cfg))
        second['bootstrap']['partsSha256']=m.sha(m.canonical(second['parts']))
        self.assertEqual(self.call('begin',value=second)['state'],'RECEIVING')
        self.assertNotEqual(first,wire.location(self.base,cfg))
        self.assertEqual(self.call('query')['state'],'UNCERTAIN')
        self.assertEqual(c.read(first/'request.json'),self.value)

    def test_binary_install_needs_no_producer_path(self):
        final=self.send();self.assertEqual(final['state'],'SUCCEEDED')
        self.assertEqual(self.call('query'),final)
        self.folder.rename(self.folder.with_name('hidden-producer-export'))
        self.assertEqual(self.fixture.call('install',self.request())['receipt']['result']['files'],6)
        self.assertEqual(boot.check_ready(self.fixture.root,self.fixture.cfg)['files'],self.value['bootstrap']['files'])
        self.assertNotIn('folder',self.request())
    def test_duplicates_out_of_order_and_partial_claim_never_consume_new_input(self):
        self.call('begin');row=self.value['chunks'][0]
        class Unreadable:
            def read(self,*_):raise AssertionError('replayed write')
        self.assertEqual(wire.put(self.base,self.value,1,Unreadable(),lambda:None)['completedChunks'],0)
        self.call('chunk',self.chunk(row),0)
        self.assertEqual(wire.put(self.base,self.value,0,Unreadable(),lambda:None)['completedChunks'],1)
        (wire.location(self.base,self.value['config'])/'chunk-0001').mkdir(mode=0o700)
        self.assertEqual(wire.put(self.base,self.value,1,Unreadable(),lambda:None)['state'],'UNCERTAIN')
        self.assertFalse(self.fixture.root.exists())
    def test_truncated_chunk_is_failed_consumed_and_does_not_import(self):
        self.call('begin');row=self.value['chunks'][0]
        result=self.call('chunk',self.chunk(row)[:-1],0);self.assertEqual(result['state'],'FAILED')
        self.assertEqual(self.call('chunk',self.chunk(row),0),result)
        self.assertEqual(self.call('finish'),result)
        with self.assertRaisesRegex(ValueError,'not complete'):self.fixture.call('install',self.request())
        self.assertFalse(self.fixture.root.exists())
    def test_source_stage_and_assembled_part_drift_cannot_reuse_success(self):
        self.send();root=wire.location(self.base,self.value['config']);path=root/'export/parts'/self.value['parts']['parts'][0]['name']
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'assembled part changed'):self.call('query')
        with self.assertRaises(ValueError):self.fixture.call('install',self.request())
    def test_renewed_budget_reboot_or_installed_package_change_reject_before_claim(self):
        with self.assertRaisesRegex(ValueError,'deadline changed'):
            self.call('begin',budget=dict(self.fixture.budget,expiresNanos=self.fixture.budget['expiresNanos']+1))
        with patch.object(helper,'boot_identity',return_value='22222222-2222-4222-8222-222222222222'):
            with self.assertRaisesRegex(ValueError,'boot changed'):self.call('begin')
        (self.base/'padding').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.call('begin')
        self.assertFalse(wire.location(self.base,self.value['config']).exists())
    def test_wrong_config_or_digest_and_symlink_reject_before_import(self):
        self.send()
        wrong=dict(self.request(),sourceTransferSha256='0'*64)
        with self.assertRaisesRegex(ValueError,'identity'):self.fixture.call('install',wrong)
        wrong=deepcopy(self.value);wrong['config']['root']='/different'
        with self.assertRaises(ValueError):self.call('query',value=wrong)
        stage=wire.location(self.base,self.value['config']);original=stage/'request.json';original.rename(stage/'original.json');original.symlink_to(stage/'original.json')
        with self.assertRaises(ValueError):self.call('query')
        self.assertFalse(self.fixture.root.exists())
    def test_receipt_identity_drift_is_rejected(self):
        self.send();path=wire.location(self.base,self.value['config'])/'finish/receipt.json';value=c.read(path);value['requestSha256']='0'*64;path.write_bytes(m.canonical(value))
        with self.assertRaisesRegex(ValueError,'identity'):self.call('query')
    def test_forged_expanded_digest_cannot_finish_or_start_import(self):
        self.value['bootstrap']['files']['hosts.txt']['sha256']='0'*64
        result=self.send();self.assertEqual(result['state'],'FAILED')
        self.assertIn('expanded member digest',result['error']['message'])
        self.assertEqual(self.call('finish'),result);self.assertFalse(self.fixture.root.exists())
    def test_declared_file_byte_bound_is_checked_before_any_extraction(self):
        expected=deepcopy(self.value['bootstrap']['files']);name='source/'+boot.SOURCE[0];expected[name]['bytes']-=1
        target=self.fixture.fixture.root/'extract'
        with self.assertRaisesRegex(ValueError,'expected member bounds'):
            parts.unpack(self.folder/'parts',target,m.sha(m.canonical(self.fixture.cfg)),expected_members=expected)
        self.assertFalse((target/name).exists())
        forged=deepcopy(self.value);forged['bootstrap']['files']=expected
        with self.assertRaisesRegex(ValueError,'expanded inventory/bound'):wire.check_archive(self.folder,forged)
    def test_closed_inventory_size_and_chunk_metadata_fail_closed(self):
        for mutate in (
            lambda v:v['bootstrap']['files'].update({'extra':dict(bytes=1,sha256='a'*64)}),
            lambda v:v['bootstrap']['files']['hosts.txt'].update(bytes=True),
            lambda v:v['bootstrap']['files']['hosts.txt'].update(bytes=65<<20),
            lambda v:v['chunks'][0].update(offset=1),lambda v:v['chunks'][0].update(index=True),
            lambda v:v['chunks'][0].update(bytes=2<<20),lambda v:v['chunks'][0].update(sha256='bad')):
            value=deepcopy(self.value);mutate(value)
            with self.assertRaises(ValueError):wire.validate(value)
        self.assertFalse(wire.location(self.base,self.value['config']).exists())
    def endpoint(self,*,uncertain=False):
        test=self;calls=[]
        class Endpoint:
            offline=True;value=test.fixture.fixture.value
            def source(_,action,value,data,deadline,index=None):
                calls.append((action,index))
                if uncertain:
                    if len(calls)==1:return wire.envelope(value,'NOT_FOUND')
                    if action=='begin':raise ConnectionError('lost before receipt')
                    return wire.envelope(value,'UNCERTAIN')
                result=test.call(action,data,index,value)
                if action in ('begin','chunk','finish'):raise ConnectionError('lost completed response')
                return result
        return Endpoint(),calls
    def test_controller_lost_replies_query_each_mutation_without_replay(self):
        ep,calls=self.endpoint();out=self.fixture.fixture.root/'controller'
        result=delivery.Delivery().deliver(self.folder,self.digest,self.fixture.cfg,ep,time.monotonic()+20,out)
        self.assertEqual(result,self.request());count=len(self.value['chunks'])
        self.assertEqual(len(calls),2*(count+2)+1)
        self.assertEqual(sum(a=='query' for a,_ in calls),count+3)
        self.assertEqual(len(list(delivery.Delivery.retention_files(out))),count+4)
        (out/'unexpected').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'inventory'):list(delivery.Delivery.retention_files(out))
    def test_existing_begin_is_not_resumed_by_another_controller(self):
        self.call('begin');ep,calls=self.endpoint();out=self.fixture.fixture.root/'restarted-controller'
        with self.assertRaisesRegex(ValueError,'consumed'):
            delivery.Delivery().deliver(self.folder,self.digest,self.fixture.cfg,ep,time.monotonic()+10,out)
        self.assertEqual(calls,[('query',None)]);self.assertFalse((out/'intent-begin.json').exists())
    def test_unresolved_begin_keeps_original_deadline_and_intent(self):
        from .cloud_fake import Clock
        clock=Clock();ep,calls=self.endpoint(uncertain=True);out=self.fixture.fixture.root/'uncertain'
        with self.assertRaisesRegex(ValueError,'deadline|no replay'):
            delivery.Delivery(clock=clock.seconds,sleep=clock.sleep).deliver(self.folder,self.digest,self.fixture.cfg,ep,clock.seconds()+.2,out)
        self.assertEqual(sum(a=='begin' for a,_ in calls),1);self.assertTrue(all(a in ('begin','query') for a,_ in calls))
        self.assertTrue((out/'intent-begin.json').is_file());self.assertEqual(c.read(out/'receipt.json')['status'],'FAIL')
    def test_endpoint_checks_native_response_and_original_deadline(self):
        class Local(package.Endpoint):
            offline=True
            def argv(_,remote):return remote
        ep=Local(dict(instanceId='123'),self.fixture.fixture.parent,self.fixture.fixture.value)
        ep.budget=self.fixture.budget;ep.deadline=time.monotonic()+10
        answer=dict(schema='gse-v51-package-source-v1',action='query',requestSha256=m.sha(m.canonical(self.value)),
                    deadlineSha256=m.sha(m.canonical(ep.budget)),receipt=wire.envelope(self.value,'NOT_FOUND'))
        with patch.object(package.transport,'process',return_value=m.canonical(answer)):
            self.assertEqual(ep.source('query',self.value,b'',ep.deadline)['state'],'NOT_FOUND')
            with self.assertRaises(ValueError):ep.source('query',self.value,b'',ep.deadline+1)
        for key in ('action','requestSha256','deadlineSha256'):
            with patch.object(package.transport,'process',return_value=m.canonical(dict(answer,**{key:'bad'}))):
                with self.assertRaisesRegex(ValueError,'identity'):ep.source('query',self.value,b'',ep.deadline)
        ep.offline=False
        with self.assertRaisesRegex(ValueError,'scope'):ep.source('query',self.value,b'',ep.deadline)


class OwnedTransferTest(unittest.TestCase):
    def test_all_transfers_precede_any_install_and_failure_prevents_sealing(self):
        fixture=fixtures.BootstrapTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        class Delivery:
            offline=True;scope='authenticated-source-chunks'
            def deliver(_,folder,digest,cfg,ep,deadline,output):
                fixture.events.append((ep.node,'transfer'))
                if ep.node=='node-3':raise ValueError('source unavailable')
                return dict(config=cfg,descriptorSha256=digest,sourceTransferSha256='a'*64)
        fixture.bridge.delivery=Delivery()
        with self.assertRaisesRegex(ValueError,'source unavailable'):fixture.run_bootstrap()
        self.assertTrue(all(not ep.counts for ep in fixture.endpoints))
        self.assertIn(('node-2','transfer'),fixture.events)

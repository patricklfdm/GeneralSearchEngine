import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import time
import unittest
from copy import deepcopy
from unittest.mock import patch
from . import guest_package_receiver as r, guest_package_delivery as d
from . import guest_delivery_receiver as helper, cloud_package as package
from .test_cloud_package import fixture, save


class PackageDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); base = self.root/'package'; self.manifest = fixture(base)
        (base/'padding').write_bytes(os.urandom((1 << 20)+128))
        # Raw package digests and the canonical workload contract digest differ.
        (base/'workload.json').write_bytes(b'{ }\n')
        self.manifest['workloadSha256']=package.sha(b'{ }\n')
        self.manifest['files'] = package.inventory(base); save(base/'manifest.json', self.manifest)
        self.archive = self.root/'guest.tar.gz'
        with tarfile.open(self.archive, 'w:gz', format=tarfile.USTAR_FORMAT) as tar:
            for item in sorted(base.rglob('*')):
                if item.is_file():
                    raw=item.read_bytes(); info=tarfile.TarInfo(str(item.relative_to(base))); info.size=len(raw)
                    info.mode=0o755 if item.stat().st_mode & 0o111 else 0o644
                    tar.addfile(info,io.BytesIO(raw))
        binding = dict(schema='gse-v51-guest-binding-v1', source='a'*40, bundleSha256=package.sha(self.archive.read_bytes()),
                       attempt='b'*32, node='node-1', workloadSha256=package.sha(b'{}'))
        self.value = d.describe(self.archive, self.manifest, binding, dict(instanceId='123', diskId='456', attempt='b'*32, node=1), 'c'*64)
        self.parent = self.root/'installations'; self.parent.mkdir(mode=0o700)
        self.budget = self.deadline(self.value)
    def deadline(self, value):
        sample = helper.clock_sample(r.identity(value), 'd'*32)
        return dict(schema='gse-v51-helper-deadline-v1', sample=sample, expiresNanos=sample['sampledNanos']+60*10**9)
    def receive(self, value=None):
        value = value or self.value; budget = self.deadline(value)
        r.begin(self.parent,value,budget)
        with self.archive.open('rb') as stream:
            for part in value['parts']: r.put(self.parent,value,budget,part['index'],io.BytesIO(stream.read(part['bytes'])))
        return budget
    def endpoint(self):
        class Local(d.Endpoint):
            offline = True
            def argv(self, remote): return [sys.executable,*remote[1:]]
        return Local(dict(instanceId='123'),self.parent,self.value)
    def test_actual_bounded_process_transfer_and_lost_replies_are_not_replayed(self):
        endpoint = self.endpoint(); original = endpoint.exchange; lost = set()
        def exchange(action,data,deadline,index=None):
            answer = original(action,data,deadline,index)
            if action in ('begin','part','finish') and (action,index) not in lost:
                lost.add((action,index)); raise ConnectionError('discard completed reply')
            return answer
        endpoint.exchange = exchange
        answer = d.deliver(endpoint,self.archive,time.monotonic()+60)
        self.assertEqual(answer['state'],'SUCCEEDED'); self.assertGreater(len(self.value['parts']),1)
        self.assertEqual(len([v for v in endpoint.calls if v['action']=='part']),len(self.value['parts']))
        self.assertEqual(len([v for v in endpoint.calls if v['action']=='query']),len(lost))
        self.assertEqual(package.verify(Path(answer['installed']['package'])),self.manifest)
        self.assertEqual(list(self.parent.rglob('__pycache__')),[])
    def test_part_order_and_duplicate_input_are_not_consumed(self):
        r.begin(self.parent,self.value,self.budget)
        raw = self.archive.read_bytes()[:r.PART_BYTES]
        skipped = io.BytesIO(raw); self.assertEqual(r.put(self.parent,self.value,self.budget,1,skipped)['completedParts'],0)
        self.assertEqual(skipped.tell(),0)
        r.put(self.parent,self.value,self.budget,0,io.BytesIO(raw))
        duplicate = io.BytesIO(b'wrong'); self.assertEqual(r.put(self.parent,self.value,self.budget,0,duplicate)['completedParts'],1)
        self.assertEqual(duplicate.tell(),0)
    def test_truncated_part_is_terminal_and_retained(self):
        r.begin(self.parent,self.value,self.budget)
        first = r.put(self.parent,self.value,self.budget,0,io.BytesIO(b'partial'))
        self.assertEqual(first['state'],'FAILED')
        later = io.BytesIO(self.archive.read_bytes()[:r.PART_BYTES])
        self.assertEqual(r.put(self.parent,self.value,self.budget,0,later),first); self.assertEqual(later.tell(),0)
        self.assertEqual((r.location(self.parent,self.value)/'part-0000/data.bin').read_bytes(),b'partial')
    def test_claim_without_receipt_stays_uncertain(self):
        r.begin(self.parent,self.value,self.budget)
        (r.location(self.parent,self.value)/'part-0000').mkdir(mode=0o700)
        self.assertEqual(r.put(self.parent,self.value,self.budget,0,io.BytesIO(b'x'))['state'],'UNCERTAIN')
    def test_interrupted_install_is_never_restarted(self):
        budget = self.receive(); root = r.location(self.parent,self.value); (root/'install').mkdir(mode=0o700)
        with patch.object(package,'unpack',side_effect=AssertionError('must not unpack')):
            self.assertEqual(r.finish(self.parent,self.value,budget)['state'],'UNCERTAIN')
        with self.assertRaises(FileNotFoundError): r.installed(self.parent,self.value)
    def test_whole_digest_rejected_before_archive_parser(self):
        value = deepcopy(self.value); value['binding']['bundleSha256']='e'*64; budget=self.receive(value)
        with patch.object(package,'unpack',side_effect=AssertionError('must not unpack')):
            answer = r.finish(self.parent,value,budget)
        self.assertEqual(answer['state'],'FAILED'); self.assertIn('complete archive digest',answer['error']['message'])
    def test_manifest_build_and_workload_must_match_descriptor(self):
        for key in ('manifestSha256','buildManifestSha256','workloadSha256'):
            with self.subTest(key=key):
                value=deepcopy(self.value); value['binding']['attempt']=package.sha(key.encode())[:32]
                (value['binding'] if key=='workloadSha256' else value)[key]='e'*64
                budget=self.receive(value); answer=r.finish(self.parent,value,budget)
                self.assertEqual(answer['state'],'FAILED'); self.assertIn('manifest/build/workload',answer['error']['message'])
                with self.assertRaises(ValueError): r.installed(self.parent,value)
    def test_install_tampering_blocks_service_before_payload_import(self):
        budget=self.receive(); answer=r.finish(self.parent,self.value,budget); base=Path(answer['installed']['package'])
        (base/'guest.py').write_text('raise RuntimeError("must not execute")')
        with self.assertRaisesRegex(ValueError,'inventory'):
            r.service(self.parent,self.value,'invalid-token',['start'])
    def test_service_after_transfer_deadline_but_not_reboot(self):
        budget=self.receive(); r.finish(self.parent,self.value,budget)
        with patch.object(helper.time,'monotonic_ns',return_value=budget['expiresNanos']+1):
            self.assertTrue(r.installed(self.parent,self.value).is_dir())
            with self.assertRaisesRegex(ValueError,'deadline'): r.query(self.parent,self.value,budget)
        with patch.object(helper,'boot_identity',return_value='00000000-0000-0000-0000-000000000000'):
            with self.assertRaisesRegex(ValueError,'boot changed'): r.installed(self.parent,self.value)
    def test_deadline_and_descriptor_cannot_change(self):
        r.begin(self.parent,self.value,self.budget); changed=deepcopy(self.budget); changed['expiresNanos']+=1
        with self.assertRaisesRegex(ValueError,'deadline changed'): r.query(self.parent,self.value,changed)
        value=deepcopy(self.value); value['diskId']='789'
        with self.assertRaisesRegex(ValueError,'deadline changed'): r.query(self.parent,value,self.deadline(value))
    def test_corrupted_retained_part_and_linked_destination_rejected(self):
        budget=self.receive(); root=r.location(self.parent,self.value); (root/'part-0000/data.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'part changed'): r.finish(self.parent,self.value,budget)
        linked=self.root/'linked'; linked.symlink_to(self.parent)
        with self.assertRaisesRegex(ValueError,'linked parent'): r.begin(linked,self.value,budget)
    def test_metadata_bound_and_live_endpoint_closed(self):
        for changed in ({'archiveBytes':package.MAX_BYTES+1},{'parts':[]},{'archiveBytes':True}):
            with self.assertRaises(ValueError): r.descriptor(dict(self.value,**changed))
        endpoint=d.Endpoint(dict(instanceId='123'),self.parent,self.value)
        with self.assertRaisesRegex(ValueError,'live package delivery disabled'): d.deliver(endpoint,self.archive,time.monotonic()+10)
    def test_uncertain_write_expires_with_queries_only(self):
        value=self.value; calls=[]
        class Missing:
            offline=True
            def __init__(self): self.value=value
            def exchange(self,action,data,deadline,index=None):
                calls.append(action)
                if action=='begin': raise ConnectionError('lost before receipt')
                return r.envelope(value,'UNCERTAIN')
        with self.assertRaisesRegex(ValueError,'unresolved; no replay'):
            d.deliver(Missing(),self.archive,time.monotonic()+.12)
        self.assertEqual(calls.count('begin'),1); self.assertTrue(all(v=='query' for v in calls[1:]))


if __name__=='__main__': unittest.main()

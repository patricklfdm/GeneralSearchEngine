import base64
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from . import measurement_trace as trace,measurement_verified as v,measurement_bundle as bundle,measurement_stream as mutations
from .test_measurement_trace import fixture
from .evidence import encoded


def inputs(root):
    root.mkdir()
    for i in (1,2,3):
        node='node-'+str(i)
        rows=[dict(node=node,pid=50+i,generation=1,order=n,localNanos=n,event='TEST',groupId='fixture',
                   manifestDigest='a'*64,payload={'value':'x'*9000}) for n in (1,2)]
        path,_,_=fixture(root,rows)
        if i!=1:
            path.rename(root/(node+'-trace.jsonl'));path.with_name(path.name+'.chunks').rename(root/(node+'-trace.jsonl.chunks'))
        else:
            path.rename(root/'saved');path.with_name(path.name+'.chunks').rename(root/'saved-chunks')
    (root/'saved').rename(root/'node-1-trace.jsonl');(root/'saved-chunks').rename(root/'node-1-trace.jsonl.chunks')
    (root/bundle.INDEX).write_bytes(encoded(bundle.members(root))+b'\n')


class MeasurementVerifiedTest(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_lossless_bounded_repetition_nested_iterators_and_mutation_isolation(self):
        path,_,raw=fixture(self.root);source=trace.Trace(path,node='node-1');cached=v.VerifiedTrace(source,self.root)
        try:
            expected=[json.loads(r) for r in raw];self.assertEqual(expected,list(cached));self.assertEqual(source.stats,cached.stats)
            left=iter(cached);first=next(left);first['payload']='changed'
            self.assertEqual(expected,list(cached));self.assertEqual(expected[1:],list(left));cached.verify()
            self.assertEqual(sum(map(len,raw))+v.HEADER*len(raw),cached.size)
        finally:cached.close()
        with self.assertRaisesRegex(ValueError,'closed'):next(iter(cached))

    def test_original_trace_budgets_apply_before_any_cached_row(self):
        path,refs,_=fixture(self.root)
        for limits in (replace(trace.Limits(),rows=1),replace(trace.Limits(),decoded_bytes=refs[0]['bytes']),
                       replace(trace.Limits(),raw_line=1),replace(trace.Limits(),chunk_bytes=1)):
            with self.subTest(limits=limits),self.assertRaises(ValueError):v.VerifiedTrace(trace.Trace(path,node='node-1',limits=limits),self.root)

    def test_duplicate_json_is_not_accepted_by_trusted_replay_parser(self):
        rows=[dict(node='node-1',pid=52,generation=1,order=1,localNanos=1,event='TEST',groupId='fixture',manifestDigest='a'*64)]
        path,refs,raw=fixture(self.root,rows);altered=raw[0].replace(b'{',b'{"event":"TEST",',1)
        refs[0].update(bytes=len(altered),sha256=hashlib.sha256(altered).hexdigest(),inline=base64.b64encode(altered).decode())
        path.write_bytes(encoded(refs[0])+b'\n')
        with self.assertRaisesRegex(ValueError,'duplicate JSON'):v.VerifiedTrace(trace.Trace(path,node='node-1'),self.root)

    def test_private_spool_corruption_truncation_and_forged_digest_are_rejected(self):
        path,_,_=fixture(self.root)
        for kind in ('row','bound','truncated','forged'):
            cached=v.VerifiedTrace(trace.Trace(path,node='node-1'),self.root)
            try:
                fd=cached.file.fileno()
                if kind=='row':os.pwrite(fd,b'x',v.HEADER)
                if kind=='bound':os.pwrite(fd,struct.pack('>I',cached.limits.raw_line+1),0)
                if kind=='truncated':os.ftruncate(fd,5)
                if kind=='forged':
                    header=cached.read(0,v.HEADER);size=struct.unpack('>I',header[:4])[0]
                    raw=cached.read(v.HEADER,size).replace(b'abcdefghijklmnopqrstuvwxyz',b'zyxwvutsrqponmlkjihgfedcba')
                    os.pwrite(fd,header[:4]+hashlib.sha256(raw).digest()+raw,0)
                with self.subTest(kind=kind),self.assertRaises(ValueError):list(cached)
                with self.assertRaises(ValueError):cached.verify()
            finally:cached.close()

    def test_original_change_after_materialization_rejects_even_after_partial_iteration(self):
        root=self.root/'input';output=self.root/'output';output.mkdir();inputs(root)
        with self.assertRaisesRegex(ValueError,'inventory/hash differs'):
            with v.traces(root,output) as cached:
                next(iter(cached['node-1']))
                path=next((root/'node-1-trace.jsonl.chunks').glob('*.bin'));path.write_bytes(b'z'*path.stat().st_size)
        self.assertEqual([],list(output.iterdir()))

    def test_negative_view_changes_only_original_target_with_no_stale_row_reuse(self):
        root=self.root/'input';output=self.root/'output';output.mkdir();inputs(root)
        with v.traces(root,output) as cached:
            changed=mutations.changed(cached,lambda r:r['node']=='node-1' and r['order']==1,lambda r:dict(r,event='INVALID'))
            for _ in range(2):
                self.assertEqual(['INVALID','TEST'],[r['event'] for r in changed['node-1']])
                self.assertEqual(['TEST','TEST'],[r['event'] for r in cached['node-1']])
        self.assertEqual([],list(output.iterdir()))

    def test_cleanup_and_no_original_mutation_on_validation_failure(self):
        root=self.root/'input';output=self.root/'output';output.mkdir();inputs(root);original=bundle.inventory(root)
        with self.assertRaisesRegex(ValueError,'semantic failure'):
            with v.traces(root,output) as cached:raise ValueError('semantic failure')
        self.assertEqual(original,bundle.inventory(root));self.assertEqual([],list(output.iterdir()))
        with self.assertRaisesRegex(ValueError,'overlaps input'):
            with v.traces(root,root/'cache'):pass


if __name__=='__main__':unittest.main()

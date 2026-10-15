"""Independent format negatives, including reconstruction budgets and relocation."""
import base64
from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest
from . import measurement_trace as t
from .evidence import encoded,digest


def fixture(root,rows=None):
    path=Path(root)/'node-1-trace.jsonl';directory=path.with_name(path.name+'.chunks');directory.mkdir()
    rows=rows or [dict(node='node-1',pid=52,generation=1,order=i,localNanos=100+i,event='TEST',groupId='fixture',
                      manifestDigest='a'*64,payload=('abcdefghijklmnopqrstuvwxyz'*1800)+str(i)) for i in range(1,4)]
    refs=[];original=[]
    for row in rows:
        raw=encoded(row)+b'\n';original.append(raw)
        ref={k:row[k] for k in t.META};ref.update(encoding=t.SCHEMA,bytes=len(raw),sha256=digest(raw))
        if len(raw)<=t.INLINE:ref['inline']=base64.b64encode(raw).decode()
        else:
            pieces=[]
            for offset in range(0,len(raw),t.CHUNK):
                part=raw[offset:offset+t.CHUNK];key=digest(part);(directory/(key+'.bin')).write_bytes(part);pieces.append(key)
            ref['pieces']=pieces
        refs.append(ref)
    path.write_bytes(b''.join(encoded(ref)+b'\n' for ref in refs));return path,refs,original


class MeasurementTraceTest(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def read(self,path,**kw):return t.Trace(path,node='node-1',**kw)
    def mutate(self,path,refs):path.write_bytes(b''.join(encoded(ref)+b'\n' for ref in refs))

    def test_exact_bytes_streaming_repeated_iteration_and_relocation(self):
        path,_,original=fixture(self.root);reader=self.read(path)
        self.assertEqual(original,list(reader.raw_rows()));self.assertEqual(original,list(reader.raw_rows()))
        self.assertLess(reader.stats['chunkBytes'],reader.stats['decodedBytes']//2)
        copy=self.root/'relocated';copy.mkdir();shutil.copyfile(path,copy/path.name)
        shutil.copytree(reader.directory,copy/reader.directory.name)
        self.assertEqual(original,list(self.read(copy/path.name).raw_rows()))

    def test_missing_corrupt_and_uninventoried_chunk_cannot_be_hidden(self):
        path,_,_=fixture(self.root);reader=self.read(path);member=next(reader.directory.glob('*.bin'));raw=member.read_bytes()
        member.unlink()
        with self.assertRaises(ValueError):reader.verify()
        member.write_bytes(b'x'*len(raw))
        with self.assertRaisesRegex(ValueError,'digest'):self.read(path)
        member.write_bytes(raw);(reader.directory/'not-a-chunk').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'type/name'):self.read(path)

    def test_reference_digest_and_metadata_must_match_reconstructed_row(self):
        path,refs,_=fixture(self.root);refs[0]['sha256']='b'*64;self.mutate(path,refs)
        with self.assertRaisesRegex(ValueError,'row digest'):self.read(path).verify()
        path.unlink();shutil.rmtree(path.with_name(path.name+'.chunks'));path,refs,_=fixture(self.root)
        refs[0]['pid']+=1;self.mutate(path,refs)
        with self.assertRaisesRegex(ValueError,'metadata'):self.read(path).verify()

    def test_chunks_cannot_escape_directory_or_change_order(self):
        path,refs,_=fixture(self.root);refs[0]['pieces'][0]='../escape';self.mutate(path,refs)
        with self.assertRaisesRegex(ValueError,'invalid chunk'):self.read(path).verify()
        path.unlink();shutil.rmtree(path.with_name(path.name+'.chunks'));path,refs,_=fixture(self.root)
        refs[0]['pieces'][0],refs[0]['pieces'][1]=refs[0]['pieces'][1],refs[0]['pieces'][0];self.mutate(path,refs)
        with self.assertRaisesRegex(ValueError,'row digest'):self.read(path).verify()

    def test_decoded_limit_checks_before_reconstruction_and_both_storage_limits(self):
        path,refs,_=fixture(self.root)
        for limits,reason in ((replace(t.Limits(),decoded_bytes=refs[0]['bytes']-1),'decoded total'),
                              (replace(t.Limits(),raw_line=refs[0]['bytes']-1),'decoded row'),
                              (replace(t.Limits(),encoded_bytes=1),'encoded trace'),
                              (replace(t.Limits(),encoded_line=1),'reference line'),
                              (replace(t.Limits(),chunk_bytes=1),'stored chunk'),
                              (replace(t.Limits(),chunks=1),'chunk count'),(replace(t.Limits(),rows=1),'reference total')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):self.read(path,limits=limits).verify()

    def test_pending_partial_and_duplicate_reference_are_not_completed_silently(self):
        path,refs,_=fixture(self.root);path.with_name(path.name+'.pending').write_bytes(b'pending')
        with self.assertRaisesRegex(ValueError,'unfinished'):self.read(path)
        path.with_name(path.name+'.pending').unlink();path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError,'completeness'):self.read(path).verify()
        self.mutate(path,[refs[0],*refs])
        with self.assertRaisesRegex(ValueError,'observation order'):self.read(path).verify()

    def test_symlinked_chunk_and_duplicate_json_are_rejected(self):
        path,refs,_=fixture(self.root);directory=path.with_name(path.name+'.chunks');member=next(directory.glob('*.bin'))
        backup=self.root/'backup';member.rename(backup);member.symlink_to(backup)
        with self.assertRaisesRegex(ValueError,'type/name'):self.read(path)
        member.unlink();backup.rename(member)
        raw=path.read_bytes();path.write_bytes(raw.replace(b'{',b'{"bytes":1,',1))
        with self.assertRaisesRegex(ValueError,'duplicate JSON'):self.read(path).verify()

    def test_inline_small_rows_and_restart_keep_original_identity(self):
        rows=[dict(node='node-1',pid=50+g,generation=g,order=i,localNanos=100+i,event='SMALL',groupId='fixture',manifestDigest='a'*64)
              for g in (1,2) for i in (1,2)]
        path,refs,raw=fixture(self.root,rows);reader=self.read(path)
        self.assertTrue(all('inline' in ref for ref in refs));self.assertEqual(raw,list(reader.raw_rows()));self.assertEqual(2,reader.stats['processGenerations'])
        rows[-1]['pid']=51;path.unlink();shutil.rmtree(reader.directory);path,_,_=fixture(self.root,rows)
        with self.assertRaisesRegex(ValueError,'generation reuse'):self.read(path).verify()

    def test_unreferenced_complete_chunks_are_accounted_not_authority(self):
        path,_,_=fixture(self.root);directory=path.with_name(path.name+'.chunks');raw=b'interrupted observation, not a row'
        (directory/(digest(raw)+'.bin')).write_bytes(raw)
        result=self.read(path).verify();self.assertEqual(1,result['unreferencedChunks']);self.assertEqual(3,result['rows'])

    def test_complete_rows_cannot_borrow_another_authority_or_skip_a_generation(self):
        for change,reason in ((dict(groupId='other'),'authority changed'),(dict(generation=3,pid=53,order=1),'generation reuse')):
            directory=self.root/reason.replace(' ','-');directory.mkdir()
            rows=[dict(node='node-1',pid=52,generation=1,order=i,localNanos=100+i,event='TEST',groupId='fixture',manifestDigest='a'*64) for i in (1,2)]
            rows[1].update(change);path,_,_=fixture(directory,rows)
            with self.assertRaisesRegex(ValueError,reason):self.read(path).verify()


if __name__=='__main__':unittest.main()

import copy
import gzip
import hashlib
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from . import remote_collection as c, remote_command as r, performance_model as m


class RemoteCollectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root/'raw'
        self.raw.mkdir()
        (self.raw/'trace.jsonl').write_text('{"raw":true}\n')
        (self.raw/'data').mkdir()
        (self.raw/'data/authority.bin').write_bytes(bytes(range(256))*64)
        self.binding = 'a'*64

    def pack(self):
        return c.pack(self.raw,self.root/'parts',self.binding)

    def test_binary_roundtrip_and_complete_inventory(self):
        manifest = self.pack()
        downloaded = self.root/'downloaded'
        downloaded.mkdir()
        for part in manifest['parts']:
            with (self.root/'parts'/part['name']).open('rb') as stream:
                c.receive_part(downloaded,part,iter(lambda:stream.read(1024),b''))
        r.write_once(downloaded/'parts.json',manifest)
        result = c.unpack(downloaded,self.root/'unpacked',self.binding)
        self.assertEqual('PASS',result['status'])
        self.assertEqual(2,result['files'])
        self.assertEqual((self.raw/'data/authority.bin').read_bytes(),(self.root/'unpacked/data/authority.bin').read_bytes())

    def test_actual_incompressible_stream_crosses_eight_mib_part_boundary(self):
        (self.raw/'random.bin').write_bytes(os.urandom((8<<20)+1024))
        manifest = self.pack()
        self.assertEqual(2,len(manifest['parts']))
        self.assertEqual(8<<20,manifest['parts'][0]['bytes'])
        self.assertEqual('PASS',c.unpack(self.root/'parts',self.root/'unpacked',self.binding)['status'])

    def test_interrupted_download_retains_partial_and_never_seals(self):
        manifest = self.pack()
        output = self.root/'interrupted'
        output.mkdir()
        part = manifest['parts'][0]
        raw = (self.root/'parts'/part['name']).read_bytes()
        def broken():
            yield raw[:10]
            raise ConnectionError('upload interrupted')
        with self.assertRaises(ConnectionError): c.receive_part(output,part,broken())
        self.assertEqual(raw[:10],(output/(part['name']+'.partial')).read_bytes())
        self.assertFalse((output/part['name']).exists())
        with self.assertRaises(FileExistsError): c.receive_part(output,part,[raw])
        retry = self.root/'fresh-download'
        retry.mkdir()
        c.receive_part(retry,part,[raw])
        self.assertEqual(raw,(retry/part['name']).read_bytes())

    def test_truncation_overflow_corruption_and_oversize_binary_blocks(self):
        manifest = self.pack()
        part = manifest['parts'][0]
        raw = (self.root/'parts'/part['name']).read_bytes()
        for i, chunks in enumerate(([raw[:-1]],[raw+b'x'],[b'x'+raw[1:]],[b'x'*((1<<20)+1)])):
            output = self.root/str(i)
            output.mkdir()
            with self.subTest(i=i),self.assertRaises(ValueError): c.receive_part(output,part,chunks)
            self.assertFalse((output/part['name']).exists())

    def test_wrong_attempt_missing_extra_and_changed_parts_rejected(self):
        manifest = self.pack()
        with self.assertRaises(ValueError): c.unpack(self.root/'parts',self.root/'wrong','b'*64)
        extra = self.root/'parts/extra.bin'
        extra.write_bytes(b'extra')
        with self.assertRaises(ValueError): c.unpack(self.root/'parts',self.root/'extra',self.binding)
        extra.unlink()
        path = self.root/'parts'/manifest['parts'][0]['name']
        original = path.read_bytes()
        path.write_bytes(b'x'+original[1:])
        with self.assertRaises(ValueError): c.unpack(self.root/'parts',self.root/'corrupt',self.binding)
        path.unlink()
        with self.assertRaises(ValueError): c.unpack(self.root/'parts',self.root/'missing',self.binding)

    def test_manifest_boundaries_and_malicious_part_names(self):
        good = self.pack()
        for patch_value in ({'name':'../outside'}, {'name':'/outside'}, {'name':'part-0001.bin'},
                            {'bytes':0}, {'bytes':(8<<20)+1}, {'sha256':'bad'}):
            bad = copy.deepcopy(good)
            bad['parts'][0].update(patch_value)
            with self.subTest(patch=patch_value),self.assertRaises(ValueError): c.validate_manifest(bad,self.binding)
        for change in ({'parts':[]},{'parts':good['parts']*257},{'compressedBytes':0},{'workloadSha256':'0'*64}):
            with self.subTest(change=change),self.assertRaises(ValueError): c.validate_manifest(dict(good,**change),self.binding)

    def test_exact_two_gib_manifest_bound_and_writer_guard(self):
        good = self.pack()
        parts = [dict(name=f'part-{i:04d}.bin',bytes=8<<20,sha256='a'*64) for i in range(256)]
        c.validate_manifest(dict(good,parts=parts,compressedBytes=2<<30),self.binding)
        directory = self.root/'writer'
        directory.mkdir()
        writer = c.PartWriter(directory)
        writer.total = 2<<30
        with self.assertRaises(ValueError): writer.write(b'x')
        self.assertEqual([],list(directory.iterdir()))

    def test_input_symlink_fifo_reserved_path_and_oversized_member_rejected(self):
        link = self.raw/'link'
        link.symlink_to(self.raw/'trace.jsonl')
        with self.assertRaises(ValueError): c.inventory(self.raw)
        link.unlink()
        os.mkfifo(link)
        with self.assertRaises(ValueError): c.inventory(self.raw)
        link.unlink()
        (self.raw/c.INDEX).write_text('{}')
        with self.assertRaises(ValueError): c.inventory(self.raw)
        (self.raw/c.INDEX).unlink()
        with (self.raw/'sparse.bin').open('wb') as stream: stream.truncate((32<<20)+1)
        with self.assertRaises(ValueError): c.inventory(self.raw)

    def malicious_archive(self, entries, suffix):
        output = self.root/('bad-parts-'+suffix)
        output.mkdir()
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw,mode='w:gz') as archive:
            for name, data, kind in entries:
                info = tarfile.TarInfo(name)
                info.type = kind
                info.size = len(data)
                if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE): info.linkname = '../outside'
                archive.addfile(info,io.BytesIO(data))
        content = raw.getvalue()
        (output/'part-0000.bin').write_bytes(content)
        manifest = dict(schema='gse-v51-binary-evidence-v1',bindingSha256=self.binding,
                        workloadSha256=c.contract.PLAN_SHA256,memberIndexSha256=m.sha(b'{}\n'),
                        parts=[dict(name='part-0000.bin',bytes=len(content),sha256=m.sha(content))],compressedBytes=len(content))
        r.write_once(output/'parts.json',manifest)
        return output

    def test_resealed_unsafe_duplicate_link_and_missing_inventory_rejected(self):
        cases = [[(name,b'x',tarfile.REGTYPE)] for name in ('../outside','/absolute','a/../outside','./a','a//b','back\\slash')]
        cases += [[('link',b'',kind)] for kind in (tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.DIRTYPE,tarfile.FIFOTYPE)]
        cases += [[('same',b'a',tarfile.REGTYPE),('same',b'b',tarfile.REGTYPE)], [('normal',b'x',tarfile.REGTYPE)]]
        for i,entries in enumerate(cases):
            parts = self.malicious_archive(entries,str(i))
            with self.subTest(entries=entries),self.assertRaises(ValueError): c.unpack(parts,self.root/f'extract-{i}',self.binding)
        self.assertFalse((self.root/'outside').exists())

    def test_resealed_inventory_omission_rejected(self):
        entries = [('extra',b'not-indexed',tarfile.REGTYPE),(c.INDEX,b'{}\n',tarfile.REGTYPE)]
        parts = self.malicious_archive(entries,'omission')
        with self.assertRaisesRegex(ValueError,'inventory differs'): c.unpack(parts,self.root/'extracted',self.binding)

    def test_output_must_be_fresh_and_outside_raw(self):
        with self.assertRaises(ValueError): c.pack(self.raw,self.raw/'parts',self.binding)
        self.pack()
        with self.assertRaises(FileExistsError): self.pack()
        alias = self.root/'alias'
        alias.symlink_to(self.raw,target_is_directory=True)
        with self.assertRaises(ValueError): c.pack(alias,self.root/'new',self.binding)

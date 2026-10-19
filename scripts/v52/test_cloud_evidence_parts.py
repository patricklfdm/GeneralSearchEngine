from copy import deepcopy
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_evidence_parts as p
from .test_cloud_authority import fixture


class PartsTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.request=fixture(domain='native');self.paths={}
        for name,raw in [('authority.json',b'{"original":true}'),('histories/original.tar.gz',b'original bytes'*5)]:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);self.paths[name]=path
        self.small=patch.object(p,'PIECE',32);self.small.start();self.addCleanup(self.small.stop)
        self.manifest=p.scan(self.paths,self.request);self.chunks=dict(p.chunks(self.paths,self.manifest))
    def test_round_trip_preserves_every_original_byte_and_uses_only_selected_chunks(self):
        result=p.restore(self.manifest,self.request,self.chunks.__getitem__,self.root/'restored')
        self.assertEqual(4,len(self.chunks))
        for name,path in self.paths.items():self.assertEqual(path.read_bytes(),(result/name).read_bytes())
        with self.assertRaises(FileExistsError):p.restore(self.manifest,self.request,self.chunks.__getitem__,result)
    def test_missing_or_extra_coverage_duplicate_files_and_noninteger_sizes_reject(self):
        changes=[lambda m:m['parts'].pop(),lambda m:m['parts'].append(m['parts'][-1]),
            lambda m:m['files'].append(m['files'][0]),lambda m:m['files'][1].update(firstPart=0),
            lambda m:m['files'][0].update(bytes=True),lambda m:m.update(totalBytes=0),lambda m:m['parts'][0].update(ordinal=1)]
        for change in changes:
            bad=deepcopy(self.manifest);change(bad)
            with self.assertRaises(ValueError):p.validate(bad,self.request)
    def test_other_request_or_manifest_chunk_cannot_splice_into_original(self):
        for change in (lambda v:v.update(requestSha256='a'*64),lambda v:v.update(manifestSha256='b'*64),
                       lambda v:v.update(ordinal=1),lambda v:v.update(data='A'*len(v['data']))):
            bad=deepcopy(self.chunks[0]);change(bad)
            with self.assertRaises(ValueError):p.decode(bad,self.manifest,0)
        with self.assertRaises(ValueError):p.validate(self.manifest,fixture(attempt='d'*32,domain='native'))
    def test_unsafe_file_names_and_directory_collision_reject(self):
        for name in ('../escape','/absolute','a/../b','x\\y'):
            bad=deepcopy(self.manifest);bad['files'][0]['name']=name
            with self.assertRaises(ValueError):p.validate(bad,self.request)
        bad=deepcopy(self.manifest);bad['files'][0]['name']='histories'
        with self.assertRaisesRegex(ValueError,'collision'):p.validate(bad,self.request)
    def test_truncated_changed_and_appended_original_files_fail_before_certificate(self):
        path=self.paths['histories/original.tar.gz'];original=path.read_bytes()
        for raw in (original[:-1],b'x'*len(original),original+b'x'):
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'changed'):list(p.chunks(self.paths,self.manifest))
    def test_links_hardlinks_and_empty_files_are_not_original_evidence(self):
        path=self.root/'linked';path.symlink_to(self.paths['authority.json'])
        with self.assertRaisesRegex(ValueError,'regular'):p.scan({'linked':path},self.request)
        path.unlink();os.link(self.paths['authority.json'],path)
        with self.assertRaisesRegex(ValueError,'regular'):p.scan({'linked':path},self.request)
        path.unlink();path.write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'regular'):p.scan({'linked':path},self.request)
    def test_manifest_and_data_bounds_fail_before_unbounded_decode_or_restore(self):
        bad=deepcopy(self.manifest);bad['files'][0]['bytes']=1<<50
        with self.assertRaises(ValueError):p.validate(bad,self.request)
        bad=deepcopy(self.chunks[0]);bad['data']='A'*1000
        with patch.object(p.base64,'b64decode') as decode,self.assertRaisesRegex(ValueError,'bound'):
            p.decode(bad,self.manifest,0)
        decode.assert_not_called()
    def test_missing_part_does_not_silently_publish_a_complete_restore(self):
        del self.chunks[1]
        with self.assertRaises(KeyError):p.restore(self.manifest,self.request,self.chunks.__getitem__,self.root/'partial')
        self.assertFalse((self.root/'partial/receipt.json').exists())


if __name__=='__main__':unittest.main()

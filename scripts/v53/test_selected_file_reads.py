"""Select names before payloads without weakening original-file qualification."""
from collections.abc import Mapping
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from . import physical_snapshot as physical
from . import round_storage_evidence as disk
from .test_current_generation_evidence import fixture
from . import test_joining_publication_evidence as publication_fixture


class Guarded(Mapping):
    def __init__(self,values,forbidden):self.values=values;self.forbidden=set(forbidden);self.reads=[]
    def __len__(self):return len(self.values)
    def __iter__(self):return iter(self.values)
    def __getitem__(self,name):
        if name in self.forbidden:raise AssertionError('unrelated payload materialized: '+name)
        self.reads.append(name);return self.values[name]


class SelectedFileReadsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'replica'
        fixture(self.root)

    def test_current_generation_reads_only_selected_member_payloads(self):
        original=disk.inventory(self.root);expected=disk.current(original)
        ignored={name for name in original if name!='selector.gsr' and not name.startswith('generations/a/')}
        files=Guarded(original,ignored)
        self.assertEqual(expected,disk.current(files))
        self.assertTrue(files.reads);self.assertFalse(set(files.reads)&ignored)

    def test_selected_content_and_unread_original_mutations_still_fail(self):
        model=SimpleNamespace(bootstrap_source='VERIFIED_DURABLE_BACKUP',wire_layout='SEGMENTED_BACKUP')
        (self.root/'unrelated').write_bytes(b'original')
        files=physical.from_model(self.root,model);disk.current(files)
        (self.root/'unrelated').write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError,'changed'):files.check_unchanged()
        image=next((self.root/'generations/a').glob('*.image'));image.write_bytes(b'changed image')
        with self.assertRaisesRegex(ValueError,'round original generation inventory'):
            disk.current(physical.from_model(self.root,model))

    def test_current_projection_of768MiB_snapshot_under64MiB_address_space(self):
        for number in range(12):
            with (self.root/f'unrelated-{number}').open('wb') as output:output.truncate(64*1024**2)
        code='''import json,resource,sys
from pathlib import Path
from types import SimpleNamespace
from scripts.v53 import physical_snapshot as p,round_storage_evidence as d
resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2))
files=p.from_model(Path(sys.argv[1]),SimpleNamespace(bootstrap_source='VERIFIED_DURABLE_BACKUP',wire_layout='SEGMENTED_BACKUP'))
prefix,members,packet=d.current(files)
assert prefix=='generations/a/' and packet['images'] and files.total_bytes>768*1024**2
files.check_unchanged()
print(json.dumps(dict(status='PASS',inputBytes=files.total_bytes,addressSpaceLimit=64*1024**2,peakRssKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,synthetic=True)))
'''
        result=subprocess.run([sys.executable,'-c',code,str(self.root)],text=True,capture_output=True,timeout=90)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual('PASS',json.loads(result.stdout)['status'])

    def test_checkpoint_receipts_do_not_load_unrelated_local_images(self):
        probe={}
        def change(replay,local,contents):
            local.update({'applied-end/application.image':b'not-a-checkpoint','generations/a/application.image':b'not-an-ack'})
            probe['files']=Guarded(local,{'applied-end/application.image','generations/a/application.image'})
            replay.owner=lambda *args:probe['files']
        _,_,receipts=publication_fixture.JoiningPublicationEvidenceTest().collected(change=change)
        self.assertEqual(1,receipts.transfers)
        self.assertEqual(['applied-end/ack.gsr'],probe['files'].reads)

    def test_checkpoint_receipts_do_not_assemble_non_record_transfers(self):
        probe={}
        def change(replay,local,contents):
            probe['transfer']=Guarded(dict(contents[0],kind='APPLICATION',raw=b'not-a-checkpoint'),{'raw'})
            contents.append(probe['transfer'])
        _,_,receipts=publication_fixture.JoiningPublicationEvidenceTest().collected(change=change)
        self.assertEqual(1,receipts.transfers)
        self.assertNotIn('raw',probe['transfer'].reads)


if __name__=='__main__':unittest.main()

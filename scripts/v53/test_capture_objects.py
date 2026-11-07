"""Streaming pools do not change independent prefix derivation or rejection."""
import copy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from . import capture_objects as c
from . import joining_source_retirement as retirement
from . import publication_resource_evidence as publication
from . import publication_resource_negatives as negatives
from . import joining_retirement_replay as retirement_replay
from . import test_publication_resource_evidence as publication_fixture
from . import test_joining_source_retirement as retirement_fixture

OPTIONS=dict(bootstrap_source=c.policy.BACKUP,wire_layout=c.policy.SEGMENTED)


class CaptureObjectsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def pool(self,raw=b'original'):
        digest=hashlib.sha256(raw).hexdigest();(self.root/digest).write_bytes(raw)
        return c.Pool(self.root,**OPTIONS),digest

    def test_shared_prefixes_are_deferred_readonly_and_exact(self):
        pool,digest=self.pool();view=pool.view({'directory':None,'directory/file':digest})
        self.assertEqual({'directory':None,'directory/file':b'original'},view)
        self.assertEqual(view,{'directory':None,'directory/file':b'original'})
        self.assertNotEqual(view,{'directory':None,'directory/file':b'changed'})
        self.assertIs(view,copy.deepcopy(view));self.assertIs(pool,pool.view({'again':digest}).pool)
        with self.assertRaises(TypeError):view['new']=b'new'
        metadata=view.identities();metadata['directory/file']['sha256']='0'*64
        self.assertEqual(digest,view.identities()['directory/file']['sha256'])
        self.assertTrue(all(type(v) is int for v in pool._sizes.values()))
        self.assertTrue(all(v is None or type(v) is str for v in view._names.values()))

    def test_changes_after_collection_and_unread_pool_objects_are_rejected(self):
        pool,digest=self.pool();view=pool.view({'file':digest})
        (self.root/digest).write_bytes(b'altered!')
        for check in (lambda:view['file'],view.identities,view.check_unchanged,pool.check_unchanged,
                      lambda:view=={'file':b'original'}):
            with self.assertRaisesRegex(ValueError,'changed'):check()
        (self.root/digest).write_bytes(b'original');pool=c.Pool(self.root,**OPTIONS)
        (self.root/hashlib.sha256(b'new').hexdigest()).write_bytes(b'new')
        with self.assertRaisesRegex(ValueError,'changed'):pool.check_unchanged()

    def test_retirement_comparison_preserves_the_oracles_bytes_extent_field(self):
        pool,digest=self.pool();files=pool.view({'directory':None,'directory/file':digest})
        state={'directory':dict(directory=True),'directory/file':dict(bytes=8,sha256=digest)}
        transaction=dict(steps=[dict(point='SOURCE_RETIREMENT_CREATED',files=files)])
        with patch.object(retirement.release,'transaction',return_value=[('SOURCE_RETIREMENT_CREATED',state)]):
            self.assertEqual(1,retirement.compare(transaction,{},b'',b'','fixture'))
        state['directory/file']['bytes']=9
        with patch.object(retirement.release,'transaction',return_value=[('SOURCE_RETIREMENT_CREATED',state)]):
            with self.assertRaisesRegex(ValueError,'exact prefix'):retirement.compare(transaction,{},b'',b'','fixture')

    def test_explicit_policy_precedes_io_and_pool_bounds_remain(self):
        with patch.object(c.physical,'Snapshot') as opened:
            for source,layout in [('EMPTY','JSON'),('EMPTY','SEGMENTED_BACKUP'),(c.policy.BACKUP,'JSON')]:
                with self.assertRaises(ValueError):c.Pool(self.root,bootstrap_source=source,wire_layout=layout)
            opened.assert_not_called()
        pool,digest=self.pool()
        with patch.object(c.policy,'ORIGINAL_BYTES',1),self.assertRaisesRegex(ValueError,'byte capacity'):c.Pool(self.root,**OPTIONS)
        with patch.object(c,'SNAPSHOT_BYTES',15),self.assertRaisesRegex(ValueError,'prefix byte capacity'):
            pool.view({'first':digest,'second':digest})
        (self.root/hashlib.sha256(b'next').hexdigest()).write_bytes(b'next')
        with patch.object(c,'MAXIMUM_OBJECTS',1),self.assertRaisesRegex(ValueError,'name/count'):c.Pool(self.root,**OPTIONS)

    def test_linked_special_wrong_digest_and_unlisted_objects_fail_closed(self):
        for kind in ('symlink','hardlink','fifo','wrong-digest'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);file=root/('0'*64)
                if kind=='symlink':file.symlink_to(self.root/'absent')
                elif kind=='hardlink':
                    outside=self.root/'external';outside.write_bytes(b'x');os.link(outside,file)
                elif kind=='fifo':os.mkfifo(file)
                else:file.write_bytes(b'x')
                with self.assertRaises(ValueError):c.Pool(root,**OPTIONS)

    def test_publication_prefixes_and_all_26_negative_reasons_match_legacy(self):
        fixture=publication_fixture.PublicationResourceEvidenceTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        old=publication.collect(fixture.root,fixture.events);new=publication.collect(fixture.root,fixture.events,**OPTIONS)
        self.assertEqual(old,new)
        self.assertEqual(publication.compare(old,fixture.plans),publication.compare(new,fixture.plans))
        self.assertTrue(all(type(row['files']) is c.Files for tx in new for row in tx))
        for name,suffix in negatives.NEGATIVES.items():
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);shutil.copytree(fixture.root/publication.DIRECTORY,root/publication.DIRECTORY)
                negatives.mutate(root,name)
                with self.assertRaises(ValueError) as caught:
                    publication.compare(publication.collect(root,fixture.events,**OPTIONS),fixture.plans)
                self.assertEqual('publication resources '+suffix,str(caught.exception))

    def test_retirement_prefixes_share_one_pool_and_require_every_object(self):
        fixture=retirement_fixture.JoiningSourceRetirementTest();fixture.setUp();self.addCleanup(fixture.doCleanups);fixture.transaction()
        old=retirement.collect(fixture.root,fixture.events);new=retirement.collect(fixture.root,fixture.events,**OPTIONS)
        self.assertEqual(old,new)
        self.assertIs(new[0]['steps'][0]['files'].pool,new[0]['steps'][1]['files'].pool)
        (fixture.objects/retirement.sha(b'unobserved')).write_bytes(b'unobserved')
        with self.assertRaisesRegex(ValueError,'unobserved object'):retirement.collect(fixture.root,fixture.events,**OPTIONS)

    def test_policy_reaches_retirement_replay_and_publication_negative_driver(self):
        fixture=retirement_fixture.JoiningSourceRetirementTest();fixture.setUp();self.addCleanup(fixture.doCleanups);fixture.transaction()
        with patch.object(retirement.grants,'MAXIMUM_BYTES',1):
            reader=retirement_replay.Retirements(fixture.root,fixture.events,voters=('node-1',),**OPTIONS)
            self.assertIsInstance(reader.rows[0]['steps'][0]['files'],c.Files)
            receipt=retirement.validate(fixture.root,fixture.events,**OPTIONS)
            self.assertEqual(c.policy.SEGMENTED,receipt['wireLayout']);self.assertFalse(receipt['independentlyDerived'])
        fixture=publication_fixture.PublicationResourceEvidenceTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        (fixture.root/'events.json').write_bytes(publication.f.canonical(fixture.events))
        with patch.object(publication,'original',return_value=({'fixtureOnly':True},fixture.plans)) as original, \
                patch.object(publication.grants,'MAXIMUM_BYTES',1):
            receipt=negatives.qualify(fixture.root,'5-REPLACE-required-four',**OPTIONS)
            self.assertEqual(26,len(receipt['negatives']));self.assertEqual(c.policy.SEGMENTED,receipt['wireLayout'])
            original.assert_called_once_with(fixture.root,'5-REPLACE-required-four',None,**OPTIONS)

    @unittest.skipUnless(sys.platform.startswith('linux'),'address-space probe requires Linux')
    def test_320_mib_pool_and_many_views_under_160_mib_address_space(self):
        for i in range(5):
            path=self.root/'building'
            with path.open('wb') as stream:stream.write(bytes([i+1]));stream.truncate(64*1024**2)
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                while block:=stream.read(1024**2):digest.update(block)
            path.rename(self.root/digest.hexdigest())
        program='''import resource,sys
from pathlib import Path
from scripts.v53 import capture_objects as c
resource.setrlimit(resource.RLIMIT_AS,(160*1024**2,160*1024**2))
pool=c.Pool(Path(sys.argv[1]),bootstrap_source=c.policy.BACKUP,wire_layout=c.policy.SEGMENTED)
names={str(i):digest for i,digest in enumerate(pool.keys())}
views=[pool.view(names) for _ in range(1024)]
assert sum(pool.size(k) for k in pool.keys())==320*1024**2
assert len(views[0].identities())==5 and all(v.pool is pool for v in views)
pool.check_unchanged()
print('captureObjectsMemory=PASS')
'''
        result=subprocess.run([sys.executable,'-c',program,str(self.root)],text=True,capture_output=True,timeout=60)
        self.assertEqual(0,result.returncode,result.stderr);self.assertIn('captureObjectsMemory=PASS',result.stdout)


if __name__=='__main__':unittest.main()

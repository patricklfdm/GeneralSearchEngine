"""Deferred physical caches still validate complete original bytes and identities."""
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import physical_snapshot as p
from . import bootstrap_replay_contract as policy
from . import joining_catalog_evidence as catalog


class PhysicalSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def original(self):
        (self.root/'nested').mkdir(); (self.root/'empty').mkdir()
        (self.root/'small').write_bytes(b'original')
        (self.root/'nested/image').write_bytes(b'ab'*p.BLOCK+b'end')
        return {'nested':None,'empty':None,'small':b'original','nested/image':b'ab'*p.BLOCK+b'end'}

    def test_read_equality_and_deepcopy_preserve_the_original_without_retaining_bytes(self):
        expected = self.original(); actual = p.Snapshot(self.root)
        self.assertEqual(expected, actual); self.assertEqual(actual, expected)
        self.assertEqual(expected, dict(actual)); self.assertEqual(actual, p.Snapshot(self.root))
        self.assertEqual(sum(len(v) for v in expected.values() if v is not None), actual.total_bytes)
        self.assertTrue(all(v is None or type(v) is tuple for v in actual._entries.values()))
        self.assertTrue(all(type(v) is str and len(v)==64 for v in actual._hashes.values()))
        self.assertIs(actual, copy.deepcopy(actual))
        bad=dict(expected,small=b'changed');self.assertNotEqual(actual,bad)
        self.assertNotEqual(bad,actual);self.assertNotEqual(actual,{})
        with self.assertRaises(KeyError):actual['absent']
        with self.assertRaises(TypeError):actual['small']=b'changed'

    def test_complete_inventory_is_checked_before_opening_even_unread_members(self):
        self.original(); (self.root/'oversized').touch()
        with (self.root/'oversized').open('wb') as stream:stream.truncate(p.FILE_BYTES+1)
        with patch.object(p.os,'open') as opened:
            with self.assertRaisesRegex(ValueError,'byte capacity'):p.Snapshot(self.root)
            opened.assert_not_called()
        self.assertEqual((64*1024**2,512*1024**2,256,4),(p.FILE_BYTES,p.TOTAL_BYTES,p.MEMBERS,p.DEPTH))

    def test_total_count_and_depth_remain_the_old_physical_limits(self):
        self.original()
        for name,limit,reason in (('TOTAL_BYTES',3,'byte capacity'),('MEMBERS',1,'member capacity'),('DEPTH',0,'directory depth')):
            with self.subTest(name=name),patch.object(p,name,limit),self.assertRaisesRegex(ValueError,reason):p.Snapshot(self.root)

    def test_links_special_files_and_root_aliases_are_not_admitted(self):
        for kind in ('symlink','directory-link','hardlink','fifo'):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'data').write_bytes(b'x');entry=root/'bad'
                if kind=='symlink':entry.symlink_to(root/'data')
                elif kind=='directory-link':entry.symlink_to(self.root,target_is_directory=True)
                elif kind=='hardlink':os.link(root/'data',entry)
                else:os.mkfifo(entry)
                with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'regular file'):p.Snapshot(root)
        alias=self.root/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'directory'):p.Snapshot(alias)

    def test_original_mutations_are_rejected_by_reads_full_checks_and_equality(self):
        for change in ('same-size','replace','add','directory','unselected-file'):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'directory').mkdir();file=root/'directory/data';file.write_bytes(b'original')
                (root/'unselected').write_bytes(b'other');view=p.Snapshot(root)
                expected={'directory':None,'directory/data':b'original','unselected':b'other'}
                if change=='same-size':file.write_bytes(b'altered!')
                elif change=='replace':file.rename(root/'previous');file.write_bytes(b'original')
                elif change=='add':(root/'extra').touch()
                elif change=='unselected-file':(root/'unselected').write_bytes(b'newer')
                else:(root/'directory').rename(root/'old');(root/'directory').symlink_to(root/'old',target_is_directory=True)
                calls=[lambda:view.check_unchanged(),lambda:view==expected,lambda:copy.deepcopy(view)]
                if change in ('add','replace','directory'):calls += [lambda:list(view),lambda:len(view)]
                if change!='unselected-file':calls.append(lambda:view['directory/data'])
                for call in calls:
                    with self.subTest(change=change,call=call),self.assertRaises(ValueError):call()

    def test_replacement_between_stat_and_open_is_rejected(self):
        self.original(); view=p.Snapshot(self.root);original=p.os.open
        def swapped(path,*args):
            file=Path(path);file.rename(file.with_name('previous'));file.write_bytes(b'original')
            return original(path,*args)
        with patch.object(p.os,'open',side_effect=swapped),self.assertRaisesRegex(ValueError,'file replaced'):
            view['small']

    def test_mutation_during_read_is_rejected(self):
        self.original();view=p.Snapshot(self.root);original=p.os.fdopen
        class Changed:
            def __init__(self,*args):self.stream=original(*args)
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def fileno(self):return self.stream.fileno()
            def read(self,size):
                value=self.stream.read(size);(view.root/'small').write_bytes(b'grew during read');return value
        with patch.object(p.os,'fdopen',side_effect=Changed),self.assertRaisesRegex(ValueError,'file changed'):view['small']

    def test_complete_hashing_is_streamed_and_repeated_reads_do_not_use_cached_bytes(self):
        self.original();sizes=[];original=p.os.fdopen
        class Observed:
            def __init__(self,*args):self.stream=original(*args)
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def fileno(self):return self.stream.fileno()
            def read(self,size):sizes.append(size);return self.stream.read(size)
        with patch.object(p.os,'fdopen',side_effect=Observed),patch.object(Path,'read_bytes',side_effect=AssertionError('stream originals')):
            view=p.Snapshot(self.root)
        self.assertTrue(sizes and set(sizes)=={p.BLOCK})
        with patch.object(view,'_open',wraps=view._open) as opened:
            self.assertEqual(b'original',view['small']);self.assertEqual(b'original',view['small'])
            self.assertEqual(2,opened.call_count)
        # A digest is an additional binding, not permission to reuse raw bytes.
        view._hashes['small']=hashlib.sha256(b'other').hexdigest()
        with self.assertRaisesRegex(ValueError,'content changed'):view['small']

    def test_model_policy_and_owner_cache_keep_ordinary_json_behavior(self):
        for model in (SimpleNamespace(),SimpleNamespace(bootstrap_source=policy.BACKUP,wire_layout=policy.JSON)):
            with patch.object(catalog.disk,'inventory',return_value={'old':b'bytes'}) as old:
                self.assertEqual({'old':b'bytes'},p.from_model(self.root,model));old.assert_called_once_with(self.root)
        with self.assertRaisesRegex(ValueError,'requires backup'):
            p.from_model(self.root,SimpleNamespace(wire_layout=policy.SEGMENTED))
        model=catalog.Replay.__new__(catalog.Replay)
        model.bootstrap_source=policy.BACKUP;model.wire_layout=policy.SEGMENTED
        model.snapshots={};model.old=('node-1',);model.joining='node-4';model.path=self.root
        folder=self.root/'applied-1/node-1';folder.mkdir(parents=True);(folder/'image').write_bytes(b'data')
        view=model.owner('applied',1,'node-1');self.assertIsInstance(view,p.Snapshot)
        self.assertIs(view,model.owner('applied',1,'node-1'));self.assertEqual({'image':b'data'},view)

    def test_generation_source_projection_keeps_only_original_paths(self):
        original=self.original();source=p.Snapshot(self.root)
        projection=p.members(source,'nested/',exclude=('absent',))
        self.assertIsInstance(projection,p.Projection);self.assertIs(source,projection.source)
        self.assertEqual({'image':original['nested/image']},projection)
        self.assertEqual(projection,p.members(original,'nested/'))
        self.assertEqual({'image':'nested/image'},projection._names)
        self.assertIs(projection,copy.deepcopy(projection))
        self.assertEqual({},p.members(source,'nested/',exclude=('image',)))
        with self.assertRaises(KeyError):projection['../small']
        (self.root/'nested/image').write_bytes(b'changed')
        for read in (lambda:projection['image'],lambda:projection.check_unchanged(),lambda:dict(projection)):
            with self.assertRaises(ValueError):read()

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux address-space bound')
    def test_multiple_physical_views_do_not_accumulate_all_application_bytes(self):
        code = '''
import resource,tempfile
from pathlib import Path
from scripts.v53.physical_snapshot import Snapshot
resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2))
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);views=[]
    for n in range(8):
        directory=root/str(n);directory.mkdir()
        with (directory/'image').open('wb') as stream:stream.truncate(8*1024**2)
        views.append(Snapshot(directory))
    for view in views:
        if view!=views[0] or len(view['image'])!=8*1024**2:raise ValueError('physical view bytes')
print('PASS')
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=catalog.f.ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(0,result.returncode,result.stderr);self.assertEqual('PASS',result.stdout.strip())


if __name__=='__main__':unittest.main()

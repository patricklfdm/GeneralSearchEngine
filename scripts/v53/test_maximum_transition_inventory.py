"""Streaming large-original hashes and strict physical member limits."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import maximum_transition_inventory as m
from . import joining_history_run as previous


class MaximumTransitionInventoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_large_tree_bound_never_becomes_a_read_allocation(self):
        (self.root/'tiny').write_bytes(b'x');(self.root/'nested').mkdir();(self.root/'nested/empty').write_bytes(b'')
        with patch.object(Path,'read_bytes',side_effect=AssertionError('must stream')):
            result=m.inventory(self.root,maximum=128*1024**3)
        self.assertEqual(dict(files={'nested/empty':hashlib.sha256(b'').hexdigest(),'tiny':hashlib.sha256(b'x').hexdigest()},directories=['nested'],bytes=1),result)
        self.assertEqual(previous.inventory(self.root,maximum=1024),result)

    def test_chunks_stay_bounded_and_multichunk_hash_matches(self):
        raw=b'ab'*m.CHUNK+b'end';(self.root/'original').write_bytes(raw);sizes=[];original=os.fdopen
        class Observed:
            def __init__(self,*a):self.stream=original(*a)
            def __enter__(self):return self
            def __exit__(self,*a):self.stream.close()
            def fileno(self):return self.stream.fileno()
            def read(self,size):sizes.append(size);return self.stream.read(size)
        with patch.object(m.os,'fdopen',side_effect=Observed):result=m.inventory(self.root,maximum=len(raw))
        self.assertEqual(hashlib.sha256(raw).hexdigest(),result['files']['original'])
        self.assertTrue(sizes and set(sizes)=={m.CHUNK});self.assertGreater(len(sizes),2)

    def test_byte_and_member_limits_are_enforced_before_read(self):
        (self.root/'file').write_bytes(b'1234')
        for limit in (0,-1,True,None):
            with self.assertRaises(ValueError):m.inventory(self.root,maximum=limit)
        with patch.object(m.os,'open') as opened:
            with self.assertRaisesRegex(ValueError,'byte bound'):m.inventory(self.root,maximum=3)
            with patch.object(m,'FILE_LIMIT',3),self.assertRaisesRegex(ValueError,'byte bound'):m.inventory(self.root,maximum=100)
            with patch.object(m,'MEMBERS',0),self.assertRaisesRegex(ValueError,'member bound'):m.inventory(self.root,maximum=100)
            opened.assert_not_called()

    def test_symlink_hardlink_fifo_and_linked_directory_are_rejected(self):
        for kind in ('symlink','hardlink','fifo','directory-link'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);path=root/'item'
                if kind=='fifo':os.mkfifo(path)
                elif kind=='directory-link':path.symlink_to(self.root,target_is_directory=True)
                else:
                    (root/'original').write_bytes(b'x')
                    if kind=='symlink':path.symlink_to(root/'original')
                    else:os.link(root/'original',path)
                with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'regular member'):m.inventory(root,maximum=1024)

    def test_changed_file_is_not_hashed_as_an_immutable_original(self):
        path=self.root/'original';path.write_bytes(b'unchanged');original=os.fdopen
        class Changed:
            def __init__(self,*a):self.stream=original(*a);self.changed=False
            def __enter__(self):return self
            def __exit__(self,*a):self.stream.close()
            def fileno(self):return self.stream.fileno()
            def read(self,size):
                value=self.stream.read(size)
                if not self.changed:self.changed=True;path.write_bytes(b'changed')
                return value
        with patch.object(m.os,'fdopen',side_effect=Changed),self.assertRaisesRegex(ValueError,'file changed'):
            m.inventory(self.root,maximum=1024)


if __name__=='__main__':unittest.main()

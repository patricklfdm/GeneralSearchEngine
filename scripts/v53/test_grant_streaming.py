"""Component boundaries only; these fixtures do not qualify a native history."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from . import joining_grant_captures as g
from . import physical_snapshot as physical
from .test_joining_grant_captures import events, observed

OPTIONS = dict(bootstrap_source=g.policy.BACKUP, wire_layout=g.policy.SEGMENTED)


class GrantStreamingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_explicit_policy_precedes_io_and_keeps_legacy_defaults(self):
        with patch.object(physical, 'Snapshot') as opened:
            for source, layout in [('EMPTY','SEGMENTED_BACKUP'), ('unknown','JSON'), (True,'JSON')]:
                with self.subTest(source=source), self.assertRaises(ValueError):
                    g.inventory(self.root, bootstrap_source=source, wire_layout=layout)
                with self.assertRaises(ValueError):
                    g.collect(self.root, [], bootstrap_source=source, wire_layout=layout)
            opened.assert_not_called()
        (self.root/'file').write_bytes(b'abc')
        with patch.object(g, 'MAXIMUM_BYTES', 2):
            for options in ({}, dict(bootstrap_source=g.policy.BACKUP)):
                with self.assertRaisesRegex(ValueError, 'byte capacity'):g.inventory(self.root, **options)
            files, metadata, size = g.inventory(self.root, **OPTIONS)
            self.assertEqual(b'abc', files['file']); self.assertEqual(3, size)
            self.assertEqual(dict(size=3, sha256=g.sha(b'abc')), metadata['file'])

    def test_deferred_inventory_checks_members_and_all_original_bytes(self):
        (self.root/'empty').mkdir(); (self.root/'file').write_bytes(b'abc')
        old_files, old_metadata, old_total = g.inventory(self.root)
        files, metadata, total = g.inventory(self.root, **OPTIONS)
        self.assertIsInstance(files, physical.Snapshot)
        self.assertEqual(old_metadata, metadata); self.assertEqual(old_total, total)
        self.assertEqual(old_files, files)
        metadata['file']['sha256'] = '0'*64
        self.assertEqual(old_metadata, files.identities())
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('whole-file metadata read')):
            self.assertEqual(old_metadata, g.inventory(self.root, **OPTIONS)[1])
        (self.root/'file').write_bytes(b'xyz')
        with self.assertRaisesRegex(ValueError, 'changed'):g.unchanged(files)

    def test_limits_links_depth_and_unread_members_fail_closed(self):
        file=self.root/'file'; file.write_bytes(b'a')
        for kind in ('symlink', 'hardlink', 'fifo'):
            with self.subTest(kind=kind):
                member=self.root/'extra'
                if kind=='symlink':member.symlink_to(file)
                elif kind=='hardlink':os.link(file,member)
                else:os.mkfifo(member)
                try:
                    with self.assertRaises(ValueError):g.inventory(self.root, **OPTIONS)
                finally:member.unlink()
        with patch.object(g, 'MAXIMUM_FILES', 1):
            (self.root/'extra').touch()
            with self.assertRaisesRegex(ValueError, 'member capacity'):g.inventory(self.root, **OPTIONS)
            (self.root/'extra').unlink()
        with patch.object(g, 'SEGMENTED_BYTES', 1):
            file.write_bytes(b'ab')
            with self.assertRaisesRegex(ValueError, 'byte capacity'):g.inventory(self.root, **OPTIONS)
        file.unlink(); deep=self.root.joinpath(*('x' for _ in range(8)));deep.mkdir(parents=True)
        (deep/'file').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError, 'member path'):g.inventory(self.root, **OPTIONS)

    def test_collection_budget_is_caller_selected_and_still_bounded(self):
        root=self.root/g.DIRECTORY;root.mkdir()
        for i in (1,2):(root/f'capture-{i:04d}').mkdir()
        row=dict(observed(), bytes=160*g.MIB)
        with patch.object(g, 'read', return_value=row):
            with self.assertRaisesRegex(ValueError, 'aggregate capacity'):g.collect(self.root, events(['node-1']*2))
            self.assertEqual(2, len(g.collect(self.root, events(['node-1']*2), **OPTIONS)))
            with patch.object(g.policy, 'ORIGINAL_BYTES', 319*g.MIB):
                with self.assertRaisesRegex(ValueError, 'aggregate capacity'):
                    g.collect(self.root, events(['node-1']*2), **OPTIONS)

    def test_explicit_snapshot_limits_do_not_change_physical_defaults(self):
        for args in ((True,512,8),(512,False,8),(512,512,-1),(129*1024**3,512,8)):
            with self.subTest(args=args), self.assertRaises(ValueError):physical.Limits(*args)
        (self.root/'a').mkdir();(self.root/'a/b').touch()
        with patch.object(physical,'MEMBERS',1):
            with self.assertRaisesRegex(ValueError,'member capacity'):physical.Snapshot(self.root)
            self.assertEqual(2,len(g.inventory(self.root,**OPTIONS)[0]))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'address-space probe requires Linux')
    def test_320_mib_inventory_under_160_mib_address_space(self):
        for i in range(5):
            with (self.root/f'image-{i}').open('wb') as stream:stream.truncate(64*g.MIB)
        program='''import json,resource,sys
from pathlib import Path
from scripts.v53 import joining_grant_captures as g
resource.setrlimit(resource.RLIMIT_AS,(160*g.MIB,160*g.MIB))
files,metadata,size=g.inventory(Path(sys.argv[1]),bootstrap_source=g.policy.BACKUP,wire_layout=g.policy.SEGMENTED)
g.unchanged(files)
assert size==320*g.MIB and len(metadata)==5
assert all(type(v) is tuple for v in files._entries.values())
print(json.dumps(dict(status='PASS',bytes=size,files=len(files))))
'''
        result=subprocess.run([sys.executable,'-c',program,str(self.root)],capture_output=True,text=True,timeout=60)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual(320*g.MIB,json.loads(result.stdout)['bytes'])


if __name__=='__main__':unittest.main()

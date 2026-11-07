"""Synthetic transport-envelope probes, not maximum-image native acceptance."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import replica_capture_limits as limits
from . import physical_snapshot as physical
from . import capture_objects as objects
from . import joining_grant_captures as grants
from . import resource_transitions as resources
from . import bootstrap_replay_contract as policy

MODEL = SimpleNamespace(bootstrap_source=policy.BACKUP, wire_layout=policy.SEGMENTED)
OPTIONS = vars(MODEL)


class ReplicaCaptureLimitsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_frozen_envelope_and_legacy_limits_are_distinct(self):
        self.assertEqual((384,7,64,832),(limits.METADATA_BYTES//limits.MIB,limits.APPLICATION_COUNT,
                                      limits.FILE_BYTES//limits.MIB,limits.SNAPSHOT_BYTES//limits.MIB))
        self.assertEqual(limits.APPLICATION_COUNT,resources.COUNTS['APPLICATION'])
        self.assertEqual(limits.FILE_BYTES,resources.BYTES['APPLICATION'])
        self.assertEqual(limits.FILE_BYTES,physical.FILE_BYTES)
        self.assertEqual(limits.SNAPSHOT_BYTES,grants.SEGMENTED_BYTES)
        self.assertEqual(limits.SNAPSHOT_BYTES,objects.SNAPSHOT_BYTES)
        self.assertEqual((256,512,256,4),(grants.MAXIMUM_BYTES//limits.MIB,physical.TOTAL_BYTES//limits.MIB,physical.MEMBERS,physical.DEPTH))
        self.assertEqual(128*1024**3,policy.ORIGINAL_BYTES)

    def test_all_segmented_entries_select_same_explicit_envelope(self):
        (self.root/'file').write_bytes(b'original')
        direct=physical.from_model(self.root,MODEL)
        captured,_,_=grants.inventory(self.root,**OPTIONS)
        expected=physical.Limits(limits.SNAPSHOT_BYTES,limits.MEMBERS,limits.DEPTH)
        self.assertEqual(expected,direct.limits);self.assertEqual(expected,captured.limits)
        self.assertEqual({'file':b'original'},direct)
        for source,layout in ((policy.EMPTY,policy.SEGMENTED),('unknown',policy.SEGMENTED)):
            with patch.object(physical,'Snapshot') as opened,self.assertRaises(ValueError):
                physical.from_model(self.root,SimpleNamespace(bootstrap_source=source,wire_layout=layout))
            opened.assert_not_called()

    def test_segmented_physical_and_grant_paths_have_the_same_member_depth(self):
        nested=self.root.joinpath(*('x' for _ in range(limits.DEPTH)));nested.mkdir(parents=True)
        self.assertEqual(limits.DEPTH,len(physical.from_model(self.root,MODEL)))
        (nested/'file').write_bytes(b'x')
        for read in (lambda:physical.from_model(self.root,MODEL),lambda:grants.inventory(self.root,**OPTIONS)):
            with self.assertRaisesRegex(ValueError,'member path'):read()

    def test_logical_duplicate_objects_count_toward_exact_prefix_boundary(self):
        # One physical sparse object can occur many times in a logical prefix;
        # deduplication must not enlarge that prefix's allowance.
        file=self.root/'sparse'
        with file.open('wb') as out:out.truncate(limits.FILE_BYTES)
        hashed=hashlib.sha256()
        with file.open('rb') as source:
            for block in iter(lambda:source.read(1024**2),b''):hashed.update(block)
        digest=hashed.hexdigest()
        file.rename(self.root/digest)
        one=hashlib.sha256(b'x').hexdigest();(self.root/one).write_bytes(b'x')
        pool=objects.Pool(self.root,**OPTIONS)
        names={f'part-{i}':digest for i in range(13)}
        view=pool.view(names);self.assertEqual(13,len(view));view.check_unchanged()
        with self.assertRaisesRegex(ValueError,'prefix byte capacity'):pool.view(dict(names,extra=one))

    def test_full_envelope_streams_under160MiB_address_space(self):
        for i in range(13):
            with (self.root/f'part-{i}').open('wb') as out:out.truncate(limits.FILE_BYTES)
        # Run in a fresh process so existing test imports do not consume its
        # limit. Payload reads are forbidden: these operations need metadata.
        code='''import json,resource,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from scripts.v53 import physical_snapshot as p,joining_grant_captures as g
resource.setrlimit(resource.RLIMIT_AS,(160*1024**2,160*1024**2))
root=Path(sys.argv[1]);options=dict(bootstrap_source='VERIFIED_DURABLE_BACKUP',wire_layout='SEGMENTED_BACKUP')
with patch.object(Path,'read_bytes',side_effect=AssertionError('eager payload')):
    files=p.from_model(root,SimpleNamespace(**options));files.check_unchanged()
    copied,metadata,size=g.inventory(root,**options)
    assert size==832*1024**2 and metadata==files.identities() and copied.limits==files.limits
try:p.Snapshot(root)
except ValueError as error:assert str(error)=='physical snapshot byte capacity'
else:raise AssertionError('legacy envelope enlarged')
print(json.dumps(dict(status='PASS',bytes=size,addressSpaceLimit=160*1024**2,peakRssKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,synthetic=True)))
'''
        result=subprocess.run([sys.executable,'-c',code,str(self.root)],capture_output=True,text=True,timeout=90)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual('PASS',json.loads(result.stdout)['status'])
        (self.root/'one-more').write_bytes(b'x')
        with patch.object(physical.os,'open') as opened:
            with self.assertRaisesRegex(ValueError,'byte capacity'):physical.from_model(self.root,MODEL)
            with self.assertRaisesRegex(ValueError,'byte capacity'):grants.inventory(self.root,**OPTIONS)
            opened.assert_not_called()


if __name__=='__main__':unittest.main()

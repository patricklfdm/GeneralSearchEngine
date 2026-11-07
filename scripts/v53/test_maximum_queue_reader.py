"""Fresh-process measurement mechanics; these fixtures are not maximum histories."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from . import maximum_queue_reader as r
from . import test_maximum_queue_run as fixture


@unittest.skipUnless(sys.platform=='linux','Linux RSS observation requires Linux units')
class MaximumQueueReaderTest(unittest.TestCase):
    def setUp(self):
        self.generator=fixture.MaximumQueueRunTest();self.generator.setUp();self.addCleanup(self.generator.doCleanups)
        self.helper=self.generator;self.root=self.generator.fixture.legacy.root
        p=patch.object(r.m.gate,'load',side_effect=lambda raw,**kw:raw);p.start();self.addCleanup(p.stop)
        self.pins=self.helper.pins

    def qualified(self):
        with patch.object(fixture.capacity,'check',return_value=fixture.native.capacity_record('verify')),\
             patch.object(r.m.gate,'qualify',return_value=fixture.result()):
            return r.m.qualify(self.helper.path,r.PROFILE,self.pins)

    def recorded(self,output):
        qualified=self.qualified()
        def verify(path,*args):
            Path(path).mkdir();r.m.h.save(Path(path)/'receipt.json',qualified);return qualified
        with patch.object(r.m,'verify',side_effect=verify):r.run(output,self.helper.path,self.pins)
        return qualified

    def test_exact_complete_verification_and_measurement_are_bound(self):
        output=self.root/'recorded';expected=self.recorded(output)
        value,memory=r.result(output,self.pins);self.assertEqual(expected,value)
        self.assertGreater(memory['peakRssBytes'],0);self.assertGreater(memory['elapsedNanos'],0)
        self.assertFalse(memory['wholeReaderMemoryQualified']);self.assertFalse(memory['phase3Complete'])
        original=r.m.read(output/'memory.json')
        for key,changed in [('status','PARTIAL'),('retries',True),('peakRssBytes',True),('peakRssBytes',0),('processId',0),
                            ('elapsedNanos',0),('cpuNanos',-1),('wholeReaderMemoryQualified',True),('phase3Complete',True),
                            ('peakRssBytes',1),('rssSource','getrusage'),('procStatusSha256','0'*64),
                            ('verificationReceiptSha256','0'*64)]:
            r.m.h.save(output/'memory.json',dict(original,**{key:changed}))
            with self.subTest(key=key,changed=changed),self.assertRaises(ValueError):r.result(output,self.pins)
        r.m.h.save(output/'memory.json',original)
        path=output/'verification/receipt.json'
        for key,changed in [('status','PARTIAL'),('originalFirst',False),('profile',r.m.SEGMENTED_PROFILE),('sourceSha256','e'*64),
                            ('verificationCapacity',fixture.native.capacity_record()),('combinedResourcesQualified',True)]:
            r.m.h.save(path,dict(expected,**{key:changed}))
            r.m.h.save(output/'memory.json',dict(original,verificationReceiptSha256=r.m.tc.file_hash(path)))
            with self.subTest(qualification=key),self.assertRaises(ValueError):r.result(output,self.pins)
        missing=copy.deepcopy(expected);missing['qualification']['negatives'].pop()
        r.m.h.save(path,missing);r.m.h.save(output/'memory.json',dict(original,verificationReceiptSha256=r.m.tc.file_hash(path)))
        with self.assertRaises(ValueError):r.result(output,self.pins)

    def test_error_retains_measurement_and_never_becomes_success(self):
        output=self.root/'failed'
        def fail(path,*args):
            Path(path).mkdir()
            r.m.h.save(Path(path)/'receipt.json',dict(status='FAIL',failure='synthetic original rejection'))
            raise ValueError('synthetic original rejection')
        with patch.object(r.m,'verify',side_effect=fail) as call:
            with self.assertRaisesRegex(ValueError,'original rejection'):r.run(output,self.helper.path,self.pins)
            self.assertEqual(1,call.call_count)
        value=r.m.read(output/'memory.json');self.assertEqual('FAIL',value['status']);self.assertGreater(value['peakRssBytes'],0)
        with self.assertRaises(ValueError):r.result(output,self.pins)

    def test_observer_spawns_one_fixed_child_and_retains_failure(self):
        output=self.root/'observer'
        def execute(command,work,log,**kw):
            self.assertEqual([sys.executable,'-B','-m','scripts.v53.maximum_queue_reader'],command[:4])
            self.assertEqual(str(self.helper.path.absolute()),command[6]);self.assertEqual(r.m.h.ROOT,work)
            Path(log).write_text('synthetic child execution')
            self.recorded(Path(command[4]));return {'exit':0,'elapsedSeconds':0.1}
        with patch.object(r.m.h,'execute',side_effect=execute) as call:
            result,memory=r.observe(output,self.helper.path,self.pins);self.assertEqual(1,call.call_count)
        self.assertEqual(20,len(result['qualification']['negatives']))
        self.assertEqual(memory,r.m.read(output/'reader/memory.json'))
        with patch.object(r.m.h,'execute',return_value={'exit':-9,'elapsedSeconds':0.1}) as call:
            with self.assertRaisesRegex(ValueError,'process failed'):r.observe(self.root/'killed',self.helper.path,self.pins)
            self.assertEqual(1,call.call_count)
        self.assertEqual(-9,r.m.read(self.root/'killed/execution.json')['exit'])
        self.assertFalse((self.root/'killed/reader/memory.json').exists())
        with patch.object(r.m.h,'execute') as call:
            with self.assertRaisesRegex(ValueError,'separation'):r.observe(self.helper.path/'bad',self.helper.path,self.pins)
            call.assert_not_called()
        with patch.object(r.m,'verify') as call:
            with self.assertRaisesRegex(ValueError,'separation'):r.run(self.helper.path/'bad',self.helper.path,self.pins)
            call.assert_not_called()
        self.assertFalse((self.helper.path/'bad').exists())

    def test_fresh_process_rss_tracks_touched_bytes_without_parent_peak(self):
        # Exercise the real Linux RSS observation in two fresh Python processes.
        # The verifier is a named synthetic stub; no resource qualification runs.
        script='''import sys
from pathlib import Path
from unittest.mock import patch
from scripts.v53 import maximum_queue_reader as r
def stub(path,*args):
    b=bytearray(int(sys.argv[2])); b[::4096]=b'x'*len(b[::4096])
    Path(path).mkdir()
    r.m.h.save(Path(path)/'receipt.json',{'synthetic':True})
with patch.object(r.m,'verify',side_effect=stub):r.run(sys.argv[1],'/synthetic',{})
'''
        # Deliberately inflate and keep the parent resident during fork/exec.
        # ru_maxrss produced two identical inherited values in the broad suite.
        parent=bytearray(128*1024**2);parent[::4096]=b'x'*len(parent[::4096])
        peaks=[];pids=[]
        for i,size in enumerate((1024**2,48*1024**2)):
            path=self.root/f'fresh-{i}'
            completed=subprocess.run([sys.executable,'-B','-c',script,str(path),str(size)],cwd=r.m.h.ROOT,capture_output=True,text=True)
            self.assertEqual(0,completed.returncode,completed.stderr)
            value=r.m.read(path/'memory.json');peaks.append(value['peakRssBytes']);pids.append(value['processId'])
            with self.assertRaises(ValueError):r.result(path,self.pins)
        self.assertNotEqual(pids[0],pids[1]);self.assertGreater(peaks[1]-peaks[0],24*1024**2)
        self.assertLess(peaks[0],len(parent))

    def test_proc_status_requires_exact_process_and_peak_units(self):
        self.assertEqual(42*1024,r.proc_peak(b'Pid: 7\nVmHWM: 42 kB\n',7))
        for raw in (b'',b'Pid: 8\nVmHWM: 42 kB\n',b'Pid: 7\n',b'Pid: 7\nVmHWM: 42 MB\n',
                    b'Pid: 7\nVmHWM: -1 kB\n',b'Pid: 7\nVmHWM: 0 kB\n',
                    b'Pid: 7\nVmHWM: 42 kB\nVmHWM: 42 kB\n',b'Pid: 7\nPid: 7\nVmHWM: 42 kB\n'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):r.proc_peak(raw,7)

    def test_measurement_failure_is_not_hidden_or_allowed_to_replace_primary_failure(self):
        for name,primary in [('primary',ValueError('original failed')),('measurement',None)]:
            output=self.root/name
            with patch.object(r.m,'verify',side_effect=primary),patch.object(r,'proc_peak',side_effect=ValueError('status missing')):
                with self.assertRaisesRegex(ValueError,'original failed' if primary else 'status missing'):
                    r.run(output,self.helper.path,self.pins)
            value=r.m.read(output/'memory.json');self.assertEqual('FAIL',value['status'])
            self.assertEqual('status missing',value['measurementFailure']['message'])
            if primary:self.assertEqual('original failed',value['failure']['message'])


if __name__=='__main__':unittest.main()

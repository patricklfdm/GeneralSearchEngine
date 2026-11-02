"""Synthetic observation checks; none qualifies a real joining transition."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import joining_process_run as r
from .test_process_toolchain import record


class JoiningProcessRunTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.case='3-ADD,JOINING_RETENTION_SEED_PREFIX_WRITTEN,halt'

    def save(self,path,value):path.write_bytes(r.h.snapshot.f.canonical(value))

    def raw(self):
        raw=self.root/'raw';raw.mkdir();area=raw/'joining-process';area.mkdir();self.save(area/'spec.json',{})
        children=[];trace=[]
        for mode,pid in (('halt',1),('resume',2)):
            (area/mode).mkdir();(area/mode/'stderr').write_bytes(b'')
            rows=[dict(kind='STARTED',value=dict(mode=mode,pid=pid))]
            child=dict(mode=mode,pid=pid,exit=73 if mode=='halt' else 0,lockReleased=True)
            if mode=='halt':
                child['liveLockRefused']=True
                rows.append(dict(kind='CUT',value=dict(point=r.selected(self.case)['point'],mode=mode,pid=pid)))
            else:
                ready=dict(mode=mode,pid=pid,cut={},state='ACTIVE',publicReady=False);child.update(ready=ready,drained=True)
                rows.extend([dict(kind='READY',value=ready),dict(kind='CLOSED',value=dict(mode=mode,pid=pid,leases=0,queued=0))])
            children.append(child);(area/mode/'stdout').write_bytes(b'\n'.join(r.h.snapshot.f.canonical(v) for v in rows)+b'\n')
            trace.extend(dict(origin=mode,value=v) for v in rows)
        self.save(area/'result.json',dict(schema='gse-v53-joining-initialization-process-v1',status='PARTIAL',point=r.selected(self.case)['point'],
            mode='halt',children=children,processDeathQualified=False,physicalReplay=False,phase3Complete=False))
        self.save(raw/'events.json',[]);(raw/'process-trace.jsonl').write_bytes(b'\n'.join(r.h.snapshot.f.canonical(v) for v in trace)+b'\n')
        self.save(raw/'joining-continuation-result.json',dict(status='PASS',profile='3-ADD',stableColdReopened=True,automaticFinalAndBarrier=True,publicReady=False))
        for stage in ('before-process','interrupted','resumed-active','resumed-closed'):
            (raw/('process-'+stage)).mkdir();(raw/('joining-process-'+stage)).mkdir();self.save(raw/('joining-process-'+stage)/'inventory.json',[])
        return raw

    def test_catalogue_and_command_select_one_whole_opt_in_history(self):
        self.assertEqual(360,len(r.CASES));self.assertEqual(360,len(set(r.CASES)))
        self.assertEqual(36,len(r.POINTS));self.assertEqual(5,len(r.profiles.PROFILES))
        for case in r.CASES:
            value=r.selected(case);cmd=r.command(case)
            self.assertIn('-Dv53.joining.profile='+value['profile'],cmd)
            self.assertIn('-Dv53.joining.process='+value['point']+','+value['mode'],cmd)
            self.assertEqual(1,sum(v.startswith('-Dtest=') for v in cmd));self.assertEqual('test',cmd[-1])
        with self.assertRaisesRegex(ValueError,'exact case'):r.selected('3-ADD,UNKNOWN,halt')

    def test_collection_remains_partial_even_with_all_process_observations(self):
        result=r.collect(self.raw(),self.case);self.assertEqual('PARTIAL',result['status'])
        for name in ('physicalHistoryQualified','processDeathQualified','phase3Complete'):self.assertFalse(result[name])

    def test_partial_line_and_mismatched_shared_trace_are_rejected(self):
        raw=self.raw();path=raw/'joining-process/halt/stdout';original=path.read_bytes();path.write_bytes(original[:-1])
        with self.assertRaisesRegex(ValueError,'complete original lines'):r.collect(raw,self.case)
        path.write_bytes(original);self.save(raw/'events.json',[dict(event='unrecorded')])
        with self.assertRaisesRegex(ValueError,'exact parent observations'):r.collect(raw,self.case)

    def test_wrong_exit_reused_pid_missing_lock_and_claimed_qualification_reject(self):
        raw=self.raw();path=raw/'joining-process/result.json';original=path.read_bytes()
        for kind in ('exit','pid','lock','qualification'):
            value=r.metadata.read(path)
            if kind=='exit':value['children'][0]['exit']=0
            elif kind=='pid':value['children'][1]['pid']=1
            elif kind=='lock':value['children'][0]['liveLockRefused']=False
            else:value['processDeathQualified']=True
            self.save(path,value)
            with self.subTest(kind=kind),self.assertRaises(ValueError):r.collect(raw,self.case)
            path.write_bytes(original)

    def test_missing_continuation_or_snapshot_and_altered_child_control_reject(self):
        raw=self.raw();path=raw/'joining-continuation-result.json';original=path.read_bytes();value=r.metadata.read(path);value['stableColdReopened']=False;self.save(path,value)
        with self.assertRaisesRegex(ValueError,'full continuation'):r.collect(raw,self.case)
        path.write_bytes(original);snapshot=raw/'joining-process-interrupted/inventory.json';snapshot.unlink()
        with self.assertRaisesRegex(ValueError,'original snapshots'):r.collect(raw,self.case)
        self.save(snapshot,[])
        stdout=raw/'joining-process/halt/stdout';stdout.write_bytes(stdout.read_bytes().replace(b'"CUT"',b'"READY"'))
        with self.assertRaisesRegex(ValueError,'shared child order'):r.collect(raw,self.case)

    def test_boolean_resource_counts_cannot_impersonate_zero(self):
        raw=self.raw()
        for path in (raw/'process-trace.jsonl',raw/'joining-process/resume/stdout'):
            path.write_bytes(path.read_bytes().replace(b'"leases":0',b'"leases":false'))
        with self.assertRaisesRegex(ValueError,'exact child controls'):r.collect(raw,self.case)

    def test_skipped_opt_in_method_and_retry_are_not_success(self):
        suite=ET.Element('testsuite',dict(name=r.CLASS,tests='1',failures='0',errors='0',skipped='0'))
        ET.SubElement(suite,'testcase',dict(classname=r.CLASS,name=r.METHOD));path=self.root/'TEST-method.xml'
        ET.ElementTree(suite).write(path);self.assertEqual(1,r.junit(self.root,self.case)['tests'])
        for tag in ('skipped','flakyFailure','rerunFailure'):
            bad=ET.fromstring(ET.tostring(suite));ET.SubElement(bad[0],tag);ET.ElementTree(bad).write(path)
            with self.assertRaisesRegex(ValueError,'unretried test'):r.junit(self.root,self.case)

    def test_failed_native_retains_original_without_retry(self):
        def source(repo,path):path.mkdir();return dict(head='a'*40,files={})
        output=self.root/'failed'
        with patch.object(r.h,'source_copy',side_effect=source),patch.object(r.process_toolchain,'capture',return_value=record()),\
             patch.object(r.h,'execute',return_value=dict(exit=1)) as execute,redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'Maven failed; original retained'):r.run(output,'mvn',self.case)
        execute.assert_called_once();receipt=r.metadata.read(output/'receipt.json')
        self.assertEqual('FAIL',receipt['status']);self.assertEqual(0,receipt['retries']);self.assertTrue((output/'execution.json').is_file())


if __name__=='__main__':unittest.main()

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import remove_process_run as r


class RemoveProcessRunTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.case=r.CASES[1]

    def test_exact_matrix_matches_native_boundaries(self):
        self.assertEqual(52,len(r.CASES));self.assertEqual(52,len(set(r.CASES)))
        source=(r.h.ROOT/r.h.MODULE/'src/test/java/io/github/patricklfdm/generalsearch/replication/V53RemoveRetirementProcessTest.java').read_text()
        for point in r.POINTS:self.assertIn('"'+point+'"',source)
        for case in r.CASES:self.assertEqual(5,r.selected(case)['index'])

    def test_bad_case_cannot_create_output_or_run(self):
        with patch.object(r.h,'execute') as execute:
            for value in ('all',None,[],True,'3-REMOVE,'+','.join(self.case.split(',')[1:]),self.case+',again',' '+self.case):
                with self.assertRaisesRegex(ValueError,'^REMOVE process exact case$'):r.run(self.root/'new','mvn',value)
            self.assertFalse((self.root/'new').exists());execute.assert_not_called()

    def test_outputs_and_producer_sources_cannot_be_overwritten(self):
        with patch.object(r.h,'source_copy') as source:
            with self.assertRaises(FileExistsError):r.run(self.root,'mvn',self.case)
            with self.assertRaisesRegex(ValueError,'source separation'):r.run(self.root/'new','mvn',self.case,source_from=self.root)
            source.assert_not_called()

    def test_failure_retains_source_and_one_execution_without_qualification(self):
        def source(repo,work):work.mkdir();return dict(head='a'*40,files={})
        output=self.root/'failed'
        with patch.object(r.h,'source_copy',side_effect=source),patch.object(r.h,'execute',return_value=dict(exit=1)) as execute, \
             patch.object(r.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='JDK 21',stderr='')),redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'Maven failed; original retained'):r.run(output,'mvn',self.case)
        execute.assert_called_once();self.assertIn('-Dv53.remove.retirement.process='+self.case,execute.call_args.args[0])
        receipt=json.loads((output/'receipt.json').read_bytes());self.assertEqual('FAIL',receipt['status']);self.assertEqual(0,receipt['retries'])
        for flag in ('collectionComplete','processDeathQualified','physicalHistoryQualified','phase3Complete'):self.assertFalse(receipt[flag])
        self.assertTrue((output/'source.json').is_file());self.assertTrue((output/'execution.json').is_file())

    def report(self):
        suite=r.ET.Element('testsuite',dict(name=r.CLASS,tests='1',failures='0',errors='0',skipped='0'))
        r.ET.SubElement(suite,'testcase',dict(classname=r.CLASS,name=r.METHOD))
        return suite

    def test_junit_retries_or_hidden_failure_cannot_pass(self):
        p=self.root/'TEST-native.xml'
        for kind in ('failure','error','skipped','flakyFailure','flakyError','rerunFailure','rerunError'):
            suite=self.report();r.ET.SubElement(suite[0],kind);r.ET.ElementTree(suite).write(p)
            with self.assertRaisesRegex(ValueError,'unretried test'):r.junit(self.root)
        r.ET.ElementTree(self.report()).write(p);self.assertEqual(1,r.junit(self.root)['tests'])

    def test_only_one_exact_test_is_accepted(self):
        p=self.root/'TEST-native.xml'
        with self.assertRaisesRegex(ValueError,'exact report'):r.junit(self.root)
        for field,value in (('name','other'),('tests','2'),('skipped','1'),('errors','1'),('failures','1')):
            suite=self.report();suite.set(field,value);r.ET.ElementTree(suite).write(p)
            with self.assertRaisesRegex(ValueError,'unretried test'):r.junit(self.root)
        suite=self.report();suite[0].set('name','other');r.ET.ElementTree(suite).write(p)
        with self.assertRaisesRegex(ValueError,'unretried test'):r.junit(self.root)
        r.ET.ElementTree(self.report()).write(p);(self.root/'TEST-extra.xml').write_text('<testsuite/>')
        with self.assertRaisesRegex(ValueError,'exact report'):r.junit(self.root)

    def collection(self):
        raw=self.root/'raw';raw.mkdir();profile=r.selected(self.case)
        r.h.save(raw/'profile.json',profile)
        r.h.save(raw/'process.json',dict(parentPid=1,childPid=2,resumePid=3,mode='kill',index=5,
            point=profile['point'],exit=137,resumeExit=0,publicReady=False,liveLockRefused=True))
        for mode,worker in (('kill','interrupted-worker'),('resume','resumed-worker')):
            (raw/worker).mkdir();(raw/'history'/f'{mode}-opened-0').mkdir(parents=True)
            (raw/worker/'stderr').write_text('')
        (raw/'interrupted-worker/stdout').write_text('SNAPSHOT kill-opened-0\nCUT '+json.dumps(dict(index=5,event=profile['point']),sort_keys=True,separators=(',',':'))+'\n')
        (raw/'resumed-worker/stdout').write_text('SNAPSHOT resume-opened-0\nREADY resume\nCLOSED resume\n')
        r.h.save(raw/'resumed-worker/ready.json',dict(state='READY',cut=dict(index=7,view=dict(operation=None)),operation=dict(phase='COMPLETED'),publicReady=False))
        (raw/'resumed-worker/ready.gsrp').write_bytes(b'not independent proof')
        return raw

    def test_collection_is_explicitly_not_physical_or_process_qualification(self):
        result=r.collect(self.collection(),self.case);self.assertEqual('PARTIAL',result['status'])
        self.assertTrue(result['collectionComplete'])
        for flag in ('processDeathQualified','physicalHistoryQualified','phase3Complete'):self.assertFalse(result[flag])

    def test_wrong_profile_and_same_process_refuse(self):
        raw=self.collection();p=raw/'profile.json';original=p.read_bytes();value=json.loads(original);value['profile']='5-REMOVE';r.h.save(p,value)
        with self.assertRaisesRegex(ValueError,'original profile'):r.collect(raw,self.case)
        p.write_bytes(original);p=raw/'process.json';value=json.loads(p.read_bytes());value['resumePid']=2;r.h.save(p,value)
        with self.assertRaisesRegex(ValueError,'distinct original workers'):r.collect(raw,self.case)

    def test_interrupted_child_cannot_claim_ready(self):
        raw=self.collection();p=raw/'interrupted-worker/ready.json';p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'interrupted readiness'):r.collect(raw,self.case)

    def test_missing_cold_open_observation_refuses(self):
        raw=self.collection();(raw/'history/resume-opened-0').rmdir()
        with self.assertRaisesRegex(ValueError,'opened inventory'):r.collect(raw,self.case)

    def test_missing_cut_or_continuation_terminal_refuses(self):
        raw=self.collection();p=raw/'interrupted-worker/stdout';original=p.read_bytes();p.write_text('SNAPSHOT kill-opened-0\n')
        with self.assertRaisesRegex(ValueError,'original interruption'):r.collect(raw,self.case)
        p.write_bytes(original);(raw/'resumed-worker/stdout').write_text('SNAPSHOT resume-opened-0\nREADY resume\n')
        with self.assertRaisesRegex(ValueError,'continuation terminal'):r.collect(raw,self.case)

    def test_incomplete_operation_does_not_count_as_continuation(self):
        raw=self.collection();p=raw/'resumed-worker/ready.json';value=json.loads(p.read_bytes());value['operation']['phase']='JOINT';r.h.save(p,value)
        with self.assertRaisesRegex(ValueError,'completion observation'):r.collect(raw,self.case)

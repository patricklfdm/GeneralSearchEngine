import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from . import remove_profile_run as r
from . import transition_round_evidence as e


class RemoveProfileRunTest(unittest.TestCase):
    def test_profile_uses_separate_governing_majorities(self):
        self.assertEqual((('INTENT',('node-1','node-2','node-3')),('FINAL',('node-1','node-2','node-3')),
                          ('BARRIER',('node-1','node-2'))),e.continuous.topology(4))
        self.assertEqual((('INTENT',('node-1','node-2','node-3')),('FINAL',('node-1','node-2','node-3')),
                          ('BARRIER',('node-1','node-2','node-3'))),e.continuous.topology(5))
        for size in (True,3,6,'5',None):
            with self.assertRaisesRegex(ValueError,'^continuous REMOVE voter count$'):e.continuous.topology(size)

    def test_invalid_profile_cannot_create_output_or_launch_Maven(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r.h,'execute') as execute:
            output=Path(temp)/'result'
            for profile in ('3-REMOVE','4-ADD','5-REPLACE','05-REMOVE',None):
                with self.assertRaisesRegex(ValueError,'^REMOVE exact profile$'):r.run(output,'mvn',profile)
            self.assertFalse(output.exists());execute.assert_not_called()

    def test_existing_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r.h,'execute') as execute:
            with self.assertRaises(FileExistsError):r.run(temp,'mvn','5-REMOVE')
            execute.assert_not_called()

    def test_native_failure_is_retained_without_retry_or_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'failed'
            def source(repo,work):work.mkdir();return dict(head='a'*40,files={})
            with patch.object(r.h,'source_copy',side_effect=source),patch.object(r.h,'execute',return_value=dict(exit=1)) as execute, \
                 patch.object(r.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='toolchain',stderr='')),redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'^REMOVE Maven failed;'):r.run(output,'mvn','5-REMOVE')
            execute.assert_called_once();command=execute.call_args.args[0]
            self.assertIn('-Dv53.remove.profile=5-REMOVE',command)
            self.assertIn('-Dtest='+r.CLASS.rsplit('.',1)[-1]+'#'+r.METHOD,command)
            receipt=json.loads((output/'receipt.json').read_bytes())
            self.assertEqual('FAIL',receipt['status']);self.assertEqual(0,receipt['retries'])
            for flag in ('continuousOriginalQualified','automaticOperationCompletion','completeNetworkQualified','processDeathQualified','phase3Complete'):
                self.assertFalse(receipt[flag])

    def test_unavailable_toolchain_retains_diagnostics_without_running_tests(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'failed'
            def source(repo,work):work.mkdir();return dict(head='a'*40,files={})
            with patch.object(r.h,'source_copy',side_effect=source),patch.object(r.h,'execute') as execute, \
                 patch.object(r.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='unavailable')),redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'^REMOVE toolchain unavailable$'):r.run(output,'mvn','4-REMOVE')
            execute.assert_not_called();self.assertEqual('unavailable',json.loads((output/'toolchain.json').read_bytes())['stderr'])
            self.assertEqual('FAIL',json.loads((output/'receipt.json').read_bytes())['status'])

    def test_source_parent_is_not_a_new_execution_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'^REMOVE source separation$'):
                r.run(Path(temp)/'new','mvn','4-REMOVE',source_from=temp)

    def report(self,path,**changes):
        attributes=dict(name=r.CLASS,tests='1',failures='0',errors='0',skipped='0');attributes.update(changes)
        node=r.ET.Element('testsuite',attributes);r.ET.SubElement(node,'testcase',dict(classname=r.CLASS,name=r.METHOD))
        r.ET.ElementTree(node).write(path/'TEST-original.xml')

    def test_only_exact_executed_method_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);self.report(path);self.assertEqual(1,r.junit(path)['tests'])
            for change in ({'tests':'0'},{'failures':'1'},{'errors':'1'},{'skipped':'1'},{'name':'another.Class'}):
                self.report(path,**change)
                with self.assertRaisesRegex(ValueError,'^REMOVE exact passing test$'):r.junit(path)
            self.report(path);p=path/'TEST-original.xml';root=r.ET.parse(p).getroot();root[0].set('name','otherMethod');r.ET.ElementTree(root).write(p)
            with self.assertRaisesRegex(ValueError,'^REMOVE exact passing test$'):r.junit(path)

    def test_child_failure_is_not_hidden_by_suite_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);self.report(path);p=path/'TEST-original.xml';root=r.ET.parse(p).getroot()
            r.ET.SubElement(root[0],'failure');r.ET.ElementTree(root).write(p)
            with self.assertRaisesRegex(ValueError,'^REMOVE exact passing test$'):r.junit(path)

    def test_mixed_or_missing_reports_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            with self.assertRaisesRegex(ValueError,'^REMOVE exact test report$'):r.junit(path)
            self.report(path);(path/'TEST-extra.xml').write_text('<testsuite/>')
            with self.assertRaisesRegex(ValueError,'^REMOVE exact test report$'):r.junit(path)

    def test_explicit_profile_cannot_alias_legacy_or_other_size(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'transition-round-result.json'
            for result,profile in ((e.RESULT,'5-REMOVE'),(dict(e.RESULT,profile='4-REMOVE'),'5-REMOVE'),
                                   (dict(e.RESULT,profile='5-REMOVE'),None)):
                p.write_text(json.dumps(result))
                with self.assertRaisesRegex(ValueError,'^transition round scope$'):e.validate(root,profile)

    def test_declared_size_is_sent_to_physical_and_lifecycle_readers(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'transition-round-result.json').write_text(json.dumps(dict(e.RESULT,profile='5-REMOVE')))
            with patch.object(e.continuous,'history',return_value={}) as history,patch.object(e,'lifecycle') as lifecycle:
                result=e.validate(root,'5-REMOVE')
            history.assert_called_once_with(root,'transition-round-result.json',size=5,current_maintenance=True);lifecycle.assert_called_once_with(root,size=5)
            self.assertEqual('5-REMOVE',result['profile']);self.assertFalse(result['phase3Complete'])


if __name__=='__main__':unittest.main()

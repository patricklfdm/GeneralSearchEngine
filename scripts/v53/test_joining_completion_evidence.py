import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from . import joining_completion_evidence as e
from . import joining_profile_run as r
from . import test_joining_profile_run as prefix_tests


class JoiningCompletionEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_supply_successful_rejections(self):
        with patch.object(e.c.collection,'inventory',return_value={}),patch.object(e,'validate',side_effect=ValueError('bad original')),patch.object(e.shutil,'copytree') as copying:
            with self.assertRaisesRegex(ValueError,'^bad original$'):e.qualify(Path('/original'),'4-ADD')
            copying.assert_not_called()

    def test_an_unrelated_failure_cannot_pass_as_the_expected_rejection(self):
        with patch.object(e.c.collection,'inventory',return_value={}),patch.object(e,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(e,'mutate'),patch.object(e.shutil,'copytree'):
            with self.assertRaisesRegex(ValueError,'^joining completion unrelated negative:'):e.qualify(Path('/original'),'3-REPLACE')

    def test_complete_gate_rejects_a_prefix_for_each_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            # Complete end checks must not be reachable from an empty prefix,
            # even when producer labels claim completion.
            (root/'joining-continuation-result.json').write_text('{"status":"PASS","stableColdReopened":true}')
            for profile in e.PROFILES:
                with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'^joining complete consecutive applied history$'):
                    e.validate(root,profile)

    def test_explicit_profile_and_reader_scope_cannot_be_promoted_by_labels(self):
        for profile in e.PROFILES:
            size,kind,_,_=e.topology(profile)
            with patch.object(e.c,'validate',return_value=dict(status='PASS',phase3Complete=False,completePhysicalQualified=False)) as validate:
                got=e.validate(Path('/original'),profile)
                validate.assert_called_once_with(Path('/original'),size=size,kind=kind)
                self.assertTrue(got['semanticFinalAndColdQualified']);self.assertFalse(got['finalAndColdReopenQualified'])
                self.assertFalse(got['phase3Complete']);self.assertFalse(got['completePhysicalQualified'])
        with patch.object(e.c,'validate') as validate:
            with self.assertRaisesRegex(ValueError,'^joining prefix profile$'):e.validate(Path('/original'),'5-ADD')
            validate.assert_not_called()

    def test_complete_execution_never_accepts_prefix_junit_and_vice_versa(self):
        fixture=prefix_tests.JoiningProfileRunTest();fixture.setUp()
        try:
            fixture.report()
            with self.assertRaisesRegex(ValueError,'^joining prefix exact passing test$'):r.junit(fixture.root,r.COMPLETE_METHOD)
            fixture.report(method=r.COMPLETE_METHOD)
            self.assertEqual(r.COMPLETE_METHOD,r.junit(fixture.root,r.COMPLETE_METHOD)['method'])
            with self.assertRaisesRegex(ValueError,'^joining prefix exact passing test$'):r.junit(fixture.root)
        finally:fixture.doCleanups()

    def test_failed_complete_native_history_is_retained_and_never_falls_back_to_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'run'
            def source(repo,work):work.mkdir();return dict(head='b'*40,files={})
            with patch.object(r.h,'source_copy',side_effect=source),patch.object(r.h,'execute',return_value=dict(exit=1)) as execute, \
                 patch.object(r.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='toolchain',stderr='')),redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'^joining prefix Maven failed;'):r.run(root,'mvn','4-ADD',complete=True)
            execute.assert_called_once();command=execute.call_args.args[0]
            self.assertIn('-Dtest='+r.h.CLASS.rsplit('.',1)[-1]+'#'+r.COMPLETE_METHOD,command)
            self.assertNotIn('-Dtest='+r.TEST,command)
            receipt=json.loads((root/'receipt.json').read_bytes())
            self.assertEqual('FAIL',receipt['status']);self.assertTrue(receipt['completeExecutionRequested'])
            self.assertEqual(0,receipt['retries']);self.assertFalse(receipt['semanticFinalAndColdQualified'])


if __name__=='__main__':unittest.main()

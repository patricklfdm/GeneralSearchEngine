import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import joining_profile_run as r
from . import joining_profile_evidence as e


class JoiningProfileRunTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_unsupported_selector_is_rejected_before_creating_output(self):
        for profile in ('5-ADD','4-REMOVE','03-ADD','3-add',None):
            with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'^joining prefix profile$'):
                r.run(self.root/'out','mvn',profile)
        self.assertFalse((self.root/'out').exists())

    def test_exact_case_failure_is_retained_without_retry_or_replay(self):
        for profile in e.PROFILES:
            output=self.root/profile
            def source(repo,work):work.mkdir();return dict(head='a'*40,files={})
            with patch.object(r.h,'source_copy',side_effect=source),patch.object(r.h,'execute',return_value=dict(exit=1)) as execute, \
                 patch.object(r.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='toolchain',stderr='')),redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'^joining prefix Maven failed;'):r.run(output,'mvn',profile)
            execute.assert_called_once();command=execute.call_args.args[0]
            self.assertIn('-Dtest='+r.TEST,command);self.assertEqual(['-Dv53.joining.profile='+profile,'test'],command[-2:])
            self.assertFalse(any('sourceFault' in v for v in command))
            receipt=json.loads((output/'receipt.json').read_bytes())
            self.assertEqual('FAIL',receipt['status']);self.assertEqual(0,receipt['retries'])
            for field in ('semanticChainQualified','finalAndColdReopenQualified','phase3Complete'):
                self.assertFalse(receipt[field])

    def test_existing_output_is_never_overwritten(self):
        with self.assertRaises(FileExistsError),patch.object(r.h,'source_copy') as source:r.run(self.root,'mvn','4-ADD')
        source.assert_not_called()

    def test_reused_source_output_cannot_be_nested_in_original(self):
        with self.assertRaisesRegex(ValueError,'^recorded source execution separation$'):
            r.run(self.root/'nested','mvn','3-REPLACE',source_from=self.root)
        self.assertFalse((self.root/'nested').exists())

    def report(self,method=r.METHOD,**kwargs):
        attrs=dict(name=r.h.CLASS,tests='1',failures='0',errors='0',skipped='0');attrs.update(kwargs)
        suite=ET.Element('testsuite',attrs);ET.SubElement(suite,'testcase',dict(classname=r.h.CLASS,name=method))
        ET.ElementTree(suite).write(self.root/'TEST-prefix.xml');return suite

    def test_only_the_exact_successful_prefix_can_supply_execution_status(self):
        self.report();self.assertEqual(1,r.junit(self.root)['tests'])
        for params in (dict(method=r.h.METHOD),dict(tests='2'),dict(skipped='1'),dict(failures='1'),dict(errors='1')):
            self.report(**params)
            with self.subTest(params=params),self.assertRaisesRegex(ValueError,'^joining prefix exact passing test$'):r.junit(self.root)
        self.report();(self.root/'TEST-other.xml').write_bytes((self.root/'TEST-prefix.xml').read_bytes())
        with self.assertRaisesRegex(ValueError,'^joining prefix exact test report$'):r.junit(self.root)


if __name__=='__main__':unittest.main()

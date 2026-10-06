import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from scripts import ci_v51_python as lanes


def ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from ids(item)
        else:
            yield item.id()


class PythonLanesTest(unittest.TestCase):
    def test_partition_matches_complete_discovery_without_duplicates(self):
        loader = unittest.TestLoader()
        original = sorted(ids(loader.discover(str(lanes.ROOT/'scripts/v51'), top_level_dir=str(lanes.ROOT))))
        selected = lanes.partition(lanes.inventory())
        actual = [test for modules in selected.values() for test in ids(loader.loadTestsFromNames(modules))]
        self.assertFalse(loader.errors)
        self.assertTrue(all(selected.values()))
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(original, sorted(actual))

    def test_new_modules_cannot_silently_miss_all_lanes(self):
        modules = ['scripts.v51.test_new_runtime', 'scripts.v51.test_cloud_new_policy', *lanes.STORAGE]
        selected = lanes.partition(modules)
        self.assertCountEqual(modules, [name for group in selected.values() for name in group])
        self.assertIn(modules[0], selected['core'])
        self.assertIn(modules[1], selected['admission'])
        self.assertEqual(sorted(lanes.STORAGE), selected['storage'])

    def test_failures_import_errors_and_empty_suites_do_not_pass(self):
        class Failure(unittest.TestCase):
            def runTest(self): self.fail('expected fixture failure')
        suites = [unittest.TestSuite([Failure()]), unittest.TestSuite(),
                  unittest.TestLoader().loadTestsFromName('scripts.v51.test_missing_ci_fixture')]
        for suite in suites:
            with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
                output=Path(tmp)/'evidence'
                self.assertFalse(lanes.run_suite(suite,output,'core',['fixture']))
                self.assertEqual('FAIL',json.loads((output/'receipt.json').read_text())['status'])

    def test_success_retains_executed_count_and_per_test_timing(self):
        suite=unittest.TestSuite([unittest.FunctionTestCase(lambda:None)])
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            output=Path(tmp)/'evidence'
            self.assertTrue(lanes.run_suite(suite,output,'core',['fixture']))
            receipt=json.loads((output/'receipt.json').read_text())
            self.assertEqual((1,1,0,0),(receipt['expected'],receipt['executed'],receipt['failures'],receipt['errors']))
            self.assertEqual(1,len((output/'timings.jsonl').read_text().splitlines()))

    def test_preflight_parts_preserve_every_default_command_and_timeout(self):
        # Execute the shell control flow, substituting only its Python boundary.
        # Record the original timeout too, so a split cannot extend a gate budget.
        def capture(args):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);log=root/'commands';hooks=root/'hooks.sh'
                hooks.write_text('python3() { echo "python3 $*" >> "$CI_CAPTURE"; }\n'
                                 'timeout() { echo "timeout $*" >> "$CI_CAPTURE"; }\n')
                result=subprocess.run(['bash',str(lanes.ROOT/'scripts/verify-v51-phase6-cloud-preflight.sh'),*args],
                    env=dict(os.environ,BASH_ENV=str(hooks),CI_CAPTURE=str(log)),capture_output=True,text=True)
                self.assertEqual(0,result.returncode,result.stderr)
                workspace=re.search(r'v51CloudPreflightEvidence=(\S+)',result.stdout).group(1)
                self.addCleanup(shutil.rmtree,workspace)
                return log.read_text().replace(workspace,'<work>').splitlines()
        complete=capture([])
        parts=[line for lane in ('admission','cleanup','storage') for line in capture(['--lane',lane])]
        self.assertEqual(complete,parts)
        modules=[name for line in parts if line.startswith('python3 -m unittest ') for name in line.split()[3:]]
        self.assertEqual(19,len(modules))
        self.assertIn('scripts.v51.test_cloud_experiment_resources', modules)
        self.assertIn('scripts.v51.test_cloud_runner_artifacts', modules)
        self.assertIn('scripts.v51.test_cloud_runner_admission', modules)
        self.assertIn('scripts.v51.test_cloud_runner_resources', modules)
        self.assertIn('scripts.v51.test_cloud_runner_iap', modules)
        self.assertIn('scripts.v51.test_cloud_runner_guest_setup', modules)
        self.assertEqual(len(modules),len(set(modules)))

    def test_invalid_preflight_lane_is_rejected_before_running_tests(self):
        result=subprocess.run(['bash',str(lanes.ROOT/'scripts/verify-v51-phase6-cloud-preflight.sh'),'--lane','unknown'],
                              capture_output=True,text=True)
        self.assertEqual(2,result.returncode)


if __name__=='__main__':unittest.main()

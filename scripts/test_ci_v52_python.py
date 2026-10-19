"""Exhaustive partition and unchanged complete-history command contracts."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tarfile
import unittest
from scripts import ci_v52_python as lanes
from scripts.test_ci_v51_python import ids
from scripts import ci_suites


class PartitionTest(unittest.TestCase):
    def test_required_workflow_runs_every_partition_once(self):
        registry=ci_suites.check();jobs=ci_suites.job_blocks((lanes.ROOT/ci_suites.WORKFLOW).read_text())
        rows={row['id']:row for row in registry['suites']}
        calls=[]
        for job,body in jobs.items():
            fields=ci_suites.fields(body,4)
            for step in ci_suites.steps(fields['steps']).values():
                if 'run' in step and 'scripts.ci_v52_python' in ''.join(step['run']):
                    self.assertNotIn('if',step)
                    calls.append((job,ci_suites.scalar(step['run'])))
        self.assertCountEqual([('python-v52-'+lane,'python3 -m scripts.ci_v52_python '+lane+
                               ' --output target/python-v52-'+lane) for lane in lanes.LANES],calls)
        for job,_ in calls:
            self.assertEqual(['changes'],rows[job]['needs'])
            self.assertEqual(('success','success','skipped'),tuple(rows[job][p+'Result'] for p in ('full','integration','docs')))
    def test_every_discovered_case_and_the_existing_cross_version_suite_runs_once(self):
        loader=unittest.TestLoader();original=list(ids(loader.discover(str(lanes.ROOT/'scripts/v52'),top_level_dir=str(lanes.ROOT))))
        original+=list(ids(loader.loadTestsFromName(lanes.EXTRA)))
        chosen=lanes.partition(lanes.inventory());actual=[test for modules in chosen.values() for test in ids(loader.loadTestsFromNames(modules))]
        self.assertFalse(loader.errors);self.assertTrue(all(chosen.values()))
        self.assertEqual(len(actual),len(set(actual)));self.assertCountEqual(original,actual)
    def test_new_modules_have_safe_defaults_and_invalid_or_duplicate_names_fail(self):
        names=['scripts.v52.test_new','scripts.v52.test_cloud_new','scripts.v52.test_remote_new','scripts.v52.test_measurement_new']
        chosen=lanes.partition(names)
        for name,lane in zip(names,('core','cloud-control','transport','measurement')):self.assertIn(name,chosen[lane])
        for bad in ([names[0],names[0]],['scripts.v51.test_unknown']):
            with self.assertRaises(ValueError):lanes.partition(bad)
    def capture(self,script,args):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);hooks=root/'hooks';log=root/'commands'
            scripts=root/'scripts';scripts.mkdir()
            (scripts/script).write_bytes((lanes.ROOT/'scripts'/script).read_bytes())
            version=scripts/'verify-version-alignment.sh'
            version.write_text('#!/usr/bin/env bash\necho "verify-version-alignment" >> "$CI_CAPTURE"\n');version.chmod(0o755)
            hooks.write_text('python3() { echo "python3 $*" >> "$CI_CAPTURE"; }\n'
                             'timeout() { echo "timeout $*" >> "$CI_CAPTURE"; }\n')
            result=subprocess.run(['bash',str(scripts/script),'--skip-build',*args],
                env=dict(os.environ,BASH_ENV=str(hooks),CI_CAPTURE=str(log)),capture_output=True,text=True)
            self.assertEqual(0,result.returncode,result.stderr)
            value=log.read_text() if log.exists() else ''
            for path in re.findall(r'v52\w+Evidence=(\S+)',result.stdout):
                # Foundation prints /evidence inside its fresh workspace.
                work=Path(path).parent
                value=value.replace(str(work),'<work>')
            return value.splitlines()
    def test_measurement_parts_preserve_all_original_commands_and_timeouts(self):
        script='verify-v52-phase6-measurement-runtime.sh';original=self.capture(script,[])
        pieces=[row for lane in ('unit','consumers','commands','installed') for row in self.capture(script,['--lane',lane])]
        self.assertEqual(original,pieces)
        legacy=[v for row in original if row.startswith('python3 -m unittest ') for v in row.split()[3:]]
        self.assertEqual(len(legacy),len(set(legacy)));self.assertLessEqual(set(legacy),set(lanes.inventory()))
        self.assertEqual(7,len([v for v in original if 'python3 -m scripts.v52.' in v]))
    def test_foundation_only_moves_discovered_python_tests(self):
        script='verify-v52-phase1-foundation.sh';original=self.capture(script,[]);moved=self.capture(script,['--skip-python'])
        self.assertEqual([v for v in original if not v.startswith('python3 -m unittest discover ')],moved)
        self.assertEqual(1,len(original)-len(moved))
        self.assertIn('python3 -m unittest scripts.test_build_coordinates',moved)
    def test_invalid_modes_fail_before_any_work(self):
        for script,args in (
            ('verify-v52-phase1-foundation.sh',['--skip-python']),
            ('verify-v52-phase1-foundation.sh',['--skip-build','--skip-build']),
            ('verify-v52-phase6-measurement-runtime.sh',['--lane','unknown']),
            ('verify-v52-phase6-measurement-runtime.sh',['--lane']),
            ('verify-v52-phase6-measurement-runtime.sh',['--lane','unit','--lane','consumers'])):
            result=subprocess.run(['bash',str(lanes.ROOT/'scripts'/script),*args],capture_output=True,text=True)
            self.assertEqual(2,result.returncode)

    def test_installed_failure_artifact_packages_fixture_links_without_traversal(self):
        jobs=ci_suites.job_blocks((lanes.ROOT/ci_suites.WORKFLOW).read_text())
        steps=ci_suites.steps(ci_suites.fields(jobs['v52-installed-runtime'],4)['steps'])
        name='Package V5.2 installed evidence without following fixture symlinks'
        self.assertLess(list(steps).index('Verify complete V5.2 installed qualification'),list(steps).index(name))
        self.assertLess(list(steps).index(name),list(steps).index('Retain complete qualification evidence including failures'))
        self.assertEqual(ci_suites.ALWAYS,ci_suites.scalar(steps[name]['if']))
        upload=steps['Retain complete qualification evidence including failures']
        self.assertEqual(ci_suites.ALWAYS,ci_suites.scalar(upload['if']))
        self.assertEqual('target/v52-installed-runtime.tar.gz',
                         ci_suites.scalar(ci_suites.fields(upload['with'][1],10)['path']))
        self.assertEqual('|',steps[name]['run'][0])
        script=steps[name]['run'][1]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'target/v52-measurement-runtime';source.mkdir(parents=True)
            outside=root/'outside';outside.mkdir();(outside/'never-upload').write_bytes(b'private host bytes')
            path=source/'run/native-storage-root/symlink-parent/rootfs/var/lib/gse-v52-volume'
            path.parent.mkdir(parents=True);path.symlink_to(outside)
            (source/'receipt.json').write_text('{"status":"FAIL","original":true}\n')
            outside.chmod(0)
            try:
                result=subprocess.run(['bash','-e','-c',script],cwd=root,
                    env=dict(os.environ,PYTHONPATH=str(lanes.ROOT)),capture_output=True,text=True)
            finally:outside.chmod(0o700)
            self.assertEqual(0,result.returncode,result.stderr)
            with tarfile.open(root/'target/v52-installed-runtime.tar.gz','r:gz') as archive:
                self.assertTrue(archive.getmember('v52-measurement-runtime/'+str(path.relative_to(source))).issym())
                self.assertFalse(any('never-upload' in v.name for v in archive.getmembers()))
                self.assertEqual((source/'receipt.json').read_bytes(),archive.extractfile('v52-measurement-runtime/receipt.json').read())
            self.assertTrue(path.is_symlink());self.assertEqual(b'private host bytes',(outside/'never-upload').read_bytes())


if __name__=='__main__':unittest.main()

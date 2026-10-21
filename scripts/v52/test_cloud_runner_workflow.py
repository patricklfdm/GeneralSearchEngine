"""Actual workflow contract and pre-auth identity/output boundary."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_runner_workflow as w, cloud_credentials_offline as auth
from .test_cloud_preflight import configuration
from .test_cloud_prepared import arguments
from .evidence import encoded


class WorkflowTest(unittest.TestCase):
    def test_actual_source_is_manual_master_only_and_uses_exact_required_job_steps(self):
        source=w.contract();self.assertEqual(w.render(),source)
        self.assertIn('timeout-minutes: 1380',source);self.assertNotIn('timeout --signal',source)
        self.assertIn('runs-on: [self-hosted, Linux, X64, gse-v52-cloud-d-wsl]',source)
        self.assertIn('python -u -m scripts.v52.cloud_self_hosted execute',source)
        self.assertLess(source.index('name: Verify dedicated self-hosted Runner'),source.index('name: '+w.origin.IDENTITY))
        self.assertIn('cancel-in-progress: false',source);self.assertEqual(2,source.count('retention-days: 90'))
        self.assertIn('path: target/v52-runner/result',source);self.assertIn('path: target/v52-runner/diagnostics',source)
        self.assertNotIn('path: target/v52-runner\n',source)
        jobs=w.origin.yaml.job_blocks(source);steps=w.origin.yaml.steps(w.origin.yaml.fields(jobs['runner'],4)['steps'])
        self.assertEqual(w.origin.REQUIRED,tuple(name for name in steps if name in w.origin.REQUIRED))
        for name,step in steps.items():
            if 'run' in step:
                run=step['run'][1]
                self.assertNotIn('${{ inputs.',run)
                result=subprocess.run(['bash','-n'],input=run,text=True,capture_output=True)
                self.assertEqual(0,result.returncode,(name,result.stderr))
    def test_bootstrap_validates_native_context_and_outputs_only_public_identity(self):
        cfg=configuration();_,env,_,invocation,_=auth.fixture(cfg['provider'],'runner','a'*40)
        estimate=arguments()['quote'];env.update(V52_OPERATION='prepare',V52_REQUEST=encoded(dict(member='experiment',sequence='c'*32,estimate=estimate)).decode())
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'actions';target.touch();env['GITHUB_OUTPUT']=str(target)
            with patch.dict(os.environ,env,clear=True),patch.object(w.reads,'source_configuration',return_value=cfg), \
                 patch.object(w.credentials,'github',side_effect=lambda path,end,clock:invocation.get(path,end)):
                w.identity_native('a'*40,root/'identity')
            outputs=target.read_text();self.assertIn('provider=projects/',outputs);self.assertIn('serviceAccount=gse-v52-runner@',outputs)
            self.assertNotIn('token',outputs);self.assertFalse(w.artifacts.read(root/'identity/identity.json')['credentialExchangeCompleted'])
    def test_actions_outputs_reject_unknown_newline_and_symlink_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'actions';path.touch();link=root/'link';link.symlink_to(path)
            for values in (dict(token='secret'),dict(artifactName='safe\nserviceAccount=other')):
                with self.assertRaises(ValueError):w.outputs(values,{'GITHUB_OUTPUT':str(path)})
            with self.assertRaises(OSError):w.outputs(dict(artifactName='safe'),{'GITHUB_OUTPUT':str(link)})
            self.assertEqual('',path.read_text())


if __name__=='__main__':unittest.main()

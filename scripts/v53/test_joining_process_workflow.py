"""Authority/topology guards for the opt-in hosted subset, not a Required gate."""
from pathlib import Path
import re
import unittest
from . import joining_process_hosted as h


class JoiningProcessWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.text=(h.h.ROOT/h.WORKFLOW).read_text()
        self.jobs={name:body for name,body in re.findall(r'^  (prepare|execute|verify|aggregate):\n(.*?)(?=^  \w+:|\Z)',self.text,re.M|re.S)}

    def test_only_opt_in_entry_and_read_only_permissions(self):
        event=self.text.split('\non:\n',1)[1].split('\npermissions:',1)[0]
        self.assertEqual({'workflow_dispatch','push'},set(re.findall(r'^  ([a-z_]+):',event,re.M)))
        self.assertIn('branches: [experiment/v53-joining-process]',event)
        self.assertEqual('  contents: read',self.text.split('permissions:\n',1)[1].split('\n\n',1)[0])
        self.assertNotRegex(self.text,r'secrets\.|id-token:|workflow_call:|continue-on-error:|retry')
        self.assertIn('cancel-in-progress: false',self.text)

    def test_separate_original_and_downloaded_replay_without_workflow_parallel_cap(self):
        self.assertEqual({'prepare','execute','verify','aggregate'},set(self.jobs))
        for job in ('execute','verify'):
            self.assertIn('fail-fast: false',self.jobs[job]);self.assertNotIn('max-parallel:',self.jobs[job])
            self.assertIn('matrix: ${{ fromJSON(needs.prepare.outputs.matrix) }}',self.jobs[job])
        self.assertIn('needs: [prepare, execute]',self.jobs['verify'])
        self.assertIn('needs: [prepare, execute, verify]',self.jobs['aggregate'])
        self.assertIn("needs.prepare.result == 'success'",self.jobs['verify'])
        self.assertIn('EXECUTE_RESULT: ${{ needs.execute.result }}',self.jobs['aggregate'])
        self.assertIn('VERIFY_RESULT: ${{ needs.verify.result }}',self.jobs['aggregate'])
        self.assertIn('merge-multiple: false',self.jobs['aggregate'])
        for body in self.jobs.values():
            self.assertIn('runs-on: ubuntu-24.04',body)
            self.assertIn('ref: ${{ github.sha }}',body);self.assertIn('persist-credentials: false',body)

    def test_all_artifact_names_pin_run_attempt_source_and_retain_failures(self):
        bindings=re.findall(r'^          (?:name|pattern): (v53-joining-process-.+)$',self.text,re.M)
        self.assertGreaterEqual(len(bindings),10)
        for binding in bindings:
            self.assertIn('${{ github.run_id }}-${{ github.run_attempt }}-${{ github.sha }}',binding)
        for name in ('execute','verify','aggregate'):
            self.assertIn('if: ${{ always() }}',self.jobs[name]);self.assertIn('retention-days: 90',self.jobs[name])
        self.assertIn('--shard "$JOINING_PROCESS_SHARD"',self.jobs['execute'])
        self.assertNotIn('matrix.id }}"',self.text)
        self.assertEqual(120,len(h.SHARDS))
        self.assertEqual(360,len(h.m.KINDS))
        self.assertLessEqual(2*len(h.SHARDS),256)

    def test_external_actions_and_tool_versions_are_pinned_without_shared_cache(self):
        setup=(h.h.ROOT/'.github/actions/v53-process-setup/action.yml').read_text()
        for name in re.findall(r'uses: (\S+)',self.text+'\n'+setup):
            self.assertTrue(name.startswith('./') or re.fullmatch(r'[\w-]+/[\w-]+@[0-9a-f]{40}',name),name)
        self.assertIn("java-version: '21.0.12+8.0.LTS'",setup)
        self.assertIn("python-version: '3.11'",setup);self.assertNotIn('cache:',setup)
        props=(h.h.ROOT/'.mvn/wrapper/maven-wrapper.properties').read_text()
        self.assertIn('apache-maven-3.9.11-bin.zip',props)
        self.assertRegex(props,r'distributionSha256Sum=[0-9a-f]{64}')

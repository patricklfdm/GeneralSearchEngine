"""Offline handoff/queue guards; synthetic provenance supplies no run credit."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import phase3_execution_plan as m


class ExecutionPlanTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.source='a'*40;self.ref='feat/v53-cluster-operations'
        paths=[a.WORKFLOW for adapters in (m.seeds.adapters(),m.resources.adapters(),m.maximum.adapters()) for a in adapters.values()]
        self.snapshot=dict(head=self.source,files={p:m.plan.digest((m.plan.ROOT/p).read_bytes()) for p in paths})

    def generate(self,source_reads=None):
        with patch.object(m.seeds,'checkout_source',side_effect=source_reads or [copy.deepcopy(self.snapshot)]*2), \
             patch.object(m.subprocess,'check_output',return_value=self.source+'\n') as git, \
             patch.object(m.workflows,'github',side_effect=AssertionError('no network')) as api:
            result=m.run(self.source,self.ref,self.root/'output')
        api.assert_not_called();git.assert_called_once_with(
            ['git','rev-parse','--verify','refs/heads/'+self.ref],cwd=m.plan.ROOT,text=True)
        return result

    def test_actual_complete_contracts_and_distinct_parallel_resource_sets(self):
        value=self.generate()
        self.assertEqual((18,565,566,260),(value['workflowCount'],value['selectedJobs'],value['wholeHistories'],value['wholeHistoryGroups']))
        self.assertEqual({'histories':544,'resources':15,'maximum':6},value['selectedJobsByFamily'])
        self.assertEqual(3,sum(r['requiresLargeHost'] for r in value['workflows']))
        self.assertEqual('PLANNED',value['status']);self.assertFalse(value['phase3Complete']);self.assertFalse(value['runtimeQualified'])
        self.assertEqual(0,value['workflowsDispatched']);self.assertEqual(5,len(value['openGaps']))
        for row in value['workflows']:
            self.assertEqual(row['selectedJobs'],sum(r['jobs'] for r in row['roles'].values()))
            self.assertEqual(['gh','workflow','run',Path(row['workflow']).name,'--repo',m.workflows.REPOSITORY,'--ref',self.ref],row['dispatchCommand'])
            if row['requiresLargeHost']:self.assertEqual(dict(group=m.workflows.LARGE_CONCURRENCY_GROUP,queue='max',cancelInProgress=False),row['concurrency'])
        capacities=value['machineRequirements'];gib=1024**3
        self.assertEqual(448*gib,capacities['finalReplayFreeBytesAfterInputs'])
        self.assertEqual({'execute':280*gib,'verify-download':416*gib,'verify':288*gib},capacities['maximumHostedFreeBytes'])
        text=(self.root/'output/EXECUTION.md').read_text();self.assertEqual(18,text.count('gh workflow run '))
        self.assertIn('No workflow or experiment was started',text);self.assertIn('after inputs',text)

    def test_all_three_large_contracts_reject_pending_eviction_or_cancel(self):
        targets=[('maximum-image',m.resources.adapters()['maximum-image'],m.resources.contract)]
        targets += [(name,a,m.maximum.contract) for name,a in m.maximum.adapters().items()]
        for name,a,contract in targets:
            text=(m.plan.ROOT/a.WORKFLOW).read_text()
            for old,new in [('  queue: max\n',''),('queue: max','queue: single'),
                            ('cancel-in-progress: false','cancel-in-progress: true'),
                            (m.workflows.LARGE_CONCURRENCY_GROUP,'other-runner')]:
                with self.subTest(name=name,change=new),self.assertRaisesRegex(ValueError,'non-evicting concurrency'):
                    contract(name,a,text.replace(old,new))

    def test_changed_workflow_bytes_cannot_use_original_source_pin(self):
        snapshot=copy.deepcopy(self.snapshot);snapshot['files'][next(iter(snapshot['files']))]='0'*64
        with self.assertRaisesRegex(ValueError,'workflow/source drift'):self.generate([snapshot])
        self.assertFalse((self.root/'output').exists())

    def test_actual_adapters_accept_one_manual_frozen_ref_with_exact_workflow_source(self):
        for adapters in (m.seeds.adapters(),m.resources.adapters(),m.maximum.adapters()):
            for name,a in adapters.items():
                env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=m.workflows.REPOSITORY,GITHUB_SHA=self.source,
                    GITHUB_REF='refs/heads/'+self.ref,GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ID='123',
                    GITHUB_RUN_ATTEMPT='1',V53_WORKFLOW_REF=m.workflows.REPOSITORY+'/'+a.WORKFLOW+'@refs/heads/'+self.ref,
                    V53_WORKFLOW_SHA=self.source)
                with self.subTest(name=name),patch.dict('os.environ',env,clear=True), \
                     patch.object(m.subprocess,'check_output',return_value=self.source+'\n'):
                    actual=a.context()
                    self.assertEqual('refs/heads/'+self.ref,actual['ref']);self.assertEqual(self.source,actual['source'])
                    self.assertEqual(a.WORKFLOW,actual['workflow'])

    def test_changed_source_during_inspection_leaves_no_completed_plan(self):
        changed=copy.deepcopy(self.snapshot);changed['head']='b'*40
        with self.assertRaisesRegex(ValueError,'source changed'):self.generate([self.snapshot,changed])
        self.assertFalse((self.root/'output').exists())

    def test_dirty_source_rejected_before_output_or_git_branch_lookup(self):
        with patch.object(m.seeds,'checkout_source',side_effect=ValueError('seed cohort dirty checkout')), \
             patch.object(m.subprocess,'check_output') as git,self.assertRaisesRegex(ValueError,'dirty checkout'):
            m.run(self.source,self.ref,self.root/'output')
        git.assert_not_called();self.assertFalse((self.root/'output').exists())

    def test_remote_branch_is_not_assumed_from_a_different_local_commit(self):
        with patch.object(m.seeds,'checkout_source',return_value=self.snapshot), \
             patch.object(m.subprocess,'check_output',return_value='b'*40+'\n'),self.assertRaisesRegex(ValueError,'branch is not selected source'):
            m.run(self.source,self.ref,self.root/'output')
        self.assertFalse((self.root/'output').exists())

    def test_invalid_refs_cannot_be_rendered_as_commands(self):
        for ref in ['--help','$(touch x)','topic\nmain','a..b','a//b','a.lock','a/.b','refs/heads/x/']:
            with self.subTest(ref=ref),patch.object(m.seeds,'checkout_source') as checkout,self.assertRaisesRegex(ValueError,'branch'):
                m.run(self.source,ref,self.root/'output')
            checkout.assert_not_called()

    def test_existing_outputs_and_source_paths_are_not_overwritten(self):
        path=self.root/'output';path.mkdir();marker=path/'original';marker.write_text('preserved')
        with patch.object(m.seeds,'checkout_source') as checkout,self.assertRaisesRegex(ValueError,'already exists'):
            m.run(self.source,self.ref,path)
        checkout.assert_not_called();self.assertEqual('preserved',marker.read_text())
        with self.assertRaisesRegex(ValueError,'must not dirty source'):
            m.run(self.source,self.ref,m.plan.ROOT/'scripts/v53/not-an-output')

    def test_missing_required_dispatch_inputs_cannot_generate_incomplete_commands(self):
        original=m.plan.regular
        def changed(root,name):
            raw=original(root,name)
            if name.endswith('v53-maximum-queue.yml'):
                return raw.replace(b'  workflow_dispatch:\n',b'  workflow_dispatch:\n    inputs:\n      confirm:\n        required: true\n')
            return raw
        snapshot=copy.deepcopy(self.snapshot);path=m.maximum.adapters()['maximum-queue'].WORKFLOW
        snapshot['files'][path]=m.plan.digest(changed(m.plan.ROOT,path))
        with patch.object(m.plan,'regular',side_effect=changed),self.assertRaisesRegex(ValueError,'dispatch inputs'):
            self.generate([snapshot])


if __name__=='__main__':unittest.main()

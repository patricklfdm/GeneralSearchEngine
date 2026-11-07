"""Synthetic API records; no actual GitHub run or resource history is attested."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import phase3_resource_workflows as r

w=r.observed


class ResourceWorkflowTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.modules=r.adapters();self.sha='a'*40;self.source=dict(head=self.sha,files={})
        self.index=dict(schema=r.INDEX_SCHEMA,source=self.sha,cohorts={});self.api={};self.calls=[];self.counter=0;self.contracts={}
        repo=dict(id=w.REPOSITORY_ID,full_name=w.REPOSITORY,owner=dict(id=w.OWNER_ID))
        for run,(name,module) in enumerate(self.modules.items(),100):
            text=(r.plan.ROOT/module.WORKFLOW).read_text();self.source['files'][module.WORKFLOW]=r.h.digest(text.encode())
            contract=r.contract(name,module,text);self.contracts[name]=contract
            ctx=dict(kind='github',repository=w.REPOSITORY,source=self.sha,ref=module.BRANCH,event='workflow_dispatch',
                     run=str(run),attempt='2',workflow=module.WORKFLOW);self.index['cohorts'][name]=ctx
            base='actions/runs/'+str(run)
            for attempt in (1,2):
                value=dict(id=run,run_attempt=attempt,head_sha=self.sha,head_branch=module.BRANCH.removeprefix('refs/heads/'),
                    event=ctx['event'],path=module.WORKFLOW,workflow_id=run+1000,status='completed',
                    conclusion='success' if attempt==2 else 'failure',updated_at='2026-01-01T00:10:00Z',
                    repository=copy.deepcopy(repo),head_repository=copy.deepcopy(repo))
                jobs=[]
                for number,(job,spec) in enumerate(contract['jobs'].items(),1):
                    start='2026-01-01T00:00:00Z';end='2026-01-01T00:01:00Z'
                    jobs.append(dict(id=run*100000+attempt*1000+number,run_id=run,run_attempt=attempt,head_sha=self.sha,
                        head_branch=value['head_branch'],name=job,status='completed',conclusion='success' if attempt==2 else 'failure',
                        started_at=start,completed_at=end,steps=[dict(name=n,number=k,status='completed',conclusion='success',
                            started_at=start,completed_at=end) for k,n in enumerate(spec['steps'],1)]))
                self.api[base+f'/attempts/{attempt}']=value
                self.api[base+f'/attempts/{attempt}/jobs?per_page=100&page=1']=dict(total_count=len(jobs),jobs=jobs)
                if attempt==2:self.api[base]=copy.deepcopy(value)
        self.path=self.root/'index.json';r.h.save(self.path,self.index)
        p=patch.object(r.seeds,'checkout_source',return_value=self.source);p.start();self.addCleanup(p.stop)

    def get(self,path):self.calls.append(path);return json.dumps(self.api[path],sort_keys=True).encode()

    def collect(self,get=None):
        self.counter+=1;self.output=self.root/str(self.counter)
        with redirect_stdout(io.StringIO()):return r.collect(self.path,self.output,get or self.get)

    def test_actual_source_graphs_have_five_whole_histories_and_fifteen_jobs(self):
        self.assertEqual((4,5,15),(len(self.contracts),sum(c['groups'] for c in self.contracts.values()),
                                sum(len(c['jobs']) for c in self.contracts.values())))
        self.assertEqual({None,'source-queue','queue-completion'},
                         {j['group'] for j in self.contracts['queue-resources']['jobs'].values()})
        result=self.collect()
        self.assertEqual(('PARTIAL',4,15,4),tuple(result[k] for k in ('status','subsets','selectedJobs','priorAttempts')))
        self.assertTrue(result['workflowExecutionAttested']);self.assertTrue(result['priorAttemptsRequireReview'])
        for key in ('originalHistoriesReplayed','failedOriginalsReplayed','runtimeQualified','phase3Complete'):self.assertFalse(result[key])
        self.assertEqual(28,len(self.calls))
        for name in self.modules:self.assertEqual('failure',result['cohorts'][name]['attempts'][0]['conclusion'])

    def test_all_workflows_contexts_and_distinct_runs_are_mandatory(self):
        for i,change in enumerate((lambda v:v['cohorts'].pop('queue-resources'),
                lambda v:v['cohorts']['maximum-image'].update(event='push'),
                lambda v:v['cohorts']['queue-resources'].update(event='push'),
                lambda v:v['cohorts']['required-four'].update(source='b'*40),
                lambda v:v['cohorts']['required-four'].update(run='101'),lambda v:v.update(schema=r.SCHEMA))):
            value=copy.deepcopy(self.index);change(value);r.h.save(self.path,value)
            with self.subTest(mutation=i),self.assertRaises(ValueError):self.collect()
        self.assertEqual([],self.calls)

    def test_only_source_fixed_jobs_runners_planners_and_owner_commands_are_supported(self):
        for name,module in self.modules.items():
            original=(r.plan.ROOT/module.WORKFLOW).read_text()
            for changed in (original.replace('needs: prepare','needs: []'),
                            original.replace('persist-credentials: false','persist-credentials: true'),
                            original.replace('scripts.v53.'+r.WORKFLOWS[name][0]+' verify','echo ignored verify')):
                with self.subTest(workflow=name),self.assertRaises(ValueError):r.contract(name,module,changed)
        name='maximum-image';module=self.modules[name];original=(r.plan.ROOT/module.WORKFLOW).read_text()
        for changed in (original.replace('gse-v53-large-evidence','gse-v52-cloud-d-wsl'),
                        original.replace('clean: false','clean: true'),original.replace('maximum_transition_capacity','other_capacity')):
            with self.assertRaises(ValueError):r.contract(name,module,changed)
        module=self.modules['queue-resources'];original=(r.plan.ROOT/module.WORKFLOW).read_text()
        for changed in (original.replace('max-parallel: 2','max-parallel: 1'),original.replace('fail-fast: false','fail-fast: true'),
                        original.replace('queue_resource_hosted plan','other plan')):
            with self.assertRaises(ValueError):r.contract('queue-resources',module,changed)

    def test_missing_failed_or_skipped_member_and_critical_step_reject(self):
        path='actions/runs/103/attempts/2/jobs?per_page=100&page=1';saved=copy.deepcopy(self.api[path])
        for change in (lambda v:v['jobs'].pop(),lambda v:v['jobs'][1].update(conclusion='failure'),
                       lambda v:v['jobs'][2].update(conclusion='skipped'),lambda v:v['jobs'][0]['steps'].pop()):
            self.api[path]=copy.deepcopy(saved);change(self.api[path])
            with self.assertRaises(ValueError):self.collect()
            self.assertTrue((self.output/'api/queue-resources/attempt-2/jobs-1.json').is_file())

    def test_newer_attempt_and_failed_selected_attempt_cannot_hide_behind_success(self):
        self.api['actions/runs/100']['run_attempt']=3
        with self.assertRaisesRegex(ValueError,'exact context'):self.collect()
        self.api['actions/runs/100']['run_attempt']=2
        for key in ('actions/runs/100','actions/runs/100/attempts/2'):self.api[key]['conclusion']='failure'
        with self.assertRaisesRegex(ValueError,'not successful'):self.collect()
        self.assertEqual('failure',r.seeds.read(self.output/'api/required-four/attempt-2/run.json')['conclusion'])

    def test_collector_keeps_raw_network_failure_and_rejects_source_drift(self):
        def fail(path):
            if 'attempts/2' in path:raise OSError('synthetic unavailable')
            return self.get(path)
        with self.assertRaisesRegex(OSError,'synthetic unavailable'):self.collect(fail)
        self.assertTrue(list((self.output/'api').glob('*/attempt-1/run.json')))
        self.source['files'][self.modules['required-four'].WORKFLOW]='0'*64
        with self.assertRaisesRegex(ValueError,'workflow/source binding'):self.collect()

    def test_artifact_names_distinguish_full_profiles_and_queue_members(self):
        names=set()
        for name,(_,_,members) in r.WORKFLOWS.items():
            ctx=self.index['cohorts'][name]
            names.add(r.artifact_name(name,ctx,'seed'))
            for member in members:names.add(r.artifact_name(name,ctx,'raw',member))
        self.assertEqual(9,len(names))
        with self.assertRaises(ValueError):r.artifact_name('queue-resources',self.index['cohorts']['queue-resources'],'raw','smoke')


if __name__=='__main__':unittest.main()

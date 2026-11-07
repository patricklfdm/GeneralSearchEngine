"""Synthetic exact-attempt API guards; no hosted history is qualified."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import maximum_resource_workflows as r
w=r.observed


class MaximumWorkflowTest(unittest.TestCase):
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


    def test_two_indivisible_components_six_jobs_and_all_prior_attempts(self):
        result=self.collect()
        self.assertEqual((2,6,2),(result['subsets'],result['selectedJobs'],result['priorAttempts']))
        self.assertEqual(14,len(self.calls));self.assertEqual('PARTIAL',result['status'])
        self.assertTrue(result['workflowExecutionAttested']);self.assertTrue(result['priorAttemptsRequireReview'])
        for key in ('originalHistoriesReplayed','failedOriginalsReplayed','runtimeQualified','phase3Complete'):self.assertFalse(result[key])
        for row in result['cohorts'].values():self.assertEqual('failure',row['attempts'][0]['conclusion'])

    def test_complete_source_bound_manual_set_is_required_before_api_access(self):
        changes=[lambda v:v['cohorts'].pop('maximum-native'),lambda v:v.update(schema='old-five-member-set'),
            lambda v:v['cohorts']['maximum-queue'].update(source='b'*40),lambda v:v['cohorts']['maximum-queue'].update(event='push'),
            lambda v:v['cohorts']['maximum-native'].update(run='101'),lambda v:v['cohorts']['maximum-queue'].update(workflow='wrong')]
        for i,change in enumerate(changes):
            value=copy.deepcopy(self.index);change(value);r.h.save(self.path,value)
            with self.subTest(i=i),self.assertRaises(ValueError):self.collect()
        self.assertEqual([],self.calls)

    def test_graph_capacity_download_artifact_and_retention_changes_are_rejected(self):
        for name,module in self.modules.items():
            original=(r.plan.ROOT/module.WORKFLOW).read_text()
            changes=[original.replace('needs: prepare','needs: []'),original.replace('persist-credentials: false','persist-credentials: true'),
                original.replace('gse-v53-large-evidence','gse-v52-cloud-d-wsl'),original.replace('clean: false','clean: true'),
                original.replace('maximum_native_capacity','other_capacity'),original.replace('retention-days: 90','retention-days: 7'),
                original.replace('github.run_attempt','github.run_id'),original.replace('workflow_dispatch:','push:'),
                original.replace('contents: read','contents: write'),
                original.replace('actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803','actions/checkout@v4'),original.replace('scripts.v53.'+r.WORKFLOWS[name][0]+' verify','echo omitted')]
            for i,changed in enumerate(changes):
                with self.subTest(component=name,i=i),self.assertRaises(ValueError):r.contract(name,module,changed)

    def test_current_rerun_and_skipped_critical_steps_cannot_use_an_older_green_result(self):
        base='actions/runs/100';original=copy.deepcopy(self.api)
        for mode in ('rerun','failed','step','job','source'):
            self.api=copy.deepcopy(original)
            if mode=='rerun':self.api[base]['run_attempt']=3
            elif mode=='failed':self.api[base]['conclusion']='failure';self.api[base+'/attempts/2']['conclusion']='failure'
            else:
                job=self.api[base+'/attempts/2/jobs?per_page=100&page=1']['jobs'][0]
                if mode=='step':job['steps'][0]['conclusion']='skipped'
                elif mode=='job':job['conclusion']='cancelled'
                else:job['head_sha']='b'*40
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.collect()
            self.assertEqual('FAIL',r.seeds.read(self.output/'receipt.json')['status'])

    def test_prior_job_pagination_is_complete_and_mixed_attempts_are_rejected(self):
        path='actions/runs/100/attempts/1/jobs?per_page=100&page=1';first=self.api[path]
        original=copy.deepcopy(first['jobs'][0]);jobs=[]
        for i in range(101):jobs.append(dict(original,id=100000000+i,name='prior-'+str(i)))
        self.api[path]=dict(total_count=101,jobs=jobs[:100]);self.api[path[:-1]+'2']=dict(total_count=101,jobs=jobs[100:])
        result=self.collect();self.assertEqual(101,result['cohorts']['maximum-native']['attempts'][0]['jobs'])
        self.api[path[:-1]+'2']['jobs'][0]['run_attempt']=2
        with self.assertRaisesRegex(ValueError,'mixed attempt'):self.collect()
        self.api[path[:-1]+'2']['jobs']=[]
        with self.assertRaisesRegex(ValueError,'truncated'):self.collect()

    def test_read_only_client_rejects_mutating_or_unrelated_endpoint(self):
        with patch.object(w.subprocess,'run') as call:
            for path in ('actions/runs/100/rerun','actions/runs/100/cancel','../settings','actions/artifacts/1'):
                with self.assertRaisesRegex(ValueError,'read-only API path'):w.github(path)
            call.assert_not_called()


if __name__=='__main__':unittest.main()

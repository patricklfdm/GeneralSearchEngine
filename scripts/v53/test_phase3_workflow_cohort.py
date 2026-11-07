"""Synthetic API observations against actual workflow/planner contracts.

These tests execute no hosted histories and confer no GitHub attestation.
"""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from . import phase3_workflow_cohort as w
from . import phase3_attested_cohort as admitted


class Phase3WorkflowCohortTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.modules=w.seeds.adapters();self.catalogs=w.plan.catalogues();self.sha='a'*40
        self.source=dict(head=self.sha,files={a.WORKFLOW:w.h.digest((w.plan.ROOT/a.WORKFLOW).read_bytes()) for a in self.modules.values()})
        self.contracts=w.contracts(self.modules,self.catalogs,self.source)
        self.index=dict(schema=w.seeds.INDEX_SCHEMA,source=self.sha,cohorts={});self.api={};self.calls=[];self.counter=0
        self.repo=dict(id=w.REPOSITORY_ID,full_name=w.REPOSITORY,owner=dict(id=w.OWNER_ID))
        for i,(name,a) in enumerate(self.modules.items(),100):
            ctx=dict(kind='github',repository=w.REPOSITORY,source=self.sha,ref=a.BRANCH,event='push',run=str(i),attempt='2',workflow=a.WORKFLOW)
            self.index['cohorts'][name]=ctx;base='actions/runs/'+str(i)
            for attempt in (1,2):
                run=dict(id=i,run_attempt=attempt,head_sha=self.sha,head_branch=a.BRANCH.removeprefix('refs/heads/'),event='push',
                    path=a.WORKFLOW,workflow_id=i+1000,status='completed',conclusion='success' if attempt==2 else 'failure',
                    updated_at='2026-01-01T00:10:00Z',repository=copy.deepcopy(self.repo),head_repository=copy.deepcopy(self.repo))
                jobs=[]
                for j,(job,spec) in enumerate(self.contracts[name]['jobs'].items(),1):
                    minute={'prepare':0,'execute':2,'verify':4,'aggregate':6}[spec['role']]
                    start=f'2026-01-01T00:0{minute}:00Z';end=f'2026-01-01T00:0{minute+1}:00Z'
                    jobs.append(dict(id=i*100000+attempt*10000+j,run_id=i,run_attempt=attempt,head_sha=self.sha,
                        head_branch=run['head_branch'],name=job,status='completed',conclusion='success' if attempt==2 else 'failure',
                        started_at=start,completed_at=end,steps=[dict(name=n,number=k,status='completed',conclusion='success',
                            started_at=start,completed_at=end) for k,n in enumerate(spec['steps'],1)]))
                self.api[base+f'/attempts/{attempt}']=run
                for page,start in enumerate(range(0,len(jobs),100),1):
                    self.api[base+f'/attempts/{attempt}/jobs?per_page=100&page={page}']=dict(total_count=len(jobs),jobs=jobs[start:start+100])
                if attempt==2:self.api[base]=copy.deepcopy(run)
        self.index_path=self.root/'index.json';w.h.save(self.index_path,self.index)
        mock=patch.object(w.seeds,'checkout_source',return_value=self.source);mock.start();self.addCleanup(mock.stop)

    def get(self,path):
        self.calls.append(path);return json.dumps(self.api[path],sort_keys=True).encode()

    def run_gate(self,get=None):
        self.counter+=1;self.output=self.root/f'observed-{self.counter}'
        with redirect_stdout(io.StringIO()):return w.collect(self.index_path,self.output,get or self.get)

    def jobs(self,name='profiles'):
        ctx=self.index['cohorts'][name];base='actions/runs/'+ctx['run']+'/attempts/2/jobs?per_page=100&page='
        values=[];page=1
        while base+str(page) in self.api:values.extend(self.api[base+str(page)]['jobs']);page+=1
        return values

    def test_all_actual_planners_match_the_complete_job_contract(self):
        self.assertEqual(544,sum(len(v['jobs']) for v in self.contracts.values()))
        self.assertEqual(260,sum(v['groups'] for v in self.contracts.values()))
        for name,adapter in self.modules.items():
            with self.subTest(cohort=name),patch.object(adapter,'context',return_value=self.index['cohorts'][name]), \
                    patch('sys.argv',['hosted','plan']),redirect_stdout(io.StringIO()) as out:adapter.main()
            matrix=json.loads(out.getvalue());ids=[v['id'] for v in matrix['include']]
            jobs=self.contracts[name]['jobs'];self.assertEqual(len(ids),sum(v['role']=='execute' for v in jobs.values()))
            for slug in ids:
                self.assertEqual(2,sum(n.endswith('('+slug+')') for n in jobs))

    def test_complete_pages_and_all_attempts_retained_without_acceptance(self):
        before=copy.deepcopy(self.api);result=self.run_gate()
        self.assertEqual(('PARTIAL',12,544,12),tuple(result[k] for k in ('status','subsets','selectedJobs','priorAttempts')))
        self.assertTrue(result['workflowExecutionAttested']);self.assertTrue(result['priorAttemptsRequireReview'])
        for k in ('runtimeQualified','originalHistoriesReplayed','failedOriginalsReplayed','phase3Complete'):self.assertFalse(result[k])
        self.assertEqual(before,self.api)
        for attempt in (1,2):
            for page in (1,2,3):self.assertIn(f'actions/runs/104/attempts/{attempt}/jobs?per_page=100&page={page}',self.calls)
        for name in self.modules:self.assertEqual('failure',result['cohorts'][name]['attempts'][0]['conclusion'])
        inventory=w.seeds.read(self.output/'api-inventory.json')
        for file,entry in inventory.items():self.assertEqual(entry['sha256'],w.h.digest((self.output/file).read_bytes()))

    def test_read_only_transport_fixed_host_and_duplicate_json_rejected(self):
        with patch.object(w.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'{"x":1}',b'')) as call:
            self.assertEqual(b'{"x":1}',w.github('actions/runs/1/attempts/2/jobs?per_page=100&page=3'))
            args=call.call_args.args[0];self.assertIn('GET',args);self.assertIn('github.com',args);self.assertNotIn('POST',args)
            for bad in ('../tokens','actions/runs/1/rerun','actions/runs/1/cancel','https://elsewhere/actions/runs/1','actions/runs/1?x=2'):
                with self.assertRaisesRegex(ValueError,'read-only API path'):w.github(bad)
            self.assertEqual(1,call.call_count)
        with self.assertRaisesRegex(ValueError,'duplicate key'):self.run_gate(lambda _:b'{"id":1,"id":1}')
        retained=list((self.output/'api').glob('*/before.json'));self.assertEqual(1,len(retained))
        self.assertEqual(b'{"id":1,"id":1}',retained[0].read_bytes())

    def test_identity_and_selected_latest_attempt_are_required(self):
        for key,value in [('id',True),('run_attempt',1),('head_sha','b'*40),('head_branch','master'),('event','pull_request'),
                          ('path','.github/workflows/ci.yml'),('workflow_id',False)]:
            original=self.api['actions/runs/100'];bad=dict(original,**{key:value});self.api['actions/runs/100']=bad
            with self.subTest(key=key),self.assertRaises(ValueError):self.run_gate()
            self.api['actions/runs/100']=original
        value=self.api['actions/runs/100'];value['head_repository']['id']+=1
        with self.assertRaisesRegex(ValueError,'repository identity'):self.run_gate()

    def test_missing_duplicate_wrong_attempt_and_skipped_jobs_reject(self):
        expected=self.contracts['profiles']['jobs'];ctx=self.index['cohorts']['profiles'];original=self.jobs()
        changes=[lambda j:j.pop(),lambda j:j.append(copy.deepcopy(j[0])),lambda j:j[1].update(id=j[0]['id']),
                 lambda j:j[0].update(run_attempt=1),lambda j:j[0].update(head_sha='b'*40),
                 lambda j:j[0].update(conclusion='skipped'),lambda j:j[0].update(status='queued'),
                 lambda j:j[0].update(name='unexpected'),lambda j:j[0].update(head_branch='master')]
        for change in changes:
            jobs=copy.deepcopy(original);change(jobs)
            with self.assertRaises(ValueError):w.check_jobs(jobs,ctx,expected,2000000000)

    def test_missing_skipped_duplicate_or_wrong_time_critical_steps_reject(self):
        expected=self.contracts['profiles']['jobs'];ctx=self.index['cohorts']['profiles'];original=self.jobs()
        for change in [lambda j:j[0]['steps'].pop(),lambda j:j[0]['steps'][0].update(conclusion='skipped'),
                       lambda j:j[0]['steps'].append(copy.deepcopy(j[0]['steps'][0])),
                       lambda j:j[0]['steps'][0].update(started_at='2026-01-02T00:00:00Z'),
                       lambda j:j[0]['steps'][0].update(number=True),lambda j:j[0].update(completed_at='2020-01-01T00:00:00Z')]:
            jobs=copy.deepcopy(original);change(jobs)
            with self.assertRaises(ValueError):w.check_jobs(jobs,ctx,expected,2000000000)
        jobs=copy.deepcopy(original);jobs[-1]['started_at']='2026-01-01T00:00:00Z'
        # Dependency authority comes from needs, not clocks on different runners.
        self.assertEqual(len(jobs),w.check_jobs(jobs,ctx,expected,2000000000))
        jobs=copy.deepcopy(original);s=jobs[0]['steps'];s[0]['name'],s[1]['name']=s[1]['name'],s[0]['name']
        with self.assertRaisesRegex(ValueError,'critical step order'):w.check_jobs(jobs,ctx,expected,2000000000)

    def test_truncated_changed_total_and_duplicate_cross_page_never_accept(self):
        path='actions/runs/104/attempts/2/jobs?per_page=100&page=2';original=copy.deepcopy(self.api[path])
        for mode in ('truncated','changed-total','duplicate'):
            self.api[path]=copy.deepcopy(original)
            if mode=='truncated':self.api[path]['jobs'].pop()
            elif mode=='changed-total':self.api[path]['total_count']+=1
            else:self.api[path]['jobs'][0]=copy.deepcopy(self.api[path.replace('page=2','page=1')]['jobs'][0])
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'truncated|page total|duplicate/mixed'):self.run_gate()
            self.assertTrue((self.output/'api/joining-process/attempt-2/jobs-2.json').is_file())
        self.api[path]=original

    def test_failed_selected_attempt_and_prior_network_failure_are_retained(self):
        for path in ('actions/runs/100','actions/runs/100/attempts/2'):self.api[path]['conclusion']='cancelled'
        with self.assertRaisesRegex(ValueError,'not successful'):self.run_gate()
        receipt=w.seeds.read(self.output/'receipt.json');self.assertEqual('FAIL',receipt['status']);self.assertFalse(receipt['workflowExecutionAttested'])
        self.assertEqual(['failure','cancelled'],[a['conclusion'] for a in receipt['cohorts']['profiles']['attempts']])
        def unavailable(path):
            if path=='actions/runs/100/attempts/1':raise RuntimeError('synthetic unavailable')
            return self.get(path)
        with self.assertRaisesRegex(RuntimeError,'synthetic unavailable'):self.run_gate(unavailable)
        self.assertTrue((self.output/'api/profiles/before.json').is_file())

    def test_rerun_during_collection_and_missing_prior_attempt_cannot_be_hidden(self):
        count=0
        def moving(path):
            nonlocal count
            if path=='actions/runs/100':
                count+=1
                if count==3:return json.dumps(dict(self.api[path],run_attempt=3,status='queued',conclusion=None)).encode()
            return self.get(path)
        with self.assertRaisesRegex(ValueError,'exact context'):self.run_gate(moving)
        path='actions/runs/100/attempts/1/jobs?per_page=100&page=1';self.api[path]['jobs'][0]['run_attempt']=2
        with self.assertRaisesRegex(ValueError,'duplicate/mixed'):self.run_gate()

    def test_workflow_graph_planner_and_matrix_drift_are_rejected(self):
        name='profiles';a=self.modules[name];text=(w.plan.ROOT/a.WORKFLOW).read_text()
        for old,new in [('needs: [prepare, execute]','needs: prepare'),('fromJSON(needs.prepare.outputs.matrix)','fromJSON(inputs.matrix)'),
                        ('scripts.v53.profile_hosted plan','scripts.v53.other plan'),('fail-fast: false','fail-fast: true'),
                        ('Membership original (${{ matrix.id }})','Membership original (${{ matrix.unknown }})')]:
            self.assertIn(old,text)
            with self.assertRaises(ValueError):w.contract(name,a,self.catalogs[name],text.replace(old,new))

    def test_existing_output_is_never_overwritten(self):
        self.run_gate();before=(self.output/'receipt.json').read_bytes()
        with self.assertRaises(FileExistsError):w.collect(self.index_path,self.output,self.get)
        self.assertEqual(before,(self.output/'receipt.json').read_bytes())

    def attested(self,output,get=None):
        common=dict(sourceSha256='a'*64,buildSha256='b'*64,toolchainSha256='c'*64,repositorySha256='d'*64)
        def resources(index,inputs,work,*,expected_common):
            self.assertEqual(common,expected_common);work.mkdir()
            result=dict(status='PARTIAL',source=self.sha,indexSha256='f'*64,allSupplementalOriginalsReplayed=True,
                phase3Complete=False,combinedPeakResourcesQualified=False,resourceWorkflowExecutionAttested=False,
                historicalCapacityPrefixQualified=False)
            w.h.save(work/'receipt.json',result);return result
        # Owning physical replay is covered by its separate suite. This test
        # exercises actual paginated workflow observations around both replays.
        with patch.object(admitted.resources,'inspect',return_value=dict(source=self.sha,commonPins={k:v for k,v in common.items() if k!='repositorySha256'})), \
                patch.object(admitted.resources,'run',side_effect=resources),patch.object(admitted.resources,'unchanged'):
            return admitted.run(self.index_path,self.root/'seeds',self.root/'raw',self.root/output,get or self.get,
                resource_index=self.root/'resource-index.json',resource_inputs=self.root/'resources')

    def history_seed(self,output):
        (output/'seeds').mkdir()
        w.h.save(output/'seeds/receipt.json',dict(commonPins=dict(sourceSha256='a'*64,buildSha256='b'*64,
                   toolchainSha256='c'*64,repositorySha256='d'*64)))

    def test_attested_entry_queries_real_collector_around_original_first_replay(self):
        seen=[]
        def replay(index,seeds,inputs,output,*,expected_common):
            seen.append(len(self.calls));output.mkdir();self.history_seed(output)
            result=dict(status='PARTIAL',allDeclaredHistoriesReplayed=True,workflowExecutionAttested=False,
                source=self.sha,indexSha256=w.h.digest(self.index_path.read_bytes()),historiesReplayed=566,groupsReplayed=260,rawArchives=500,
                candidateWitnesses=dict(rejected=16,notApplicable=4,phase3Complete=False),phase3Complete=False,runtimeQualified=False,
                combinedPeakResourcesQualified=False,frozenScenarioCoverageQualified=False)
            w.h.save(output/'receipt.json',result);return result
        # Same parsed API values with a different wire representation still
        # attest the same execution; original responses are both retained.
        def formatted(path):
            raw=self.get(path);return json.dumps(json.loads(raw),indent=2).encode() if seen else raw
        with patch.object(admitted.histories,'run',side_effect=replay) as call, \
                patch.object(admitted,'unchanged_originals') as unchanged,redirect_stdout(io.StringIO()):
            result=self.attested('complete',formatted)
        unchanged.assert_called_once()
        self.assertEqual(1,call.call_count);self.assertLess(seen[0],len(self.calls));self.assertTrue(result['workflowExecutionAttested'])
        self.assertTrue(result['allDeclaredHistoriesReplayed']);self.assertTrue(result['priorAttemptsRequireReview'])
        self.assertTrue(result['allSupplementalOriginalsReplayed']);self.assertFalse(result['resourceWorkflowExecutionAttested'])
        self.assertIn('resources',result['receipts'])
        self.assertFalse(result['phase3Complete']);self.assertFalse(result['runtimeQualified']);self.assertFalse(result['failedOriginalsReplayed'])

    def test_attested_entry_stops_before_replay_on_failed_workflow(self):
        for path in ('actions/runs/100','actions/runs/100/attempts/2'):self.api[path]['conclusion']='failure'
        with patch.object(admitted.histories,'run') as call,redirect_stdout(io.StringIO()),self.assertRaises(ValueError):
            self.attested('failed')
        call.assert_not_called();self.assertFalse(w.seeds.read(self.root/'failed/receipt.json')['workflowExecutionAttested'])

    def test_attested_entry_requires_resource_inputs_and_rejects_wrong_source_before_histories(self):
        with self.assertRaises(TypeError):
            admitted.run(self.index_path,self.root/'seeds',self.root/'raw',self.root/'missing',self.get)
        with patch.object(admitted.resources,'inspect',return_value=dict(source='0'*40)), \
                patch.object(admitted.histories,'run') as replay,redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(ValueError,'resource source'):
            admitted.run(self.index_path,self.root/'seeds',self.root/'raw',self.root/'wrong-resource-source',self.get,
                resource_index=self.root/'resource-index.json',resource_inputs=self.root/'resources')
        replay.assert_not_called()

    def test_resource_rejection_stops_admission_even_after_histories_pass(self):
        def replay(index,seeds,inputs,output,*,expected_common):
            output.mkdir();self.history_seed(output)
            result=dict(status='PARTIAL',source=self.sha,indexSha256=w.h.digest(self.index_path.read_bytes()),
                allDeclaredHistoriesReplayed=True,workflowExecutionAttested=False,phase3Complete=False,runtimeQualified=False,
                combinedPeakResourcesQualified=False,frozenScenarioCoverageQualified=False)
            w.h.save(output/'receipt.json',result);return result
        with patch.object(admitted.resources,'inspect',return_value=dict(source=self.sha,commonPins={})), \
                patch.object(admitted.histories,'run',side_effect=replay), \
                patch.object(admitted.resources,'run',side_effect=ValueError('actual resource original rejected')), \
                redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'actual resource original rejected'):
            admitted.run(self.index_path,self.root/'seeds',self.root/'raw',self.root/'resource-rejected',self.get,
                resource_index=self.root/'resource-index.json',resource_inputs=self.root/'resources')
        result=w.seeds.read(self.root/'resource-rejected/receipt.json')
        self.assertFalse(result['allSupplementalOriginalsReplayed']);self.assertEqual('FAIL',result['status'])
        self.assertFalse((self.root/'resource-rejected/workflow-after').exists())

    def test_attested_entry_refuses_original_failure_or_changed_later_execution(self):
        def replay(index,seeds,inputs,output,*,expected_common):
            output.mkdir();self.history_seed(output);result=dict(status='PARTIAL',source=self.sha,indexSha256=w.h.digest(self.index_path.read_bytes()),
                allDeclaredHistoriesReplayed=True,workflowExecutionAttested=False,phase3Complete=False,runtimeQualified=False,
                combinedPeakResourcesQualified=False,frozenScenarioCoverageQualified=False)
            w.h.save(output/'receipt.json',result);self.jobs()[0]['id']+=5000;return result
        with patch.object(admitted.histories,'run',side_effect=replay),redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(ValueError,'observations changed'):
            self.attested('changed')
        self.assertTrue((self.root/'changed/histories/receipt.json').is_file())
        self.assertFalse(w.seeds.read(self.root/'changed/receipt.json')['allDeclaredHistoriesReplayed'])
        with patch.object(admitted.histories,'run',side_effect=ValueError('bad original')),redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(ValueError,'bad original'):
            self.attested('original-failed')
        self.assertFalse((self.root/'original-failed/workflow-after').exists())

    def test_post_observation_rechecks_original_archive_and_seed_bytes(self):
        output=self.root/'histories';output.mkdir();(output/'seeds').mkdir();seed_inputs=self.root/'seeds';seed_inputs.mkdir()
        bundle=dict(manifestSha256='a'*64,archiveSha256='b'*64)
        for name in self.modules:(seed_inputs/name).mkdir()
        w.h.save(output/'seeds/receipt.json',dict(seeds={n:bundle for n in self.modules}))
        inventory={'original':dict(archiveSha256='c'*64)}
        result=dict(rawInventorySha256=w.h.digest(w.plan.encoded(inventory)),seedReceiptSha256=w.seeds.shared.tc.file_hash(output/'seeds/receipt.json'))
        w.h.save(output/'receipt.json',result)
        with patch.object(w.histories,'raw_inventory',return_value=inventory) as raw, \
                patch.object(w.seeds,'bundle_identity',return_value=bundle) as identity:
            admitted.unchanged_originals(self.index_path,seed_inputs,self.root/'raw',output,result)
            raw.return_value={}
            with self.assertRaisesRegex(ValueError,'originals changed'):admitted.unchanged_originals(self.index_path,seed_inputs,self.root/'raw',output,result)
            raw.return_value=inventory;identity.return_value=dict(bundle,archiveSha256='d'*64)
            with self.assertRaisesRegex(ValueError,'seed changed'):admitted.unchanged_originals(self.index_path,seed_inputs,self.root/'raw',output,result)


if __name__=='__main__':unittest.main()

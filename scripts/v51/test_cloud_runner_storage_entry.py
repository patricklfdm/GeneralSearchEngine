from copy import deepcopy
from pathlib import Path
import tempfile
import time
import subprocess
import sys
import os
import textwrap
import unittest
from unittest.mock import Mock, patch
from . import cloud_runner_storage_entry as e, cloud_runner_storage_plan as p, cloud_runner_storage as s
from . import cloud_runner_storage_entry_qualification as q, cloud_native_authority as n
from . import cloud_cleanup_qualification as cleanup, cloud_http as h, cloud_http_fake as f, performance_model as m
from . import test_cloud_runner_precheck as pre, cloud_runner_precheck as r
from .remote_command import read, write_once


class StoragePreparationTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.cfg,self.clock,self.http,self.value,self.api=q.fixture()
    def prepare(self):return p.prepare(self.api,self.root/'prepare',wall=self.clock.wall)

    def test_two_distinct_reservations_and_independent_readback(self):
        prepared=self.prepare();self.assertEqual('PREPARED',prepared['status'],prepared)
        self.assertNotIn(n.LEASE,self.http.objects)
        api,backend=q.runner(prepared['manifest'],self.http,self.clock);s.run(api)
        after=e.capture(self.cfg,prepared['manifest'],api=q.independent(backend,self.clock),wall=self.clock.wall)
        result=e.check_state(self.cfg,prepared['manifest'],after,native=False)
        self.assertEqual(14_000_000,result['retainedCostMicrousd'])
        for flag in p.FLAGS:self.assertIs(result[flag],False)
        self.assertFalse(any('/compute/' in row['path'] for row in self.http.requests+backend.requests))

    def test_plan_roundtrips_without_tuple_list_readback_drift(self):
        self.assertEqual(self.value,m.strict_json(m.canonical(self.value)))
        self.assertEqual(p.validate(self.value,now=self.clock.wall()),p.validate(m.strict_json(m.canonical(self.value)),now=self.clock.wall()))

    def test_prices_scope_cost_and_expiry_are_bound(self):
        changes=[lambda v:v.update(maximumCombinedCostMicrousd=1),lambda v:v['prices']['stages'].pop('run'),
            lambda v:v['prices']['stages']['prepare'].update(actions=p.COST),
            lambda v:v['prices'].update(retentionDays=1),lambda v:v['prices'].update(pricedThroughSeconds=100),
            lambda v:v['prices'].update(sources=['https://example.org/price']),
            lambda v:v['configuration']['provider'].update(bucket='foreign'),
            lambda v:v['requests']['run'].update(source='f'*40),lambda v:v.update(paidAdmission=True),
            lambda v:v['identities'].update(runAttempt=v['identities']['prepareAttempt'])]
        for change in changes:
            value=deepcopy(self.value);change(value)
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):
                p.validate(value,now=self.clock.wall())
        with self.assertRaises(ValueError):p.validate(self.value,now=self.value['expiresAt'])

    def test_network_preparation_rejects_offline_and_wrong_confirmation_before_credentials(self):
        with patch.object(p,'protected') as protected,patch.object(h,'Network') as wire:
            with self.assertRaises(ValueError):p.NetworkPreparation(self.value,m.sha(m.canonical(self.value)))
            value=deepcopy(self.value);value['execution']='operator-runner-storage-plan'
            with self.assertRaises(ValueError):p.NetworkPreparation(value,'0'*64)
            protected.assert_not_called();wire.assert_not_called()

    def test_native_preparation_wiring_uses_review_and_exact_operator_credential(self):
        before=deepcopy(self.value['before']);before['execution']='read-only-native-cleanup-observation'
        value=p.make(self.cfg,self.value['requests']['prepare']['source'],self.value['operator'],self.value['prices'],
                     before,now=self.clock.wall(),identities=self.value['identities'])
        http=self.http
        class Wire:
            offline=False
            def send(self,*args):return http.send(*args)
        with patch.object(p,'protected',return_value={'offlineUnitFixture':True}) as protected,\
             patch.object(p.driver,'operator_account') as account,patch.object(h,'Network',Wire),\
             patch.object(p.time,'time',return_value=self.clock.wall()),\
             patch.object(p.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'synthetic-unit-token',b'')) as command:
            api=p.NetworkPreparation(value,p.validate(value,now=self.clock.wall()))
            result=p.prepare(api,self.root/'native-prepare',wall=self.clock.wall)
        self.assertEqual('PREPARED',result['status'],result.get('failure'));protected.assert_called_once_with(value)
        account.assert_called_once_with(value['operator'])
        self.assertEqual(['gcloud','auth','print-access-token','--account='+value['operator']],command.call_args.args[0])
        self.assertEqual(13_000_000,n.inspect_ledger(result['manifest']['baseline'][n.LEDGER][1])[0])
        self.assertNotIn(n.LEASE,self.http.objects)

    def test_observe_cli_retains_the_documented_observation_file(self):
        prepared=self.prepare();path=self.root/'manifest.json';write_once(path,prepared['manifest'])
        observed=e.capture(self.cfg,prepared['manifest'],api=q.independent(self.http,self.clock),wall=self.clock.wall)
        output=self.root/'observed'
        with patch.object(sys,'argv',['storage','observe','--manifest',str(path),'--output',str(output)]),\
             patch.object(e.plan.driver,'operator_account') as account,patch.object(e,'capture',return_value=observed):
            e.main()
        account.assert_called_once_with(self.value['operator'])
        self.assertEqual(m.strict_json(m.canonical(observed)),read(output/'observation.json'))
        self.assertFalse((output/'receipt.json').exists())

    def test_all_preparation_writes_are_guarded_even_through_base_api(self):
        before=deepcopy(self.http.objects)
        for method,url,body in [('POST',self.api.upload,{}),('DELETE',self.api.store.url(n.LEDGER),None),
            ('GET','https://compute.googleapis.com/compute/v1/projects/x',None),
            ('GET',self.api.store.url(n.LEDGER)+'?alt=media',None)]:
            for call in (self.api.call,lambda *args,**kw:h.Api.call(self.api,*args,**kw)):
                with self.assertRaises(ValueError):call(method,url,body,deadline=self.clock.seconds()+30)
        self.assertEqual(before,self.http.objects)

    def test_stale_or_used_preparation_cannot_reacquire_or_reset_ledger(self):
        result=self.prepare();self.assertEqual('PREPARED',result['status'])
        before=deepcopy(self.http.objects)
        api=p.OfflinePreparation(self.value,transport=self.http,clock=self.clock.seconds,now=self.clock.wall())
        result=p.prepare(api,self.root/'again',wall=self.clock.wall)
        self.assertEqual('FAIL',result['status']);self.assertEqual(before,self.http.objects)

    def test_terminal_cas_requires_original_reserved_generation_and_bytes(self):
        for _ in range(5):self.api.step(now=self.clock.wall())
        generation,raw,content=self.http.objects[n.LEDGER]
        self.http.objects[n.LEDGER]=generation+1,raw,content
        before=deepcopy(self.http.objects)
        with self.assertRaisesRegex(ValueError,'reservation changed'):self.api.step(now=self.clock.wall())
        self.assertEqual(before,self.http.objects)

    def test_immutable_manifest_is_outside_runner_write_prefix(self):
        result=self.prepare();key=p.manifest_key(result['planSha256'])
        self.assertTrue(key.startswith(n.PREFIX));self.assertFalse(key.startswith(n.PREFIX+'attempts/'))
        api,_=q.runner(result['manifest'],self.http,self.clock)
        with self.assertRaises(ValueError):api.call('POST',api.put_url(key,0),{},deadline=self.clock.seconds()+30)

    def test_manifest_tampering_and_cross_domain_relabel_are_rejected(self):
        result=self.prepare();manifest=result['manifest']
        for change in [lambda v:v.update(planSha256='0'*64),lambda v:v['baseline'].pop(n.LEDGER),
                       lambda v:v['baseline'][n.LEDGER][1]['entries'].pop(),lambda v:v.update(preparedAt=self.value['expiresAt']),
                       lambda v:v['plan'].update(execution='operator-runner-storage-plan')]:
            value=deepcopy(manifest);change(value)
            with self.assertRaises((ValueError,KeyError)):
                p.validate_manifest(value,self.cfg,manifest['planSha256'],now=self.clock.wall(),offline=True)
        with self.assertRaises(ValueError):p.validate_manifest(manifest,self.cfg,manifest['planSha256'],now=self.clock.wall())

    def test_independent_review_rejects_changed_canaries_missing_evidence_and_lost_charges(self):
        prepared=self.prepare();api,backend=q.runner(prepared['manifest'],self.http,self.clock);s.run(api)
        after=e.capture(self.cfg,prepared['manifest'],api=q.independent(backend,self.clock),wall=self.clock.wall)
        for change in [lambda v:v['objects'].pop(api.keys['outside']),
                       lambda v:v['objects'][api.keys['existing']][1].update(kind='changed'),
                       lambda v:v['objects'].__setitem__(api.keys['outside'],[999,v['objects'][api.keys['outside']][1]]),
                       lambda v:v['objects'][n.LEDGER][1]['entries'].pop(),
                       lambda v:v['objects'].__setitem__(api.keys['report'],None),
                       lambda v:v['objects'].__setitem__(n.LEASE,[999,api.lease])]:
            value=deepcopy(after);change(value)
            with self.assertRaises((ValueError,KeyError,TypeError)):e.check_state(self.cfg,prepared['manifest'],value,native=False)


class StorageEntryTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.cfg,self.env,self.preflight,self.github=pre.fixture(self.root)
        self.env.update(RUNNER_STORAGE_REQUEST='1'*64,RUNNER_STORAGE_CONFIRMATION='2'*64)
        self.now=pre.q.NOW+2
        r.bind(self.cfg,self.env,pre.q.SOURCE,pre.q.SOURCE,self.preflight,self.root/'identity',get=self.get,wall=lambda:self.now)
        pre.permission_files(self.cfg,self.env,self.root/'permissions','runner',self.now)
        r.finish(self.cfg,self.env,pre.q.SOURCE,pre.q.SOURCE,self.preflight,self.root,get=self.get,wall=lambda:self.now)
    def get(self,path):return deepcopy(self.github[path])
    def admit(self):return e.admission(self.cfg,self.env,pre.q.SOURCE,pre.q.SOURCE,self.preflight,self.root,get=self.get,wall=lambda:self.now)

    def test_selection_is_empty_by_default_and_requires_two_exact_digests(self):
        self.assertIsNone(e.selection({}))
        for env in [dict(RUNNER_STORAGE_REQUEST='a'*64),dict(RUNNER_STORAGE_CONFIRMATION='b'*64),
                    dict(self.env,RUNNER_PERMISSION_PRECHECK='false'),dict(self.env,RUNNER_STORAGE_REQUEST='../foreign'),
                    dict(self.env,RUNNER_STORAGE_CONFIRMATION='')]:
            with self.assertRaises(ValueError):e.selection(env)
        self.assertEqual(('1'*64,'2'*64),e.selection(self.env))

    def test_admission_replays_raw_observer_and_permission_evidence(self):
        binding,before=self.admit();self.assertEqual('runner',binding['role'])
        self.assertEqual(222,before['runId']);self.assertFalse(before['cleanup']['scheduleRequired'])
        (self.preflight/'provider.json').unlink()
        with self.assertRaises(ValueError):self.admit()

    def test_missing_or_forged_same_run_permission_receipt_is_rejected(self):
        for filename in ('receipt.json','permissions/receipt.json','identity/binding.json'):
            path=self.root/filename;original=path.read_bytes();value=read(path);value['status']='FORGED'
            path.write_bytes(m.canonical(value))
            with self.assertRaises(ValueError):self.admit()
            path.write_bytes(original)

    def test_wrong_role_attempt_and_expiry_block_before_cloud_constructor(self):
        admission=e.admission
        def local_admission(*args):return admission(*args,get=self.get,wall=lambda:self.now)
        self.github['actions/runs/222/attempts/1']=dict(self.github['actions/runs/222'],run_attempt=1)
        for field,val in [('GITHUB_JOB','observations'),('GITHUB_RUN_ATTEMPT','1'),('GITHUB_SHA','b'*40)]:
            old=self.env[field];self.env[field]=val
            with patch.object(e,'admission',side_effect=local_admission),patch.object(e.credentials,'NetworkCredentials') as tokens,self.assertRaises(ValueError):
                e.NetworkApi(self.cfg,self.env,pre.q.SOURCE,pre.q.SOURCE,self.preflight,self.root)
            tokens.assert_not_called();self.env[field]=old
        self.now=pre.q.NOW+900
        with self.assertRaises(ValueError):self.admit()

    def test_generic_storage_policy_cannot_be_constructed_as_an_admitted_live_runner(self):
        cfg,clock,http,value,prepare=q.fixture()
        manifest=p.prepare(prepare,self.root/'other-preparation',wall=clock.wall)['manifest']
        api=s._Policy(transport=h.Network(),tokens=lambda _: 'never-send')
        api.initialize(cfg['provider'],value['requests']['run'],manifest['baseline'],maximum_cost=p.COST,native=True)
        with self.assertRaises(ValueError):api.call('GET',api.url(n.LEDGER),deadline=api.clock()+30)

    def test_failed_entry_retains_sanitized_receipt_and_summary(self):
        with patch.object(e,'NetworkApi',side_effect=ConnectionError('secret-credential')):
            result=e.execute_network(self.cfg,self.env,pre.q.SOURCE,pre.q.SOURCE,self.preflight,self.root,self.root/'output')
        self.assertEqual('FAIL',result['status']);self.assertFalse(result['paidCloud'])
        self.assertNotIn('secret-credential',(self.root/'output/receipt.json').read_text())
        self.assertTrue((self.root/'output/summary.md').is_file())

    def native_fixture(self):
        # Native bytes remain synthetic temporary unit-test inputs.
        cfg,clock,http,value,api=q.fixture(source=pre.q.SOURCE,now=pre.q.NOW-1,cfg=self.cfg)
        manifest=p.prepare(api,self.root/'canaries',wall=clock.wall)['manifest']
        native_before=deepcopy(value['before']);native_before['execution']='read-only-native-cleanup-observation'
        native=p.make(cfg,pre.q.SOURCE,value['operator'],value['prices'],native_before,now=clock.wall(),identities=value['identities'])
        native_sha=p.validate(native,now=clock.wall())
        # Native bytes are synthetic test inputs, never retained as cloud qualification.
        native_manifest=dict(manifest,plan=native,planSha256=native_sha)
        oldkey=p.manifest_key(manifest['planSha256']);gen,_,content=http.objects.pop(oldkey)
        http.objects[p.manifest_key(native_sha)]=(gen,m.canonical(native_manifest),content)
        _,backend=q.runner(native_manifest,http,clock)
        provider=read(self.preflight/'provider.json');provider['observations']['ledger']=native_manifest['baseline'][n.LEDGER]
        (self.preflight/'provider.json').write_bytes(m.canonical(provider))
        new_preflight=r.p.report(cfg,pre.q.SOURCE,self.preflight,dict(self.env,GITHUB_JOB='observations'),now=pre.q.NOW)
        (self.preflight/'preflight.json').write_bytes(m.canonical(new_preflight))
        # Bind a new set of local receipts to the changed raw observer sample.
        bound=read(self.root/'identity/receipt.json')
        binding=r.identity(cfg,self.env,pre.q.SOURCE,pre.q.SOURCE)
        bound['prerequisites']=r.prerequisites(cfg,self.env,binding,self.preflight,
            self.github['actions/runs/222/attempts/2/jobs?per_page=100'],now=self.now)
        (self.root/'identity/receipt.json').write_bytes(m.canonical(bound))
        prior=read(self.root/'receipt.json');prior['prerequisites']=bound['prerequisites']
        (self.root/'receipt.json').write_bytes(m.canonical(prior))
        self.env.update(RUNNER_STORAGE_REQUEST=native_sha,RUNNER_STORAGE_CONFIRMATION=m.sha(m.canonical(native_manifest)))
        return cfg,clock,backend,native_manifest

    def test_network_entry_and_completed_review_with_synthetic_credentials_and_http(self):
        cfg,clock,backend,native_manifest=self.native_fixture()
        class Wire:
            offline=False
            def send(self,*args):return backend.send(*args)
        class Tokens:
            exchanges=1
            def __call__(self,timeout):return h.AccessToken('synthetic-unit-token',time.monotonic()+3600)
        admission=e.admission;collect=e.entry.collect_run
        def local_admission(*args):return admission(*args,get=self.get,wall=lambda:self.now)
        with patch.object(e,'admission',side_effect=local_admission),patch.object(e.entry,'collect_run',side_effect=lambda b,*_:collect(b,self.get)),\
             patch.object(e.entry,'credential_file',return_value={}),patch.object(e.credentials,'NetworkCredentials',return_value=Tokens()),\
             patch.object(h,'Network',Wire),patch.object(e.time,'time',return_value=self.now):
            before=deepcopy(backend.objects)
            failed=e.execute_network(cfg,dict(self.env,RUNNER_STORAGE_CONFIRMATION='f'*64),pre.q.SOURCE,pre.q.SOURCE,
                                     self.preflight,self.root,self.root/'wrong-confirmation')
            self.assertEqual('FAIL',failed['status']);self.assertFalse(failed['paidCloud']);self.assertEqual(before,backend.objects)
            result=e.execute_network(cfg,self.env,pre.q.SOURCE,pre.q.SOURCE,self.preflight,self.root,self.root/'native-entry')
        self.assertEqual('PROBES_RECORDED',result['status'],result.get('failure'))
        self.assertTrue(result['credentialExchangeCompleted']);self.assertTrue(result['paidCloud'])
        # Independently sample final bytes using the unrestricted operator double.
        native_reader=q.independent(backend,clock)
        native_reader.transport.offline=False
        after=e.capture(cfg,native_manifest,api=native_reader,wall=lambda:self.now+5)
        run=deepcopy(self.github['actions/runs/222']);run.update(status='completed',conclusion='success')
        jobs=deepcopy(self.github['actions/runs/222/attempts/2/jobs?per_page=100']);jobs['total_count']=2
        jobs['jobs'].append(dict(name=e.workflow.RUNNER_JOB_NAME,run_id=222,run_attempt=2,head_sha=pre.q.SOURCE,
            status='completed',conclusion='success',started_at=pre.at(self.now),completed_at=pre.at(self.now+3),
            steps=[dict(name=name,status='completed',conclusion='success') for name in
                   (e.STEP,'Report runner permission diagnostics','Retain runner precheck evidence including failures')]))
        runs=dict(before=run,attempt=deepcopy(run),after=deepcopy(run),jobs=jobs)
        reviewed=e.review(cfg,result,after,runs,self.root)
        self.assertEqual('OBJECT_SCOPE_MATCH',reviewed['status']);self.assertFalse(reviewed['artifactProvenanceVerified'])
        for change in [lambda v:v.update(credentialExchangeCompleted=False),lambda v:v['binding'].update(role='manual'),
                       lambda v:v['result']['cases'].pop(),lambda v:v.update(confirmation='f'*64),
                       lambda v:v.update(manifestGeneration=v['manifestGeneration']+1)]:
            mutated=deepcopy(result);change(mutated)
            with self.assertRaises((ValueError,KeyError)):e.review(cfg,mutated,after,runs,self.root)
        jobs['jobs'][1]['steps'][0]['conclusion']='skipped'
        with self.assertRaises(ValueError):e.review(cfg,result,after,runs,self.root)

    def test_python_module_cli_runs_the_bound_storage_transaction(self):
        cfg,clock,backend,manifest=self.native_fixture()
        write_once(self.root/'cli-fixture.json',dict(configuration=cfg,manifest=manifest,
            state=cleanup.snapshot(backend),github=self.github,now=self.now,source=pre.q.SOURCE))
        write_once(self.root/'configuration.json',cfg)
        hooks=self.root/'hooks';hooks.mkdir()
        # Python's real -m path runs in a fresh interpreter. Only external I/O
        # boundaries are replaced; do not replace NetworkApi/run/type guards.
        (hooks/'sitecustomize.py').write_text(textwrap.dedent('''
            import atexit, json, os, socket, subprocess, time
            from pathlib import Path
            root=Path(os.environ['V51_CLI_TEST_ROOT'])
            value=json.loads((root/'cli-fixture.json').read_text())
            time.time=lambda:value['now']
            from scripts.v51 import cloud_runner_storage_entry as e
            from scripts.v51 import cloud_runner_storage_entry_qualification as q
            from scripts.v51 import cloud_cleanup_qualification as cleanup
            _,http,_,_=cleanup.restore(value['state'])
            clock=q.cloud_fake.Clock()
            _,backend=q.runner(value['manifest'],http,clock)
            e.p.CONFIG=root/'configuration.json'
            def blocked(*args,**kwargs):
                raise AssertionError('CLI regression must not contact external services')
            socket.socket.connect=blocked
            socket.create_connection=blocked
            subprocess.run=blocked
            def checkout(args,**kwargs):
                if args!=['git','rev-parse','HEAD']:return blocked()
                return value['source']
            subprocess.check_output=checkout
            def get(path):return value['github'][path]
            jobs=e.precheck.collect_jobs;run=e.entry.collect_run
            e.precheck.collect_jobs=lambda binding,*args:jobs(binding,get)
            e.entry.collect_run=lambda binding,*args:run(binding,get)
            e.entry.credential_file=lambda env:{}
            class Tokens:
                exchanges=1
                def __call__(self,timeout):
                    return e.h.AccessToken('synthetic-cli-token',time.monotonic()+3600)
            e.credentials.NetworkCredentials=lambda *args:Tokens()
            class Wire:
                offline=False
                def send(self,*args):return backend.send(*args)
            e.h.Network=Wire
            atexit.register(lambda:(root/'cli-after.json').write_bytes(e.m.canonical(cleanup.snapshot(backend))))
        '''))
        env=dict(os.environ,**self.env,V51_CLI_TEST_ROOT=str(self.root),
                 PYTHONPATH=os.pathsep.join((str(hooks),str(e.ci.ROOT))))
        command=[sys.executable,'-m','scripts.v51.cloud_runner_storage_entry','run',
            '--source',pre.q.SOURCE,'--preflight',str(self.preflight),'--precheck',str(self.root)]
        result=subprocess.run([*command,'--output',str(self.root/'cli-output')],env=env,cwd=e.ci.ROOT,
                              capture_output=True,text=True,timeout=60)
        receipt=read(self.root/'cli-output/receipt.json')
        self.assertEqual(0,result.returncode,(receipt.get('status'),receipt.get('failure'),result.stderr))
        self.assertEqual('PROBES_RECORDED',receipt['status'])
        self.assertEqual(list(s.CASES),[v['case'] for v in receipt['result']['cases']])
        _,after,_,_=cleanup.restore(read(self.root/'cli-after.json'))
        reader=q.independent(after,clock);reader.transport.offline=False
        captured=e.capture(cfg,manifest,api=reader,wall=lambda:self.now+5)
        self.assertEqual(14_000_000,e.check_state(cfg,manifest,captured,native=True)['retainedCostMicrousd'])
        # A fresh process with a changed confirmation must still stop before writes.
        env['RUNNER_STORAGE_CONFIRMATION']='f'*64
        failed=subprocess.run([*command,'--output',str(self.root/'cli-rejected')],env=env,cwd=e.ci.ROOT,
                              capture_output=True,text=True,timeout=60)
        self.assertEqual(2,failed.returncode,failed.stderr)
        self.assertEqual(read(self.root/'cli-fixture.json')['state'],read(self.root/'cli-after.json'))
        self.assertFalse(read(self.root/'cli-rejected/receipt.json')['paidCloud'])

    def test_workflow_selects_no_writes_by_default_and_guards_before_auth(self):
        raw=e.workflow.workflow().decode();job=e.workflow.JOB
        self.assertIn("runner_storage_request:",raw);self.assertIn("default: ''",raw)
        self.assertLess(job.index('cloud_runner_storage_entry guard'),job.index('google-github-actions/auth@'))
        self.assertLess(job.index('cloud_runner_precheck report'),job.index('cloud_runner_storage_entry run'))
        self.assertIn("success() && inputs.runner_storage_request != ''",job)
        self.assertIn('Retain runner precheck evidence including failures',job)
        for changed in [raw.replace("success() && inputs.runner_storage_request != ''",'always()'),
                        raw.replace('RUNNER_STORAGE_CONFIRMATION:','RUNNER_FORGED_CONFIRMATION:')]:
            with self.assertRaises(ValueError):e.workflow.workflow(changed)


if __name__=='__main__':unittest.main()

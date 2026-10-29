"""One failed retention can be waived; failed workloads and generic retries cannot."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_retention_recovery as r, cloud_acceptance as c
from . import cloud_member_evidence as member
from . import test_cloud_quota_continuation as batch_fixture
from .test_cloud_runner_provenance import RunnerFixture, WORKFLOW


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.b = batch_fixture.BatchTest(); self.addCleanup(self.b.doCleanups); self.b.setUp()
        f = self.b.fixtures['experiment']; self.req = f['request']; sha = r.a.validate_request(self.req, domain='native')
        f['completed'].update(status='FAIL', evidenceSha256=None)
        terminal = dict(kind='FINISHED', requestSha256=sha, status='FAIL', completionSha256=r.digest(r.encoded(f['completed'])))
        for value in self.b.fixtures.values():
            ledgers = [value['ledger']['value']]
            if value['plan']['baseline']: ledgers.append(value['plan']['baseline']['ledger'])
            for ledger in ledgers:
                for i,row in enumerate(ledger['entries']):
                    if row['kind']=='FINISHED' and row['requestSha256']==sha: ledger['entries'][i]=deepcopy(terminal)
        for name, value in self.b.fixtures.items():
            if name!='experiment': self.b.records[name]['seal']=c.seal.create(**value)
        self.client = RunnerFixture(self.b.records['experiment']['seal'])
        self.client.run.update(conclusion='failure', head_sha=f['source']['source'])
        self.client.jobs[0].update(conclusion='failure', head_sha=f['source']['source'])
        self.client.jobs[0]['steps'][-2]['conclusion']='failure'; self.client.jobs[0]['steps'][-1]['conclusion']='skipped'
        diagnostic=dict(status='FAIL',causeCode='V52_ORIGINAL_MEMBER_RETENTION_REJECTED',
            readRetry=dict(attempts=1,code='V52_READ_DEADLINE',reason='timeout',scope='provider-read',stop='deadline'),
            cleanup=dict(leaseReleased=True,resourceDeletesSubmitted=13,status='PASS'))
        self.client.record.update(name='v52-runner-diagnostics-123456-2')
        self.client.record['workflow_run']['head_sha']=f['source']['source']
        self.client.install();self.client.rezip([('failure.json',r.encoded(diagnostic))])
        self.client.data['branches/master']=dict(commit=dict(sha=self.b.bound['source']))
        self.client.data['contents/'+r.runners.PATH+'?ref='+f['source']['source']]=deepcopy(
            self.client.data['contents/'+r.runners.PATH+'?ref='+'a'*40])
        policy=dict(id='synthetic-retention-only',scope='synthetic only',configurationSha256=r.preflight.configuration(self.b.cfg),
            artifactPins=self.b.policy['artifactPins'],originals={},failure=dict(member='experiment',diagnostic=diagnostic,
            runKeySha256=r.digest(r.encoded(r.ci.run_key(self.client.run))),jobKeySha256=r.digest(r.encoded(r.ci.job_key(self.client.jobs[0]))),
            manifestGeneration=91,completionGeneration=92,cleanupGeneration=93,recoveredParts=[1]))
        for name, record in self.b.records.items():
            value=self.b.fixtures[name];pin=dict(self.b.chosen[name],source=value['source'],binding=value['request']['selection']['binding'],
                artifactId=record['artifactId'],artifactSha256=record['artifactSha256'],
                **{k:record['seal'][k] for k in ('manifestSha256','completionSha256','cleanupSha256')})
            if name=='experiment':
                pin.update(self.client.chosen,artifactId=901,artifactSha256=r.digest(self.client.raw),completionSha256=terminal['completionSha256'])
                self.b.chosen[name].update(self.client.chosen)
                self.b.replayed[name]['invocation']=dict(run='123456',attempt=2)
            policy['originals'][name]=pin
        self.policy=policy;self.enterContext(patch.object(r,'load',side_effect=lambda:deepcopy(self.policy)))
        self.scope=r.Scope(self.b.cfg,self.b.bound,self.b.chosen);self.b.scope=self.scope
        self.b.envelope=dict(recovery=self.policy['id'],selected=self.b.chosen)
        self.b.replayed['experiment']['retentionRecovery']=self.scope.report()

    def accounting(self, scope=True, **changes):
        f=deepcopy(self.b.fixtures['experiment']);f.update(changes)
        return member.completion(f['request'],f['manifest'],f['completed'],f['clean'],f['ledger']['value'],f['claim'],f['plan'],
                                 retention_scope=self.scope if scope else None)

    def test_exact_envelope_requires_all_original_selections(self):
        self.assertEqual(self.b.envelope,c.request(self.b.envelope))
        for field,value in (('runId',999),('runAttempt',3),('requestSha256','f'*64)):
            changed=deepcopy(self.b.envelope);changed['selected']['experiment'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):c.request(changed)
        for name in ('experiment','canonical-1-minimum'):
            changed=deepcopy(self.b.envelope);changed['selected'].pop(name)
            with self.assertRaises(ValueError):c.request(changed)
        for change in (dict(recovery='different'),dict(continuation='also')):
            with self.assertRaises(ValueError):c.request(dict(self.b.envelope,**change))

    def test_original_fail_accounting_is_preserved_and_default_rejects(self):
        before=deepcopy(self.b.fixtures['experiment']);self.accounting()
        self.assertEqual(before,self.b.fixtures['experiment'])
        with self.assertRaises(ValueError):self.accounting(False)
        self.assertEqual('FAIL',r.terminal_status(self.scope,self.req))
        self.assertEqual('PASS',r.terminal_status(None,self.req))
        self.assertEqual('PASS',r.terminal_status(self.scope,self.b.fixtures['canonical-1-legacy']['request']))

    def test_changed_manifest_failure_cleanup_or_terminal_rejects(self):
        f=self.b.fixtures['experiment']
        mutations=[dict(manifest={'altered':True}),dict(completed=dict(f['completed'],status='PASS',evidenceSha256='a'*64)),
                   dict(clean=dict(f['clean'],checks=[])),dict(claim=dict(f['claim'],source='f'*40))]
        for change in mutations:
            with self.subTest(change=change),self.assertRaises(ValueError):self.accounting(**change)
        ledger=deepcopy(f['ledger']);ledger['value']['entries'][-1]['completionSha256']='f'*64
        with self.assertRaises(ValueError):self.accounting(ledger=ledger)

    def test_generation_and_source_scope_reject_mutations(self):
        for name,gen in (('manifest',91),('completion',92),('cleanup',93)):
            self.scope.generation(name,dict(generation=gen))
            with self.assertRaises(ValueError):self.scope.generation(name,dict(generation=gen+1))
        self.scope.policy['failure']['member']='canonical-1-legacy'
        with self.assertRaises(ValueError):r.applies(self.scope,self.req)

    def test_failed_runner_requires_exact_step_outcomes_and_diagnostic_bytes(self):
        self.scope.failed_runner(self.client.run,self.client.jobs,self.client.record,self.client.raw)
        for field,value in (('conclusion','success'),('run_attempt',3),('head_sha','f'*40),('head_branch','topic')):
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.scope.failed_runner(dict(self.client.run,**{field:value}),self.client.jobs,self.client.record,self.client.raw)
        jobs=deepcopy(self.client.jobs);jobs[0]['steps'][0]['conclusion']='failure'
        with self.assertRaises(ValueError):self.scope.failed_runner(self.client.run,jobs,self.client.record,self.client.raw)
        with self.assertRaises(ValueError):self.scope.failed_runner(self.client.run,self.client.jobs,self.client.record,self.client.raw+b'x')
        with self.assertRaises(ValueError):self.scope.failed_runner(self.client.run,self.client.jobs,dict(self.client.record,expired=True),self.client.raw)

    def test_exact_failed_attempt_collector_rechecks_master_and_originals(self):
        with patch.object(r.runners,'contract',return_value=WORKFLOW),patch.object(r.time,'time',return_value=1200):
            result=self.scope.collect(self.req,self.b.root/'failed-origin',self.client)
            self.assertEqual('ORIGINAL_FAILED_RETENTION_VERIFIED_NOT_QUALIFIED',result['status'])
            self.assertEqual([901],self.client.downloads)
            self.client.data['branches/master']=dict(commit=dict(sha='f'*40))
            with self.assertRaises(ValueError):self.scope.collect(self.req,self.b.root/'moved-origin',self.client)

    def execute(self,fail=None):
        def collect(scope,req,path,client):
            self.b.calls.append('origin:experiment')
            return scope.failed_runner(self.client.run,self.client.jobs,self.client.record,self.client.raw)
        with patch.object(r.Scope,'collect',collect):return self.b.execute(fail)

    def test_complete_join_replays_all_members_and_reports_original_failure(self):
        value=self.execute();self.assertTrue(value['fullRemoteQualification']);self.assertEqual(31,len(self.b.calls))
        self.assertEqual('FAIL',value['continuation']['originalCompletionStatus'])
        self.assertFalse(value['continuation']['originalLedgerRewritten'])
        self.assertEqual(27428,value['totals']['reads']);self.assertEqual(439,value['totals']['formalNegativesPerLocation'])

    def test_replay_failure_missing_waiver_or_other_failed_member_never_qualifies(self):
        with self.assertRaisesRegex(ValueError,'physical failure'):self.execute('experiment')
        self.assertFalse(c.artifacts.read(self.b.output/'receipt.json')['fullRemoteQualification'])
        self.b.replayed['experiment'].pop('retentionRecovery')
        with self.assertRaisesRegex(ValueError,'waiver missing'):self.execute()
        other=self.b.chosen['canonical-1-legacy']['requestSha256']
        for row in self.b.ledger['value']['entries']:
            if row['requestSha256']==other and row['kind']=='FINISHED':row['status']='FAIL'
        with self.assertRaises(ValueError):c.evidence.inputs(self.b.values,self.b.bound,self.b.cfg,self.b.ledger['value'],continuation=self.scope)

    def test_fourteen_success_seals_cannot_be_substituted(self):
        for name in ('canonical-1-legacy','failure-drill-m03'):
            record=deepcopy(self.b.records[name]);self.scope.original(name,record)
            record['seal']['manifestSha256']='f'*64
            with self.assertRaises(ValueError):self.scope.original(name,record)

    def test_get_only_restoration_preserves_failure_and_missing_bytes_reject(self):
        from .cloud_provider_offline import Server
        objects=c.objects;server=Server(self.b.cfg['provider']);ledger=r.a.empty_ledger(domain='native')
        def seed(key,value):
            server.serial+=1;server.objects[key]=(server.serial,r.encoded(value),'application/json');return server.serial
        missing=None
        for i,value in enumerate(self.b.values):
            req=value['request'];name=req['selection']['member']['name'];f=self.b.fixtures[name]
            directory=self.b.root/('restore-input-'+name);directory.mkdir();path=directory/'authority.json';path.write_bytes(b'synthetic-original')
            manifest=objects.parts.scan({'authority.json':path},req)
            clean=deepcopy(f['clean']);completed=deepcopy(f['completed'])
            completed['evidenceSha256']=None if name=='experiment' else r.digest(r.encoded(manifest))
            pin=self.policy['originals'][name]
            pin.update(manifestSha256=r.digest(r.encoded(manifest)),completionSha256=r.digest(r.encoded(completed)))
            prefix=objects.control.attempt_key(req)
            seed(objects.p.context_key(req),objects.p.context(self.b.cfg['provider'],req,domain='native'))
            cg=seed(prefix+'completion.json',completed);kg=seed(objects.control.cleanup_key(req,completed['cleanupSha256']),clean)
            mg=seed(objects.retention.prefix(req)+'manifest.json',manifest)
            for ordinal,body in objects.parts.chunks({'authority.json':path},manifest):
                key=objects.retention.chunk_key(req,ordinal);seed(key,body)
                if name=='experiment':missing=key
            if name=='experiment':self.policy['failure'].update(manifestGeneration=mg,completionGeneration=cg,cleanupGeneration=kg)
            ledger=r.a.finish(r.a.reserve(ledger,req,previous_cost=i*4_000_000,cost=4_000_000),req,completed)
        seed(r.a.LEDGER,ledger);scope=r.Scope(self.b.cfg,self.b.bound,self.b.chosen)
        reader=objects.OfflineObjects(self.b.cfg,self.b.bound,server,self.b.root/'restore-reads');self.addCleanup(reader.close)
        selected={n:v['requestSha256'] for n,v in self.b.chosen.items()}
        result=objects.restore(reader,selected,self.b.root/'complete-restore',continuation=scope)
        experiment=next(v for v in result['inputs'] if v['request']['selection']['member']['name']=='experiment')
        self.assertEqual('FAIL',experiment['completed']['status']);self.assertIsNone(experiment['completed']['evidenceSha256'])
        self.assertFalse(result['receipt']['fullRemoteQualification']);self.assertEqual(15,len(result['inputs']))
        with self.assertRaises(ValueError):objects.restore(reader,selected,self.b.root/'ordinary-restore')
        server.objects.pop(missing)
        with self.assertRaises(Exception):objects.restore(reader,selected,self.b.root/'missing-restore',continuation=scope)
        self.assertTrue(all(v['method']=='GET' and v['body'] is None for v in server.events))


class FrozenRecoveryTest(unittest.TestCase):
    def test_actual_one_run_policy_is_pinned(self):
        policy=r.load();self.assertEqual(15,len(policy['originals']))
        self.assertEqual(40809895634,policy['originals']['experiment']['runId'])
        self.assertEqual(list(range(34,55)),policy['failure']['recoveredParts'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/r.POLICY;path.parent.mkdir(parents=True)
            changed=deepcopy(policy);changed['originals']['experiment']['runAttempt']=2;path.write_bytes(r.encoded(changed))
            with self.assertRaises(ValueError):r.load(directory)


if __name__=='__main__':unittest.main()

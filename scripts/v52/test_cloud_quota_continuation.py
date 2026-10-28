"""Batch opt-in boundaries; synthetic replay cannot establish cloud acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_quota_continuation as q, cloud_acceptance as c, cloud_operator as operator
from .test_cloud_member_seal import fixture as seal_fixture
from .test_cloud_prepared import arguments
from .test_cloud_set_evidence import fixture as set_fixture
from .test_cloud_runner_provenance import RunnerFixture, WORKFLOW


class BatchTest(unittest.TestCase):
    def setUp(self):
        plan=q.suite.load(); self.enterContext(patch.object(q.suite,'load',return_value=plan))
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root=Path(temp.name)
        self.policy=json.loads((q.ci.ROOT/q.POLICY).read_text())
        self.policy['newSequence']='d'*32; self.policy['inherited']={k:{} for k in self.policy['inherited']}
        self.values=[];self.records={};self.chosen={};self.fixtures={};baseline=None
        _,self.replayed,_,_,_=set_fixture()
        for i,name in enumerate(q.suite.MEMBERS,1):
            args=arguments(member=name,attempt=f'{i:032x}',baseline=baseline)
            if name in self.policy['remaining']:
                args.update(source='b'*40,sequence='d'*32)
                args['proof']['source'].update(source='b'*40,checkoutSha256='b'*64)
                args['proof'].update(buildManifestSha256='4'*64,packageSha256='5'*64)
            with patch('scripts.v52.test_cloud_member_seal.arguments',return_value=args): f=seal_fixture()
            f['ledger']['generation']=10+i;f['context'].update(runId=1000+i,runAttempt=1)
            value=c.seal.create(**f);self.fixtures[name]=f
            self.cfg=f['cfg'];self.ledger=f['ledger'];baseline=dict(generation=10+i,ledger=self.ledger['value'])
            row=dict(requestSha256=value['requestSha256'],runId=1000+i,runAttempt=1);self.chosen[name]=row
            record=dict(status='ORIGINAL_RUNNER_VERIFIED_NOT_QUALIFIED',source=f['source'],
                selected=dict(runId=1000+i,runAttempt=1),seal=value,artifactId=2000+i,artifactSha256=f'{i:064x}')
            self.records[name]=record
            if name in self.policy['inherited']:
                self.policy['oldSource']=f['source'];self.policy['oldBinding']=f['request']['selection']['binding']
                self.policy['inherited'][name]=dict(row,artifactId=record['artifactId'],artifactSha256=record['artifactSha256'],
                    **{k:value[k] for k in ('completionSha256','manifestSha256','cleanupSha256')})
            else:self.bound=f['source']
            self.values.append(dict(root=str(self.root/name),request=f['request'],manifest=f['manifest'],completed=f['completed'],cleanup=f['clean']))
            self.replayed[name].update(source=f['source'],selection=f['request']['selection'],requestSha256=row['requestSha256'])
            for binding in self.replayed[name]['bindings'].values():binding.update(f['source'])
        self.policy['configurationSha256']=q.preflight.configuration(self.cfg)
        self.enterContext(patch.object(q,'load',side_effect=lambda:deepcopy(self.policy)))
        self.enterContext(patch.object(q,'source_compatible'))
        self.scope=q.Scope(self.cfg,self.bound,self.chosen)
        self.envelope=dict(continuation=self.policy['id'],selected=self.chosen)
        self.calls=[]

    def test_explicit_input_only_and_exact_ten_old_pins(self):
        self.assertEqual(self.envelope,c.request(self.envelope))
        self.assertEqual(('verify-set',self.envelope),operator.environment(dict(V52_OPERATION='verify-set',V52_REQUEST=json.dumps(self.envelope))))
        for key in ('runId','runAttempt','requestSha256'):
            value=deepcopy(self.envelope);row=value['selected']['canonical-1-legacy']
            row[key]=('f'*64 if key=='requestSha256' else 999999)
            with self.subTest(key=key),self.assertRaises(ValueError):c.request(value)
        for change in (dict(continuation='future-batch'),dict(extra=True)):
            with self.assertRaises(ValueError):c.request(dict(self.envelope,**change))
        with self.assertRaises(ValueError):c.selection(self.envelope)

    def test_two_true_bindings_preserved_and_default_entry_rejects(self):
        selected,_,_=c.evidence.inputs(self.values,self.bound,self.cfg,self.ledger['value'],continuation=self.scope)
        self.assertEqual(self.policy['oldBinding'],selected['originalBindings']['canonical-1-minimum'])
        self.assertEqual('b'*40,selected['originalBindings']['experiment']['source'])
        with self.assertRaises(ValueError):c.evidence.inputs(self.values,self.bound,self.cfg,self.ledger['value'])
        with self.assertRaises(ValueError):q.suite.complete_selection([v['request']['selection'] for v in self.values])

    def test_remaining_sequence_source_and_build_drift_reject_even_with_selected_hash(self):
        for field,length in (('source',40),('checkoutSha256',64),('sequence',32),('buildManifestSha256',64),('packageSha256',64)):
            values=deepcopy(self.values);req=next(v['request'] for v in values if v['request']['selection']['member']['name']=='experiment')
            req['selection']['binding'][field]='f'*length
            # Even an explicitly selected new request must satisfy the frozen batch.
            chosen=deepcopy(self.chosen);chosen['experiment']['requestSha256']=q.a.validate_request(req,domain='native')
            scope=q.Scope(self.cfg,self.bound,chosen)
            with self.subTest(field=field),self.assertRaises(ValueError):scope.selections([v['request'] for v in values])

    def test_layout_or_ownership_policy_drift_rejects_even_when_hash_selected(self):
        for field,key in (('layout','dataDiskGiB'),('policy','budgetMicrousd')):
            req=deepcopy(next(v['request'] for v in self.values if v['request']['selection']['member']['name']=='experiment'))
            req[field][key]+=1;chosen=deepcopy(self.chosen)
            chosen['experiment']['requestSha256']=q.a.validate_request(req,domain='native')
            scope=q.Scope(self.cfg,self.bound,chosen)
            with self.subTest(field=field),self.assertRaises(ValueError):scope.validate_request(req)

    def test_missing_failed_or_duplicate_originals_never_qualify(self):
        for mutation in (lambda v:v.pop(),lambda v:v.__setitem__(-1,v[0]),lambda v:v[-1].update(root=v[0]['root'])):
            values=deepcopy(self.values);mutation(values)
            with self.assertRaises(ValueError):c.evidence.inputs(values,self.bound,self.cfg,self.ledger['value'],continuation=self.scope)
        ledger=deepcopy(self.ledger['value']);ledger['entries'][-1]['status']='FAIL'
        with self.assertRaisesRegex(ValueError,'terminal successes'):
            c.evidence.inputs(self.values,self.bound,self.cfg,ledger,continuation=self.scope)

    def test_artifact_and_immutable_object_pins_cannot_be_reselected(self):
        name='canonical-1-legacy';self.scope.original(name,self.records[name])
        for key in ('artifactId','artifactSha256','completionSha256','manifestSha256','cleanupSha256'):
            record=deepcopy(self.records[name])
            target=record if key.startswith('artifact') else record['seal'];target[key]=999 if key=='artifactId' else 'f'*64
            with self.subTest(key=key),self.assertRaises(ValueError):self.scope.original(name,record)

    def test_guard_rejects_mutated_source_config_and_scope(self):
        for field in ('source','cfg','policy','chosen'):
            scope=q.Scope(self.cfg,self.bound,self.chosen);getattr(scope,field)['tampered']=True
            with self.subTest(field=field),self.assertRaises(ValueError):scope.guard()
        cfg=deepcopy(self.cfg);cfg['projectNumber']='99999'
        with self.assertRaises(ValueError):q.Scope(cfg,self.bound,self.chosen)
        source=deepcopy(self.bound);source['java']['java.vendor']='other'
        with self.assertRaises(ValueError):q.Scope(self.cfg,source,self.chosen)

    def execute(self,fail=None):
        output=self.root/('accept-'+str(len(list(self.root.iterdir()))))
        def restore(source,selected,path,**kw):
            self.calls.append('restore');kw['continuation'].guard(self.bound,self.cfg)
            (path/'originals').mkdir(parents=True);c.artifacts.save(path/'originals/ledger-after.json',self.ledger)
            return dict(inputs=deepcopy(self.values),ledger=self.ledger['value'],receipt=dict(status='ORIGINALS_RESTORED_NOT_QUALIFIED',execution='native-v52-evidence-reads'))
        def provenance(source,req,chosen,path,**kw):
            name=kw['continuation'].validate_request(req);self.calls.append('origin:'+name)
            return deepcopy(self.records[name])
        def physical(root,req,manifest,completed,cleanup,ledger,source,cfg,path,**kw):
            name=req['selection']['member']['name'];self.calls.append('replay:'+name)
            self.assertEqual(self.scope.member_source(name),source);self.assertEqual(self.policy['artifactPins'],kw['artifact_pins'])
            if fail==name:raise ValueError('original physical failure')
            value=deepcopy(self.replayed[name]);path.mkdir();c.artifacts.save(path/'receipt.json',value);return value
        with patch.object(c.reads,'source_configuration',return_value=self.cfg),patch.object(c.inputs,'checkout',return_value=self.bound), \
             patch.object(c.runners,'contract',return_value='unchanged'),patch.object(c.objects,'restore_native',side_effect=restore), \
             patch.object(c.runners,'collect_native',side_effect=provenance),patch.object(c.evidence.member,'replay',side_effect=physical), \
             patch.object(c.member.Progress,'report'):
            self.output=output;return c.verify_native(self.bound['source'],self.envelope,output)

    def test_complete_join_replays_every_original_and_retains_exception_in_final_summary(self):
        result=self.execute();self.assertTrue(result['fullRemoteQualification']);self.assertEqual('PASS',result['status'])
        self.assertEqual(31,len(self.calls));self.assertEqual(27428,result['totals']['reads'])
        self.assertEqual(439,result['totals']['formalNegativesPerLocation'])
        self.assertEqual(self.policy['oldSource'],result['continuation']['oldSource'])
        self.assertEqual(self.bound,result['continuation']['newSource']);self.assertEqual(self.chosen,result['selected'])
        self.assertEqual(self.policy['oldBinding'],result['originalBindings']['canonical-1-legacy'])
        report=operator.report_data('verify-set',self.bound['source'],result,self.root)
        self.assertEqual(result['continuation'],report['continuation'])

    def test_one_replay_failure_or_invocation_change_never_promotes(self):
        with self.assertRaisesRegex(ValueError,'physical failure'):self.execute('failure-drill-m03')
        self.assertFalse(c.artifacts.read(self.output/'receipt.json')['fullRemoteQualification'])
        self.replayed['experiment']['invocation']['attempt']=2
        with self.assertRaisesRegex(ValueError,'original protected invocation'):self.execute()
        self.assertFalse(c.artifacts.read(self.output/'receipt.json')['fullRemoteQualification'])

    def test_missing_negatives_or_reused_resources_still_fail_scoped_reduction(self):
        for kind in ('negative','resource'):
            original=deepcopy(self.replayed)
            if kind=='resource':self.replayed['experiment']['claim']=self.replayed['canonical-1-legacy']['claim']
            else:
                key=q.suite.member('failure-drill-m02-equal')['histories'][0]
                self.replayed['failure-drill-m02-equal']['histories'][key]['result']['negatives']=[]
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.execute()
            self.assertFalse(c.artifacts.read(self.output/'receipt.json')['fullRemoteQualification']);self.replayed=original

    def test_original_provenance_uses_old_run_source_and_current_master(self):
        name='canonical-1-legacy';f=self.fixtures[name];seal=deepcopy(self.records[name]['seal'])
        seal['credentialContext'].update(runId=123456,runAttempt=2)
        client=RunnerFixture(seal);client.data['branches/master']=dict(commit=dict(sha=self.bound['source']))
        selected=dict(self.chosen);selected[name]=dict(selected[name],runId=123456,runAttempt=2)
        self.policy['inherited'][name].update(runId=123456,runAttempt=2,artifactId=901,artifactSha256=q.digest(client.raw))
        scope=q.Scope(self.cfg,self.bound,selected)
        path=self.root/'origin';path.mkdir()
        result=c.runners.collect(path,self.cfg,f['source'],f['request'],client.chosen,WORKFLOW,client,lambda:1200,continuation=scope)
        scope.original(name,result);self.assertEqual('a'*40,result['source']['source'])
        observation=c.artifacts.read(path/'observation.json');self.assertEqual('b'*40,observation['masterBefore'])
        observation['masterAfter']='c'*40
        with self.assertRaisesRegex(ValueError,'source/configuration'):
            c.runners.validate(observation,self.cfg,f['source'],f['request'],client.chosen,path/'runner.zip',WORKFLOW,1200,continuation=scope)
        with self.assertRaises(ValueError):c.runners.validate(dict(observation,masterAfter='b'*40),self.cfg,f['source'],f['request'],client.chosen,path/'runner.zip',WORKFLOW,1200)

    def test_original_objects_restore_two_bound_groups_with_generation_pins(self):
        r=c.objects
        from .cloud_provider_offline import Server
        server=Server(self.cfg['provider']);ledger=q.a.empty_ledger(domain='native')
        def seed(key,value):
            server.serial+=1;server.objects[key]=(server.serial,q.encoded(value),'application/json')
        for i,value in enumerate(self.values):
            req=value['request'];name=req['selection']['member']['name'];root=self.root/('raw-'+name);root.mkdir()
            path=root/'authority.json';path.write_bytes(b'synthetic input')
            paths={'authority.json':path};manifest=r.parts.scan(paths,req)
            clean=dict(status='PASS',checks=[],errors=[],leftovers=[]);completed=deepcopy(value['completed'])
            completed.update(evidenceSha256=q.digest(q.encoded(manifest)),cleanupSha256=q.digest(q.encoded(clean)))
            seed(r.p.context_key(req),r.p.context(self.cfg['provider'],req,domain='native'))
            seed(r.control.attempt_key(req)+'completion.json',completed)
            seed(r.control.cleanup_key(req,completed['cleanupSha256']),clean);seed(r.retention.prefix(req)+'manifest.json',manifest)
            for ordinal,body in r.parts.chunks(paths,manifest):seed(r.retention.chunk_key(req,ordinal),body)
            ledger=q.a.finish(q.a.reserve(ledger,req,previous_cost=i*4_000_000,cost=4_000_000),req,completed)
        seed(q.a.LEDGER,ledger)
        reader=r.OfflineObjects(self.cfg,self.bound,server,self.root/'reads');self.addCleanup(reader.close)
        selected={k:v['requestSha256'] for k,v in self.chosen.items()}
        with self.assertRaises(ValueError):r.restore(reader,selected,self.root/'ordinary')
        value=r.restore(reader,selected,self.root/'restored',continuation=self.scope)
        self.assertEqual(15,len(value['inputs']));self.assertFalse(value['receipt']['fullRemoteQualification'])
        self.assertTrue(all(row['method']=='GET' and row['body'] is None for row in server.events))


class FrozenPolicyTest(unittest.TestCase):
    def test_actual_policy_inventory_and_pinned_core(self):
        policy=q.load();self.assertEqual(10,len(policy['inherited']));self.assertEqual(5,len(policy['remaining']))
        self.assertEqual(set(q.suite.MEMBERS),set(policy['inherited'])|set(policy['remaining']))
        for name,sha in policy['approvedSourceChanges'].items():
            self.assertEqual(sha,q.digest((q.ci.ROOT/name).read_bytes()),name)
        for key in ('newSequence','oldSource','inherited','artifactPins','configurationSha256'):
            changed=deepcopy(policy);changed[key]='tampered'
            with tempfile.TemporaryDirectory() as root:
                path=Path(root)/q.POLICY;path.parent.mkdir(parents=True);path.write_bytes(q.encoded(changed))
                with self.subTest(key=key),self.assertRaises(ValueError):q.load(root)

    def test_source_guard_checks_whole_tree_with_no_historical_objects_required(self):
        policy=q.load();source='e'*40
        raw=subprocess.check_output(['git','ls-tree','-r','-z','HEAD'],cwd=q.ci.ROOT)
        tree={row.split(b'\t')[1].decode():row.split(b'\t')[0].decode() for row in raw.split(b'\0') if row}
        files={name:(q.ci.ROOT/name).read_bytes() for name in (*policy['approvedSourceChanges'],q.POLICY)}
        for name in files:tree[name]='100644 blob '+'e'*40
        def git(root,*args):
            if args==('ls-tree','-r','-z',source):return b'\0'.join((v+'\t'+k).encode() for k,v in tree.items())+b'\0'
            if args[0]=='show' and args[1].startswith(source+':'):return files[args[1].split(':',1)[1]]
            raise AssertionError('unexpected history/network access: '+str(args))
        with patch.object(q.inputs.build,'git',side_effect=git):
            q.source_compatible(source,policy)
            tree['pom.xml']='100644 blob '+'0'*40
            with self.assertRaisesRegex(ValueError,'unapproved source'):q.source_compatible(source,policy)
            tree.pop('pom.xml')
            with self.assertRaises(ValueError):q.source_compatible(source,policy)

    def test_member_replay_rejects_changed_jar_before_any_history(self):
        member=c.evidence.member
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'original';root.mkdir()
            pins={'artifacts/a.jar':dict(bytes=1,sha256=q.digest(b'a'))}
            with patch.object(member,'inventory',return_value=root),patch.object(member.artifacts,'read',return_value={}), \
                 patch.object(member.authority,'replay',return_value=dict(files={'artifacts/a.jar':b'b'})), \
                 patch.object(member,'replay_history') as replay:
                with self.assertRaisesRegex(ValueError,'executable bytes differ'):
                    member.replay(root,{}, {}, {}, {}, {}, {}, {}, Path(directory)/'replay',artifact_pins=pins)
                replay.assert_not_called()

    def test_actual_artifact_pins_require_every_jar_byte(self):
        files={'artifacts/a.jar':b'a','artifacts/b.jar':b'b','source.json':b'{}'}
        pins={k:dict(bytes=len(v),sha256=q.digest(v)) for k,v in files.items() if k.startswith('artifacts/')}
        q.artifacts_match(files,pins)
        for altered in (dict(files,**{'artifacts/a.jar':b'x'}),{k:v for k,v in files.items() if k!='artifacts/b.jar'},dict(files,**{'artifacts/c.jar':b'c'})):
            with self.assertRaises(ValueError):q.artifacts_match(altered,pins)


if __name__=='__main__':unittest.main()

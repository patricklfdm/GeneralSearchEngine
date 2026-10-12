"""Offline mutations; fabricated records never count as native qualification."""
from copy import deepcopy
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch, Mock
import zipfile
from . import native_image_continuation as v, cloud_native_authority as n
from . import performance_model as m, native_preset_timing as t, test_cloud_package as packages

SOURCE = 'a'*40


def wrapped(value):
    raw=m.canonical(value)
    return dict(generation=1, bytes=len(raw), sha256=m.sha(raw), value=value)


def fixture(names=(*v.INHERITED, *v.REMAINING)):
    frozen=deepcopy(v.policy()); frozen['inherited']={}; ledger=n.empty_ledger(); members={}; plans={}
    for index, name in enumerate(names):
        inherited=name in v.INHERITED
        req=n.request(frozen['oldSource'] if inherited else SOURCE, 'b'*64, frozen['configurationSha256'],
            frozen['oldSequence'] if inherited else frozen['sequence'], format(index+1,'032x'), name,
            now=1000+index, order='any-order', guest_access_sha256='d'*64,
            timing_profile=t.allocation(name,soft=True)['profile'], timing_plan_sha256=t.SOFT_PLAN_SHA256)
        sha=n.validate_request(req); allocation=t.validate(req); scope='owned-complete-'+allocation['preset']
        evidence=dict(status='PASS',execution=n.EXECUTION,paidCloud=True,engineWorkloadExecuted=True,
            fullRemoteQualification=False,physicalHistoryQualified=True,cells=allocation['cells'],errors=[],scope=scope)
        if name!='failure-drill':evidence['backupRestoreQualified']=True
        if name.startswith('canonical-'):
            evidence.update(repetition=allocation['repetition'],aggregate=dict(status='PASS',calls=1080,
                repetition=allocation['repetition'],requestSha256=sha,ownedCanonicalQualified=True))
        prefix=v.a.PREFIX+'attempts/'+sha+'/owned-experiment/'
        inventory=dict(schema='gse-v51-native-owned-evidence-v2',requestSha256=sha,files={
            prefix+'evidence.json':dict(bytes=len(m.canonical(evidence)),sha256=m.sha(m.canonical(evidence))),
            **{prefix+p:dict(bytes=1,sha256='e'*64) for p in ('metadata/parts.json','parts/parts.json')}})
        plan=dict(resourcePlan=dict(request=req));plans[name]=plan
        completion=dict(schema=n.COMPLETION_SCHEMA,status='PASS',requestSha256=sha,errors=[],
            execution=n.EXECUTION,paidCloud=True,engineWorkloadExecuted=True,fullRemoteQualification=False,
            qualificationScope=scope,evidence=evidence,evidenceSha256=m.sha(m.canonical(evidence)),
            inventorySha256=m.sha(m.canonical(inventory)),preparation=dict(planSha256=m.sha(m.canonical(plan))),
            cleanup=dict(status='PASS',errors=[],leftovers=[],checks=[dict(name=r['name'],expectedId=str(i+1),
                observed=None,absent=True) for i,r in enumerate(n.resources(req))]))
        rows=dict(zip(v.RECORDS,map(wrapped,(completion,evidence,inventory))));members[name]=rows
        if inherited:frozen['inherited'][name]=dict(requestSha256=sha,records={k:r['sha256'] for k,r in rows.items()})
        total,_=n.inspect_ledger(ledger)
        ledger=n.reserve(ledger,req,dict(previousCostMicrousd=total,maximumCostMicrousd=25_000_000))
        ledger=n.finish(ledger,req,completion)
    obs=dict(schema=v.SCHEMA,source=SOURCE,policySha256=m.sha(m.canonical(frozen)),ledgerGeneration=1,
             ledger=ledger,lease=None,members=members)
    return frozen,obs,plans


class ContinuationTest(unittest.TestCase):
    def review(self,frozen,obs,plans):
        roots={k:k for k in plans if k in v.REMAINING and k in obs['members']}
        with patch.object(v,'policy',return_value=frozen), patch.object(v,'source_compatible',return_value=['repair']) as source,\
             patch.object(v,'prepared',side_effect=lambda root,*_:plans[root]) as prepared:
            result=v.review(obs,SOURCE,roots)
            source.assert_called_once_with(SOURCE,frozen)
            self.assertEqual(len(roots),prepared.call_count)
            return result

    def test_checked_in_exception_has_only_two_exact_historical_runs(self):
        p=v.policy()
        self.assertEqual([38280933954,38300809738],[p['inherited'][k]['runId'] for k in v.INHERITED])
        self.assertEqual('68efdd6b99df497fb1b1dd6d87947fb4',p['sequence'])
        self.assertEqual(list(v.REMAINING),p['remaining'])
        self.assertEqual('763874002631433611',p['image']['imageId'])
        scripts={name for name in p['allowedChanges'] if name.startswith('scripts/')}
        self.assertEqual(scripts,set(p['approvedScripts']))
        # Digests freeze this batch's source, not every future checkout. Later
        # phases may evolve these scripts without inheriting this exception.
        for digest in p['approvedScripts'].values():v.a.digest(digest)

    def test_source_and_package_failures_propagate_without_partial_acceptance(self):
        f,o,p=fixture()
        with patch.object(v,'policy',return_value=f),patch.object(v,'source_compatible',side_effect=ValueError('drift')),\
             self.assertRaisesRegex(ValueError,'drift'):v.review(o,SOURCE,{})
        with patch.object(v,'policy',return_value=f),patch.object(v,'source_compatible',return_value=[]),\
             patch.object(v,'prepared',side_effect=ValueError('package drift')),self.assertRaisesRegex(ValueError,'package drift'):
            v.review(o,SOURCE,{name:name for name in v.REMAINING})

    def test_two_inherited_passes_are_partial_then_all_five_complete(self):
        for names in (v.INHERITED,(*v.INHERITED,'canonical-3'),(*v.INHERITED,*v.REMAINING)):
            f,o,p=fixture(names);original=deepcopy(o);result=self.review(f,o,p)
            self.assertEqual('PASS' if len(names)==5 else 'PARTIAL',result['status'])
            self.assertEqual(len(names)==5,result['batchComplete'])
            self.assertFalse(result['fullRemoteQualification']);self.assertFalse(result['ledgerModified'])
            self.assertFalse(result['paidAdmission']);self.assertEqual(original,o)
            self.assertEqual(25_000_000*len(names),result['recordedCostMicrousd'])
            self.assertEqual(2,sum(r['inherited'] for r in result['members']))

    def test_remaining_members_are_order_independent(self):
        import itertools
        for order in itertools.permutations(v.REMAINING):
            f,o,p=fixture((*v.INHERITED,*order));self.assertTrue(self.review(f,o,p)['batchComplete'])

    def test_future_source_sequence_image_timing_and_old_request_cannot_borrow_exception(self):
        f,o,p=fixture();req=p['canonical-3']['resourcePlan']['request']
        for key,value in [('source','c'*40),('sequence','d'*32),('configurationSha256','c'*64),
                          ('timingPlanSha256','c'*64),('workloadSha256','c'*64),('member','canonical-1')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                v.request_compatible(dict(req,**{key:value}),f,SOURCE)
        old=p['canonical-1']['resourcePlan']['request']
        with self.assertRaises(ValueError):v.request_compatible(dict(old,attempt='e'*32),f,SOURCE)

    def test_default_ledger_still_rejects_source_drift_in_one_sequence(self):
        f,o,p=fixture(v.INHERITED);req=dict(p['canonical-2']['resourcePlan']['request'],source=SOURCE,member='canonical-3',attempt='f'*32)
        total,_=n.inspect_ledger(o['ledger'])
        with self.assertRaisesRegex(ValueError,'sequence changed'):
            n.reserve(o['ledger'],req,dict(previousCostMicrousd=total,maximumCostMicrousd=25_000_000))

    def test_lease_pending_missing_duplicate_or_tampered_evidence_cannot_complete(self):
        f,o,p=fixture()
        changes=[lambda x:x.update(lease={}),lambda x:x['members'].pop('canonical-1'),
            lambda x:x['members'].update(extra=x['members']['canonical-1']),
            lambda x:x['ledger']['entries'].pop(),
            lambda x:x['members']['canonical-1']['completion.json'].update(sha256='e'*64),
            lambda x:x['members']['canonical-3']['completion.json']['value'].update(status='FAIL')]
        for change in changes:
            bad=deepcopy(o);change(bad)
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):self.review(f,bad,p)

    def test_rehashed_new_completion_still_requires_cleanup_and_independent_results(self):
        f,o,p=fixture();name='canonical-3';req=p[name]['resourcePlan']['request']
        for change in (lambda c:c['cleanup']['checks'][0].update(absent=False),
                       lambda c:c['cleanup']['checks'].pop(),lambda c:c.update(fullRemoteQualification=True),
                       lambda c:c['preparation'].update(planSha256='f'*64)):
            rows=deepcopy(o['members'][name]);c=rows['completion.json']['value'];change(c);rows['completion.json']=wrapped(c)
            ledger=deepcopy(o['ledger'])
            next(r for r in ledger['entries'] if r.get('completionSha256')==o['members'][name]['completion.json']['sha256'])['completionSha256']=rows['completion.json']['sha256']
            with self.assertRaises(ValueError):v.member(req,rows,ledger,f,p[name])

    def test_rehashed_old_completion_cannot_replace_pinned_record(self):
        f,o,p=fixture();name='canonical-1';rows=deepcopy(o['members'][name])
        rows['completion.json']['value']['extra']='rewritten';rows['completion.json']=wrapped(rows['completion.json']['value'])
        ledger=deepcopy(o['ledger']);ledger['entries'][1]['completionSha256']=rows['completion.json']['sha256']
        with self.assertRaisesRegex(ValueError,'pinned historical'):
            v.member(p[name]['resourcePlan']['request'],rows,ledger,f)

    def test_source_diff_rejects_engine_workflow_or_unapproved_script_changes(self):
        f=v.policy();f['approvedScripts']={'scripts/v51/cloud_image_policy.py':m.sha(b'approved')}
        def output(*args):
            if args[0]=='diff':return b'scripts/v51/cloud_image_policy.py\0'
            if args[0]=='show':return m.canonical(f) if args[1].endswith(v.POLICY_PATH) else b'approved'
            return b''
        with patch.object(v,'git',side_effect=output):self.assertTrue(v.source_compatible(SOURCE,f))
        for path in ('src/main/java/Engine.java','pom.xml','.github/workflows/ci.yml','scripts/v51/guest_owned_canonical.py'):
            with patch.object(v,'git',side_effect=lambda *a: path.encode()+b'\0' if a[0]=='diff' else output(*a)),\
                 self.assertRaisesRegex(ValueError,'outside image repair'):v.source_compatible(SOURCE,f)
        with patch.object(v,'git',side_effect=lambda *a:b'changed' if a[0]=='show' else output(*a)),\
             self.assertRaisesRegex(ValueError,'approved script'):v.source_compatible(SOURCE,f)
        with self.assertRaisesRegex(ValueError,'corrected source'):v.source_compatible(f['oldSource'],f)

    def test_collect_is_generation_bound_get_only_and_rechecks_control(self):
        f,o,p=fixture(v.INHERITED)
        objects={n.LEDGER:(1,o['ledger']),n.LEASE:None}
        for name,rows in o['members'].items():
            sha=n.validate_request(p[name]['resourcePlan']['request'])
            for key,row in rows.items():objects[v.a.PREFIX+'attempts/'+sha+'/'+key]=(1,m.canonical(row['value']))
        store=Mock();store.get.side_effect=lambda key:deepcopy(objects[key])
        with tempfile.TemporaryDirectory() as tmp,patch.object(v,'policy',return_value=f),\
             patch.object(v,'source_compatible'),patch.object(v.h,'Api'),patch.object(v.g,'Store',return_value=store):
            path=Path(tmp)/'observations.json';v.collect(SOURCE,path)
            result=self.review(f,v.c.read(path),p);self.assertEqual('PARTIAL',result['status'])
            self.assertTrue(all(call[0]=='get' for call in store.mock_calls))
            count=[0]
            def drift(key):
                if key==n.LEDGER:
                    count[0]+=1
                    if count[0]==2:return (2,o['ledger'])
                return deepcopy(objects[key])
            store.get.side_effect=drift
            with self.assertRaisesRegex(ValueError,'control changed'):v.collect(SOURCE,Path(tmp)/'changed.json')

    def test_package_binding_checks_actual_bytes_and_excludes_only_ci_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);guest=root/'guest';manifest=packages.fixture(guest)
            manifest.update(adapterSources={},dirty=False)
            helper=m.canonical(dict(schema='gse-v51-helper-payload-v1',source=SOURCE,files={'example.py':'cHJvZ3JhbQ=='}))
            (guest/'startup-helper.json').write_bytes(helper);manifest['files']=v.package.inventory(guest)
            (guest/'manifest.json').write_bytes(m.canonical(manifest))
            (root/'originals').mkdir();archive=root/'guest.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                for path in sorted(guest.rglob('*')):
                    if path.is_file():tar.add(path,arcname=path.relative_to(guest).as_posix())
            raw=archive.read_bytes();zpath=root/'originals/package.zip'
            with zipfile.ZipFile(zpath,'w') as z:
                z.writestr('guest.tar.gz',raw);z.writestr('package/manifest.json',m.canonical(manifest))
            f,o,plans=fixture();plan=deepcopy(plans['canonical-3']);req=plan['resourcePlan']['request']
            plan['configuration']=v.c.read(v.ci.ROOT/'docs/v5x/v5.1/phase6-preflight-config.json')
            req['bundleSha256']=m.sha(raw)
            proof=dict(archiveSha256=m.sha(raw),packageManifestSha256=m.sha(m.canonical(manifest)),
                buildBinding=manifest['buildBinding'],buildManifestSha256=manifest['buildManifestSha256'],source=SOURCE,
                artifacts=dict(package=dict(sha256=m.sha(zpath.read_bytes()))))
            plan['artifacts']=proof;(root/'plan.json').write_bytes(m.canonical(plan))
            f['payloadSha256']=m.sha(m.canonical(v.payload(manifest,helper)))
            self.assertEqual(plan,v.prepared(root,f,SOURCE))
            with self.assertRaisesRegex(ValueError,'payload changed'):v.prepared(root,dict(f,payloadSha256='e'*64),SOURCE)
            zpath.write_bytes(zpath.read_bytes()+b'tamper')
            with self.assertRaisesRegex(ValueError,'original package ZIP'):v.prepared(root,f,SOURCE)
            projection=v.payload(manifest,helper)
            self.assertEqual(len(manifest['files'])-1,len(projection['files']))
            for path in ('guest.py','runtime/bin/java','workload.json'):
                changed=deepcopy(manifest);next(r for r in changed['files'] if r['path']==path)['sha256']='f'*64
                self.assertNotEqual(projection,v.payload(changed,helper))
            moved=deepcopy(manifest);moved['source']='b'*40
            moved_helper=m.canonical(dict(m.strict_json(helper),source=moved['source']))
            next(r for r in moved['files'] if r['path']=='startup-helper.json')['sha256']=m.sha(moved_helper)
            self.assertEqual(projection,v.payload(moved,moved_helper))
            with self.assertRaisesRegex(ValueError,'helper source'):v.payload(manifest,moved_helper)
            changed_helper=m.canonical(dict(m.strict_json(helper),files={'example.py':'Y2hhbmdlZA=='}))
            changed=deepcopy(manifest)
            next(r for r in changed['files'] if r['path']=='startup-helper.json').update(sha256=m.sha(changed_helper),size=len(changed_helper))
            self.assertNotEqual(projection,v.payload(changed,changed_helper))


if __name__ == '__main__':unittest.main()

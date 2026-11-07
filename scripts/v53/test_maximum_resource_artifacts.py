"""Real ZIP byte checks around synthetic API jobs; no physical qualification."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import stat
import unittest
from unittest.mock import patch
import zipfile
from . import maximum_resource_artifacts as a
from . import test_maximum_resource_workflows as fixture


class MaximumArtifactTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.MaximumWorkflowTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.index=self.fixture.path;self.value=self.fixture.index;self.api=self.fixture.api
        self.zips=self.root/'zips';self.bundles=self.root/'bundles';self.outputs=0;self.calls=[];self.identifier=1
        for name,adapter in self.fixture.modules.items():
            ctx=self.value['cohorts'][name];rows=[];(self.zips/name).mkdir(parents=True)
            for kind in ('seed','raw'):
                data=self.root/(name+'-'+kind);data.mkdir();(data/'synthetic.txt').write_text('not a native original')
                adapter.pack(data,self.bundles/name/kind,ctx,kind)
                path=self.zips/name/(kind+'.zip');self.make_zip(path,self.bundles/name/kind)
                row=dict(id=self.identifier,name=a.workflows.artifact_name(name,ctx,kind),size_in_bytes=path.stat().st_size,
                    digest='sha256:'+a.tc.file_hash(path),expired=False,created_at='2026-01-01T00:00:00Z',
                    updated_at='2026-01-01T00:01:00Z',expires_at='2100-01-01T00:00:00Z',
                    workflow_run=dict(id=int(ctx['run']),repository_id=a.w.REPOSITORY_ID,head_repository_id=a.w.REPOSITORY_ID,
                        head_sha=ctx['source'],head_branch=ctx['ref'].removeprefix('refs/heads/')))
                self.identifier+=1;rows.append(row)
            self.api[f"actions/runs/{ctx['run']}/artifacts?per_page=100&page=1"]=dict(total_count=2,artifacts=rows)

    def make_zip(self,path,bundle,changes=None):
        values={n:(bundle/n).read_bytes() for n in ('manifest.json','bundle.tar.gz')}
        if changes:changes(values)
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in values.items():archive.writestr(name,data)

    def rows(self,name='maximum-native'):
        return self.api[f"actions/runs/{self.value['cohorts'][name]['run']}/artifacts?per_page=100&page=1"]['artifacts']

    def get(self,path):self.calls.append(path);return json.dumps(self.api[path],sort_keys=True).encode()

    def run_binding(self,get=None):
        self.outputs+=1;self.output=self.root/('binding-'+str(self.outputs))
        with redirect_stdout(io.StringIO()):return a.bind(self.index,self.zips,self.bundles,self.output,get or self.get)

    def test_exact_live_jobs_and_all_four_zip_bundle_pairs_bind_without_runtime_credit(self):
        result=self.run_binding();self.assertEqual('PARTIAL',result['status'])
        self.assertTrue(result['artifactBytesBound']);self.assertTrue(result['workflowExecutionAttested'])
        self.assertEqual((6,2),(result['selectedJobs'],result['priorAttempts']));self.assertTrue(result['priorAttemptsRequireReview'])
        for k in ('originalHistoriesReplayed','priorFailuresResolved','combinedResourcesQualified','phase3Complete'):self.assertFalse(result[k])
        bound=a.seeds.read(self.output/'bindings.json');self.assertEqual(set(self.fixture.modules),set(bound))
        for name in bound:
            for kind in bound[name]:self.assertEqual(a.tc.file_hash(self.zips/name/(kind+'.zip')),bound[name][kind]['zipSha256'])
        self.assertTrue((self.output/'workflow-before/api/maximum-native/attempt-1/run.json').is_file())
        self.assertEqual(32,len(self.calls))

    def test_missing_duplicate_expired_or_wrong_source_api_artifacts_fail_closed(self):
        original=copy.deepcopy(self.api)
        changes=[lambda rows:rows[0].update(digest=None),lambda rows:rows[0].update(expired=True),
            lambda rows:rows[0]['workflow_run'].update(head_sha='b'*40),lambda rows:rows[0]['workflow_run'].update(repository_id=1),
            lambda rows:rows[0].update(size_in_bytes=True),lambda rows:rows[0].update(name='previous-attempt-seed'),
            lambda rows:rows[1].update(name=rows[0]['name']),lambda rows:rows[1].update(id=rows[0]['id']),
            lambda rows:rows[0].update(expires_at='2026-01-01T00:01:00Z')]
        for i,change in enumerate(changes):
            self.api=copy.deepcopy(original);change(self.rows())
            with self.subTest(i=i),self.assertRaises(ValueError):self.run_binding()
            result=a.seeds.read(self.output/'receipt.json');self.assertEqual('FAIL',result['status']);self.assertFalse(result['artifactBytesBound'])

    def test_list_pagination_retains_prior_artifacts_and_rejects_truncation(self):
        endpoint='actions/runs/100/artifacts?per_page=100&page=1';selected=copy.deepcopy(self.rows());template=selected[0]
        prior=[dict(template,id=1000+i,name='prior-or-diagnostic-'+str(i),expired=True) for i in range(99)]
        rows=prior+selected
        self.api[endpoint]=dict(total_count=101,artifacts=rows[:100]);self.api[endpoint[:-1]+'2']=dict(total_count=101,artifacts=rows[100:])
        self.run_binding();self.assertTrue((self.output/'artifacts-before/maximum-native/page-2.json').is_file())
        self.api[endpoint[:-1]+'2']['artifacts']=[]
        with self.assertRaisesRegex(ValueError,'truncated'):self.run_binding()

    def test_zip_api_digest_and_same_context_inner_bytes_are_both_required(self):
        path=self.zips/'maximum-native/raw.zip';original=path.read_bytes();row=self.rows()[1];record=copy.deepcopy(row)
        # A fresh ZIP digest alone cannot authenticate altered inner bytes.
        self.make_zip(path,self.bundles/'maximum-native/raw',lambda v:v.update({'bundle.tar.gz':b'x'*len(v['bundle.tar.gz'])}))
        with self.assertRaisesRegex(ValueError,'API ZIP digest'):self.run_binding()
        row.update(size_in_bytes=path.stat().st_size,digest='sha256:'+a.tc.file_hash(path))
        with self.assertRaisesRegex(ValueError,'ZIP differs'):self.run_binding()
        path.write_bytes(original);row.clear();row.update(record)
        bundle=self.bundles/'maximum-native/raw';manifest=a.seeds.read(bundle/'manifest.json')
        manifest['context']['attempt']='1';a.h.save(bundle/'manifest.json',manifest);self.make_zip(path,bundle)
        row.update(size_in_bytes=path.stat().st_size,digest='sha256:'+a.tc.file_hash(path))
        with self.assertRaisesRegex(ValueError,'inner workflow/profile'):self.run_binding()

    def test_zip_shape_paths_links_duplicates_and_member_bounds(self):
        component='maximum-native';kind='seed';path=self.zips/component/(kind+'.zip');bundle=self.bundles/component/kind
        row=self.rows()[0];ctx=self.value['cohorts'][component];adapter=self.fixture.modules[component]
        for mode in ('extra','traversal','link','directory','duplicates','wrong-size','unsupported-compression'):
            with zipfile.ZipFile(path,'w') as archive:
                for name in ('manifest.json','bundle.tar.gz'):
                    actual='../manifest.json' if mode=='traversal' and name=='manifest.json' else name
                    info=zipfile.ZipInfo(actual)
                    if name=='manifest.json':
                        if mode=='link':info.external_attr=(stat.S_IFLNK|0o777)<<16
                        if mode=='directory':info.external_attr=(stat.S_IFDIR|0o777)<<16
                        if mode=='unsupported-compression':info.compress_type=zipfile.ZIP_BZIP2
                    raw=(bundle/name).read_bytes()
                    archive.writestr(info,raw+b'x' if mode=='wrong-size' and name=='manifest.json' else raw)
                if mode=='extra':archive.writestr('extra.txt',b'x')
                if mode=='duplicates':
                    import warnings
                    with warnings.catch_warnings():warnings.simplefilter('ignore');archive.writestr('manifest.json',b'x')
            row.update(size_in_bytes=path.stat().st_size,digest='sha256:'+a.tc.file_hash(path))
            with self.subTest(mode=mode),self.assertRaises(ValueError):a.zip_binding(path,bundle,row,ctx,adapter,kind)

    def test_changed_selected_metadata_and_later_rerun_are_detected(self):
        original=copy.deepcopy(self.api);counts={}
        def changed(path):
            counts[path]=counts.get(path,0)+1
            if path=='actions/runs/100/artifacts?per_page=100&page=1' and counts[path]==2:self.rows()[0]['id']=400
            return self.get(path)
        with self.assertRaisesRegex(ValueError,'selected metadata changed'):self.run_binding(changed)
        self.api=copy.deepcopy(original);counts={}
        def rerun(path):
            counts[path]=counts.get(path,0)+1
            if path=='actions/runs/100' and counts[path]==4:self.api[path]['run_attempt']=3
            return self.get(path)
        with self.assertRaisesRegex(ValueError,'exact context'):self.run_binding(rerun)

    def test_late_local_change_is_not_hidden_by_original_api_digest(self):
        real=a.zip_binding;calls=0
        def changed(*args):
            nonlocal calls
            result=real(*args);calls+=1
            if calls==4:(self.bundles/'maximum-native/seed/manifest.json').write_bytes(b'{}')
            return result
        with patch.object(a,'zip_binding',side_effect=changed),self.assertRaises(ValueError):self.run_binding()
        self.assertEqual('FAIL',a.seeds.read(self.output/'receipt.json')['status'])

    def test_failed_job_or_input_overlap_never_receives_binding_credit(self):
        path='actions/runs/100/attempts/2/jobs?per_page=100&page=1';self.api[path]['jobs'][1]['conclusion']='failure'
        with patch.object(a,'zip_binding') as binding,self.assertRaises(ValueError):self.run_binding()
        binding.assert_not_called();self.assertFalse((self.output/'artifacts-before').exists())
        with patch.object(a,'github') as get,self.assertRaisesRegex(ValueError,'overlaps'):
            a.bind(self.index,self.zips,self.bundles,self.bundles/'bad',get)
        get.assert_not_called()

    def test_retained_api_observations_cannot_change_while_bytes_are_bound(self):
        real=a.zip_binding;calls=0
        def changed(*args):
            nonlocal calls
            value=real(*args);calls+=1
            if calls==4:(self.output/'artifacts-before/maximum-native/page-1.json').write_bytes(b'{}')
            return value
        with patch.object(a,'zip_binding',side_effect=changed),self.assertRaisesRegex(ValueError,'retained observations changed'):
            self.run_binding()
        self.assertFalse(a.seeds.read(self.output/'receipt.json')['artifactBytesBound'])

    def test_incomplete_observer_result_is_not_promoted_to_attested_bytes(self):
        with patch.object(a.workflows,'collect',return_value={'status':'FAIL'}),patch.object(a,'zip_binding') as binding:
            with self.assertRaisesRegex(ValueError,'workflow prerequisite'):self.run_binding()
            binding.assert_not_called()

    def test_metadata_client_is_get_only_and_never_follows_an_api_supplied_url(self):
        with patch.object(a.subprocess,'run',return_value=type('R',(),dict(returncode=0,stdout=b'{}'))()) as call:
            self.assertEqual(b'{}',a.github('actions/runs/100/artifacts?per_page=100&page=1'))
            cmd=call.call_args.args[0];self.assertEqual('GET',cmd[cmd.index('--method')+1]);self.assertEqual('gh',cmd[0])
            self.assertEqual('repos/'+a.w.REPOSITORY+'/actions/runs/100/artifacts?per_page=100&page=1',cmd[-1])
        with patch.object(a.subprocess,'run') as call:
            for path in ('actions/runs/100/rerun','actions/artifacts/1/zip','https://hostile.example/secret'):
                with self.assertRaises(ValueError):a.github(path)
            call.assert_not_called()


if __name__=='__main__':unittest.main()

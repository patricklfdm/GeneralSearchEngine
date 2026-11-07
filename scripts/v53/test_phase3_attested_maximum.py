"""Complete-cohort orchestration with real maximum seed/API/archive readers.

History/resource JVM readers and native maximum child executions are synthetic.
These tests exercise admission and failure propagation, not hosted qualification.
"""
from contextlib import ExitStack,redirect_stdout
import copy
import io
import unittest
from unittest.mock import patch
from . import phase3_attested_cohort as c
from . import test_maximum_resource_attested as maximum_fixture


class Phase3AttestedMaximumTest(unittest.TestCase):
    def setUp(self):
        self.fixture=maximum_fixture.MaximumAttestedTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.sha=self.fixture.value['source'];self.calls=[];self.counter=0
        self.common={k:c.seeds.read(self.fixture.data['maximum-native']/'seed.json')[k] for k in c.seeds.COMMON_PINS}
        self.index=self.root/'history-index.json';c.h.save(self.index,{'schema':'synthetic-history-index','source':self.sha})
        self.history_error=None;self.resource_error=None;self.history_change=None
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for module,name,implementation in ((c.workflows,'collect',self.observe),(c.resource_workflows,'collect',self.observe),
                (c.resource_artifacts,'bind',self.bind),(c.resources,'inspect',self.inspect),
                (c.histories,'run',self.histories),(c.resources,'run',self.resources)):
            self.stack.enter_context(patch.object(module,name,side_effect=implementation))
        for module,name in ((c,'unchanged_originals'),(c.resources,'unchanged'),(c.resource_artifacts,'unchanged')):
            self.stack.enter_context(patch.object(module,name))

    def observe(self,index,output,get):
        output.mkdir();self.calls.append(output.name)
        value=dict(status='PARTIAL',workflowExecutionAttested=True,source=self.sha,
            indexSha256=c.h.digest(self.index.read_bytes()) if index==self.index else 'e'*64,
            contractsSha256='1'*64,observationsSha256='2'*64,selectedJobs=544 if index==self.index else 15,
            priorAttempts=0,priorAttemptsRequireReview=False,cohorts={})
        c.h.save(output/'receipt.json',value);return value

    def inspect(self,*args):
        return dict(source=self.sha,indexSha256='f'*64,commonPins={k:self.common[k] for k in c.resources.COMMON_PINS})

    def bind(self,index,resource_index,inputs,bundles,output):
        output.mkdir();value=dict(status='PARTIAL',resourceArtifactsBound=True,phase3Complete=False,source=self.sha,
            executionIndexSha256='e'*64,resourceIndexSha256='f'*64,commonPins=copy.deepcopy(self.common))
        c.h.save(output/'receipt.json',value);return value

    def histories(self,index,seeds,inputs,output,*,expected_common):
        self.assertEqual([],self.fixture.calls);self.assertEqual(self.common,expected_common)
        self.assertTrue((output.parent/'maximum/binding-before/receipt.json').is_file())
        self.calls.append('histories');output.mkdir()
        if self.history_error:raise ValueError(self.history_error)
        (output/'seeds').mkdir();c.h.save(output/'seeds/receipt.json',dict(commonPins=copy.deepcopy(expected_common)))
        value=dict(status='PARTIAL',source=self.sha,indexSha256=c.h.digest(self.index.read_bytes()),
            allDeclaredHistoriesReplayed=True,workflowExecutionAttested=False,phase3Complete=False,runtimeQualified=False,
            combinedPeakResourcesQualified=False,frozenScenarioCoverageQualified=False,
            historiesReplayed=566,groupsReplayed=260,rawArchives=500,candidateWitnesses={'synthetic':True})
        c.h.save(output/'receipt.json',value)
        if self.history_change:self.history_change()
        return value

    def resources(self,index,inputs,output,*,expected_common):
        self.assertEqual([],self.fixture.calls);self.assertEqual(self.common,expected_common)
        self.calls.append('resources');output.mkdir()
        if self.resource_error:raise ValueError(self.resource_error)
        value=dict(status='PARTIAL',source=self.sha,indexSha256='f'*64,allSupplementalOriginalsReplayed=True,
            phase3Complete=False,combinedPeakResourcesQualified=False,resourceWorkflowExecutionAttested=False,
            historicalCapacityPrefixQualified=False)
        c.h.save(output/'receipt.json',value);return value

    def arguments(self):
        return dict(resource_index=self.root/'resource-index.json',resource_inputs=self.root/'resources',
            resource_execution_index=self.root/'resource-workflows.json',resource_bundles=self.root/'resource-bundles',
            maximum_index=self.fixture.index,maximum_zips=self.fixture.zips,maximum_bundles=self.fixture.bundles)

    def run_gate(self):
        self.counter+=1;self.output=self.root/('cohort-'+str(self.counter));self.fixture.output=self.output/'maximum'
        with redirect_stdout(io.StringIO()):
            return c.run(self.index,self.root/'seeds',self.root/'raw',self.output,self.fixture.fixture.get,**self.arguments())

    def test_complete_entry_runs_all_prerequisites_and_maxima_with_same_preparation(self):
        result=self.run_gate()
        self.assertEqual('gse-v53-phase3-attested-cohort-v4',result['schema']);self.assertEqual('PARTIAL',result['status'])
        self.assertEqual(['workflow-before','resource-workflow-before','histories','resources',
                          'workflow-after','resource-workflow-after'],self.calls)
        self.assertEqual(['maximum-native','maximum-queue'],self.fixture.calls)
        self.assertTrue(result['maximumComponentOriginalsReplayed']);self.assertTrue(result['maximumArtifactsBound'])
        self.assertTrue(result['maximumWorkflowExecutionAttested']);self.assertEqual(2,result['maximumHistories'])
        self.assertEqual((544,15,6),tuple(result[k] for k in ('selectedJobs','supplementalJobs','maximumJobs')))
        self.assertEqual(2,result['maximumPriorAttempts']);self.assertTrue(result['priorAttemptsRequireReview'])
        for key in ('combinedPeakResourcesQualified','frozenScenarioCoverageQualified','runtimeQualified','failedOriginalsReplayed','phase3Complete'):
            self.assertFalse(result[key])
        self.assertEqual(c.seeds.shared.tc.file_hash(self.output/'maximum/receipt.json'),result['receipts']['maximum'])

    def test_omitted_maximum_inputs_do_not_start_old_cohort(self):
        for key in ('maximum_index','maximum_zips','maximum_bundles'):
            args=self.arguments();args.pop(key)
            with self.subTest(key=key),self.assertRaises(TypeError):
                c.run(self.index,self.root/'seeds',self.root/'raw',self.root/'missing',**args)
        self.assertEqual([],self.calls);self.assertFalse((self.root/'missing').exists())

    def test_unqualified_host_stops_before_collection_or_hashing_originals(self):
        with patch.object(c.maximum,'capacity',side_effect=ValueError('native Linux required')), \
                patch.object(c.resources,'inspect') as inspect,self.assertRaisesRegex(ValueError,'native Linux required'):
            self.run_gate()
        inspect.assert_not_called();self.assertEqual([],self.calls);self.assertEqual([],self.fixture.fixture.calls)
        self.assertEqual('FAIL',c.seeds.read(self.output/'receipt.json')['status'])

    def test_missing_maximum_archive_stops_before_any_physical_reader(self):
        (self.fixture.bundles/'maximum-queue/raw/bundle.tar.gz').unlink()
        with self.assertRaises(ValueError):self.run_gate()
        self.assertNotIn('histories',self.calls);self.assertEqual([],self.fixture.calls)
        self.assertEqual('FAIL',c.seeds.read(self.output/'receipt.json')['status'])

    def test_mixed_supplemental_dependencies_fail_before_any_history(self):
        self.common['repositorySha256']='0'*64
        with self.assertRaisesRegex(ValueError,'differs from cohort'):self.run_gate()
        self.assertNotIn('histories',self.calls);self.assertEqual([],self.fixture.calls)

    def test_maximum_source_mismatch_stops_before_external_maximum_collection(self):
        value=copy.deepcopy(self.fixture.value);value['source']='b'*40
        for row in value['cohorts'].values():row['source']=value['source']
        c.h.save(self.fixture.index,value)
        with self.assertRaisesRegex(ValueError,'maximum source'):self.run_gate()
        self.assertEqual([],self.fixture.fixture.calls);self.assertNotIn('histories',self.calls)

    def test_prerequisite_failure_keeps_primary_error_and_prevents_maximum_readers(self):
        for field in ('history_error','resource_error'):
            setattr(self,field,'rejected original')
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'rejected original'):self.run_gate()
            value=c.seeds.read(self.output/'receipt.json');self.assertEqual('FAIL',value['status'])
            self.assertEqual('rejected original',value['failure']['message'])
            self.assertEqual([],self.fixture.calls);self.assertFalse(value['maximumComponentOriginalsReplayed'])
            self.assertTrue((self.output/'maximum/binding-before/receipt.json').is_file())
            self.assertFalse((self.output/'maximum/replay').exists())
            setattr(self,field,None)

    def test_maximum_attempt_change_during_old_histories_rejects_whole_cohort(self):
        self.history_change=lambda:self.fixture.fixture.api['actions/runs/100'].update(run_attempt=3)
        with self.assertRaisesRegex(ValueError,'exact context'):self.run_gate()
        self.assertEqual(['maximum-native','maximum-queue'],self.fixture.calls)
        self.assertTrue((self.output/'resources/receipt.json').is_file())
        self.assertFalse(c.seeds.read(self.output/'receipt.json')['maximumComponentOriginalsReplayed'])

    def test_maximum_original_failure_does_not_accept_preceding_readers(self):
        def failed(*args):raise ValueError('native original rejected')
        with patch.object(self.fixture.modules['maximum-native'],'verify',side_effect=failed), \
                self.assertRaisesRegex(ValueError,'native original rejected'):self.run_gate()
        self.assertTrue((self.output/'histories/receipt.json').is_file())
        self.assertFalse((self.output/'workflow-after').exists())
        value=c.seeds.read(self.output/'receipt.json');self.assertEqual('FAIL',value['status'])
        self.assertFalse(value['allDeclaredHistoriesReplayed']);self.assertFalse(value['phase3Complete'])


if __name__=='__main__':unittest.main()

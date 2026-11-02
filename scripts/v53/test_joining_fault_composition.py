"""Conditional replay/metadata fixtures, never a native fault cohort claim."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import joining_fault_cohort as m
from . import test_joining_fault_matrix as fixtures
from . import test_joining_source_loss as traces
from . import test_profile_matrix as profiles


class FaultCompositionTest(unittest.TestCase):
    def test_complete_original_uses_ballot_chain_before_fault_trace(self):
        order=[]
        def original(*args):order.append('complete');return dict(scope='complete')
        def inputs(*args):order.append('fault');return traces.trace()
        with patch.object(m.gate.n.s.collection,'inventory',return_value={}),patch.object(m.gate.ballots,'validate',side_effect=original),\
             patch.object(m.gate,'inputs',side_effect=inputs),patch.object(m.gate.peer,'validate') as legacy:
            result=m.gate.validate('/unused',full_chain=True)
        self.assertEqual(['complete','fault'],order);legacy.assert_not_called()
        self.assertTrue(result['fullImplementedCompositionQualified']);self.assertEqual(dict(scope='complete'),result['ballotPrecondition'])
        self.assertNotIn('peerLedgerPrecondition',result)

    def test_bad_original_stops_both_negative_families(self):
        with patch.object(m.gate,'validate',side_effect=ValueError('invalid original')) as original,\
             patch.object(m.gate,'mutate') as fault,patch.object(m.gate.ballots,'qualify') as ballot:
            with self.assertRaisesRegex(ValueError,'invalid original'):m.gate.qualify('/unused',full_chain=True)
        original.assert_called_once_with(Path('/unused'),full_chain=True);fault.assert_not_called();ballot.assert_not_called()

    def test_fault_negatives_and_ballots_both_run_after_complete_original(self):
        original=dict(ballotPrecondition=dict(original='valid'));order=[]
        def validate(*args,**kwargs):order.append('original');return original
        def ballot(*args,**kwargs):order.append('ballot');return dict(original=original['ballotPrecondition'])
        with patch.object(m.gate,'validate',side_effect=validate),patch.object(m.gate.n.s.collection,'inventory',return_value={}),\
             patch.object(m.gate,'inputs',return_value=traces.trace()),patch.object(m.gate.ballots,'qualify',side_effect=ballot) as replay:
            result=m.gate.qualify('/unused',full_chain=True)
        self.assertEqual(['original','ballot'],order);self.assertEqual(14,len(result['negatives']));self.assertTrue(result['originalPreserved'])
        self.assertEqual('3-ADD',replay.call_args.args[1]);self.assertEqual(1,replay.call_args.kwargs['workers'])

    def test_changed_ballot_result_or_original_during_second_replay_refuses(self):
        for changed in ('result','files'):
            with self.subTest(changed=changed),patch.object(m.gate,'validate',return_value=dict(ballotPrecondition=dict(value='original'))),\
                 patch.object(m.gate.n.s.collection,'inventory',side_effect=[{}, {}, {'changed':True} if changed=='files' else {}]),\
                 patch.object(m.gate,'inputs',return_value=traces.trace()),patch.object(m.gate.ballots,'qualify',return_value=dict(original=dict(value='different' if changed=='result' else 'original'))):
                with self.assertRaisesRegex(ValueError,'composition changed original result|composed negatives changed original'):
                    m.gate.qualify('/unused',full_chain=True)

    def test_composition_mode_cannot_be_inferred_or_truthy_string(self):
        for mode in ('true',1,None):
            with patch.object(m.gate,'inputs') as inputs,self.assertRaisesRegex(ValueError,'explicit composition mode'):
                m.gate.qualify('/unused',full_chain=mode)
            inputs.assert_not_called()


class JoiningFaultCohortTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.JoiningFaultMatrixTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.paths=self.fixture.paths;self.root=self.fixture.root
        self.reader=dict(sha256='f'*64,files={'original.java':m.h.digest(b'original source')})
        for path in self.paths.values():m.h.save(path/'execution.json',dict(exit=0))
        first=self.paths[m.KINDS[0]]
        self.pins=[self.fixture.source,self.fixture.build,m.h.digest((first/'toolchain.json').read_bytes()),self.reader['sha256']]
        for replacement in (patch.object(m,'reader_manifest',return_value=self.reader),
                            patch.object(m.h,'collection',side_effect=lambda raw:m.legacy.read(raw.parents[4]/'collection.json'))):
            replacement.start();self.addCleanup(replacement.stop)

    @staticmethod
    def replay(raw,*,full_chain):
        kind=raw.parents[4].name;ballot=profiles.ProfileMatrixTest.result('3-ADD')
        return dict(original=dict(status='PASS',sourceFault=kind,joiningSourceFaultQualified=True,fullImplementedCompositionQualified=True,
            lostReplies=1,recoveredLostReplies=1,phase3Complete=False,processDeathQualified=False,ballotPrecondition=ballot['original']),
            originalPreserved=True,negatives=[dict(case=k,status='REJECTED',reason=v) for k,v in m.gate.NEGATIVES.items()],ballotQualification=ballot)

    def member(self,kind='SOURCE_OFFER'):return m.member(self.paths[kind],kind,*self.pins)

    def matrix(self,paths=None,workers=2):
        with patch('concurrent.futures.ProcessPoolExecutor',ThreadPoolExecutor):
            return m.validate(self.paths if paths is None else paths,*self.pins,workers=workers)

    def test_complete_three_synthetic_histories_keep_both_negative_families_and_scope(self):
        with patch.object(m.gate,'qualify',side_effect=self.replay) as replay:result=self.matrix()
        self.assertEqual(3,replay.call_count);self.assertTrue(all(v.kwargs['full_chain'] is True for v in replay.call_args_list))
        self.assertEqual('PASS',result['status']);self.assertEqual(42,result['faultNegativeCases']);self.assertEqual(63,result['ballotNegativeCases'])
        self.assertEqual(6,result['notApplicable']);self.assertEqual(list(m.KINDS),[v['case'] for v in result['cases']])
        for key in ('phase3Complete','processDeathQualified','allMembershipProfilesQualified','originalObservationCoverageComplete'):self.assertFalse(result[key])

    def test_missing_extra_aliased_and_duplicate_originals_refuse_before_replay(self):
        for paths in ({k:v for k,v in self.paths.items() if k!='CHUNK'},dict(self.paths,extra=self.root),dict(self.paths,CHUNK=self.paths['SOURCE_OFFER'])):
            with patch.object(m.gate,'qualify') as replay,self.assertRaises(ValueError):self.matrix(paths)
            replay.assert_not_called()
        a=self.paths['SOURCE_OFFER'];b=self.paths['CHUNK'];ra=a/m.legacy.read(a/'receipt.json')['raw'];rb=b/m.legacy.read(b/'receipt.json')['raw']
        (rb/'original-plan.gsbp').write_bytes((ra/'original-plan.gsbp').read_bytes())
        value=m.legacy.read(b/'collection.json');value['inventory']=m.h.inventory(rb);m.h.save(b/'collection.json',value)
        self.fixture.receipt('CHUNK',collectionSha256=m.h.digest((b/'collection.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'distinct original histories'):self.matrix()

    def test_old_reader_sources_mismatched_tools_and_unrecollected_bytes_refuse(self):
        self.reader['files']['new-reader.py']='d'*64
        with self.assertRaisesRegex(ValueError,'readers belong to producer source'):self.member()
        del self.reader['files']['new-reader.py']
        self.pins[2]='e'*64
        with self.assertRaisesRegex(ValueError,'exact toolchain'):self.member()
        self.pins[2]=m.h.digest((self.paths['SOURCE_OFFER']/'toolchain.json').read_bytes())
        with patch.object(m.h,'collection',return_value={'different':True}),self.assertRaisesRegex(ValueError,'independently recollected original'):self.member()

    def test_execution_and_junit_retry_fields_are_not_trusted(self):
        path=self.paths['SOURCE_OFFER'];m.h.save(path/'execution.json',dict(exit=0,changed=True))
        with self.assertRaisesRegex(ValueError,'original execution receipt'):self.member()
        m.h.save(path/'execution.json',dict(exit=0));report=path/'workspace'/m.h.MODULE/'target/surefire-reports/TEST-fixture.xml'
        tree=ET.parse(report);ET.SubElement(tree.getroot()[0],'flakyFailure');tree.write(report)
        with self.assertRaisesRegex(ValueError,'unretried JUnit'):self.member()

    def test_full_chain_mixed_original_or_negative_result_cannot_pass(self):
        raw=self.paths['SOURCE_OFFER']/m.legacy.read(self.paths['SOURCE_OFFER']/'receipt.json')['raw']
        mutations=[lambda v:v['original'].pop('fullImplementedCompositionQualified'),lambda v:v['original'].update(lostReplies=True),
                   lambda v:v['original'].update(ballotPrecondition={}),lambda v:v['negatives'].pop(),
                   lambda v:v['ballotQualification']['negatives'][0].update(reason='unrelated failure'),
                   lambda v:v['ballotQualification']['original'].update(phase3Complete=True)]
        for change in mutations:
            result=self.replay(raw,full_chain=True);change(result)
            with self.assertRaises(ValueError):m.check_result(result,'SOURCE_OFFER')

    def test_failures_are_retained_and_other_members_finish(self):
        def fail(raw,**kwargs):
            if raw.parents[4].name=='CHUNK':raise ValueError('original failed')
            return self.replay(raw,**kwargs)
        with patch.object(m.gate,'qualify',side_effect=fail):result=self.matrix()
        self.assertEqual('FAIL',result['status']);self.assertFalse(result['joiningSourceFaultCompositionQualified'])
        self.assertEqual(2,sum(v['status']=='PASS' for v in result['cases']))

    def test_reader_changes_after_replay_and_later_members_changing_prior_receipts_refuse(self):
        def drift(raw,**kwargs):
            result=self.replay(raw,**kwargs);self.reader['sha256']='d'*64;return result
        path=self.paths['SOURCE_OFFER']
        with patch.object(m.gate,'qualify',side_effect=drift),self.assertRaisesRegex(ValueError,'pinned reader'):
            m.qualify_member(path,'SOURCE_OFFER',*self.pins)
        self.reader['sha256']='f'*64
        def later(raw,**kwargs):
            result=self.replay(raw,**kwargs)
            if raw.parents[4].name==m.KINDS[-1]:self.fixture.receipt(note='modified by later member')
            return result
        with patch.object(m.gate,'qualify',side_effect=later),self.assertRaisesRegex(ValueError,'producer changed before completion'):self.matrix(workers=1)

    def test_hash_types_declared_member_and_workers_are_bounded(self):
        for i in range(4):
            changed=list(self.pins);changed[i]='master'
            with self.assertRaisesRegex(ValueError,'pinned hashes'):m.check_pins(*changed)
        with self.assertRaisesRegex(ValueError,'declared reply'):m.member(self.paths['SOURCE_OFFER'],'UNKNOWN',*self.pins)
        for workers in (0,4,True,1.5):
            with self.assertRaisesRegex(ValueError,'replay workers'):self.matrix(workers=workers)

    def test_cli_retains_failed_receipt_and_exclusive_output(self):
        output=self.root/'cli';args=['cohort','member',str(output),'--producer',str(self.paths['SOURCE_OFFER']),'--case','SOURCE_OFFER']
        for name,value in zip(('source','build','toolchain','reader'),self.pins):args+=['--'+name+'-sha256',value]
        self.fixture.receipt(status='FAIL')
        with patch('sys.argv',args),self.assertRaisesRegex(ValueError,'successful whole member'):m.main()
        self.assertEqual('FAIL',m.legacy.read(output/'receipt.json')['status'])
        with patch('sys.argv',args),self.assertRaises(FileExistsError):m.main()


class FaultPortableCollectorTest(unittest.TestCase):
    def test_portable_option_retains_tool_diagnostics_and_never_retries_native_failure(self):
        from . import process_toolchain
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'run'
            def source(repo,work):work.mkdir();return dict(head='a'*40,files={})
            tools=dict(exit=0,synthetic='portable tools')
            with patch.object(m.h,'source_copy',side_effect=source),patch.object(process_toolchain,'capture',return_value=tools) as capture,\
                 patch.object(m.h,'execute',return_value=dict(exit=1)) as run,redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'whole joining Maven failed'):m.h.run(output,'mvn',fault='CHUNK',portable_toolchain=True)
            run.assert_called_once();capture.assert_called_once();receipt=m.legacy.read(output/'receipt.json')
            self.assertEqual('FAIL',receipt['status']);self.assertEqual(0,receipt['retries'])
            self.assertEqual(m.h.digest((output/'toolchain.json').read_bytes()),receipt['toolchainSha256'])

    def test_nonboolean_portable_option_refuses_before_execution(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(m.h,'execute') as run:
            for flag in (1,None,'true'):
                with self.assertRaisesRegex(ValueError,'portable toolchain option'):m.h.run(Path(temp)/'run','mvn',portable_toolchain=flag)
            self.assertFalse((Path(temp)/'run').exists());run.assert_not_called()


if __name__=='__main__':unittest.main()

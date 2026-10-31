"""Conditional boundary tests; native history and physical replay are separate."""
import copy
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from . import joining_same_view_semantics as e
from . import joining_profile_run as runner
from .test_joining_retention_evidence import Inputs
from . import test_joining_profile_run as prefix_tests


class JoiningSameViewSemanticsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def fixture(self):
        v=Inputs(3,True);root=v.cap['root'];targets=v.view['new']
        joint=dict(index=9,entry='9'*64,view=v.view)
        stable=dict(generation=1,old=targets,new=targets,operation=None)
        final=dict(index=10,entry='a'*64,view=stable);barrier=dict(index=11,entry='b'*64,view=stable)
        states=[None]*12
        for index,cut in ((9,joint),(10,final),(11,barrier)):states[index]=dict(cut=cut,identities=v.identities)
        replay=SimpleNamespace(states=states,joining=v.joining['node'],root=root,root_bytes=b'original-root',targets=targets,packet=Mock())
        self.prefix=dict(before=joint,after=final,adopted=True,installed=False,publicReady=False)
        self.recovery=dict(before=final,after=barrier,adopted=False,installed=True,publicReady=False)
        (self.root/'joining-final-prefix.json').write_bytes(e.f.canonical(self.prefix))
        (self.root/'joining-final-recovery.json').write_bytes(e.f.canonical(self.recovery))
        ballot=dict(counter=8,proposer=v.joining['node'],incarnation=v.joining['storage'])
        sources=[dict(voter=node,basisId=v.identities[i]['storage'],basisDigest=str(i+1)*64) for i,node in enumerate(('node-1','node-4'))]
        selected=dict(root=root,view=e.c.catalog.authority(root,stable),ballot=ballot,cut=barrier,nextEntry=None,sources=sources)
        raw=e.f.encode('records','SELECTED',selected);(self.root/'joining-final-recovery-selection.gsr').write_bytes(raw)
        originals={}
        for label,index in (('joining-before-final-prefix',9),('joining-after-final-prefix',10),
                            ('joining-before-final-recovery',10),('joining-after-final-recovery',11)):
            originals[label]={'root.gsr':replay.root_bytes,
                'node.gsr':e.f.encode('records','NODE',dict(root=root,identity=v.joining)),
                'allocator.gsr':e.f.encode('records','ALLOCATOR',dict(root=root,node=v.joining['node'],counter=7)),
                'grants.gsr':b'', 'test-cut':states[index]['cut'],'test-selection':raw}
        stack=ExitStack();self.addCleanup(stack.close)
        stack.enter_context(patch.object(e.c.joining,'read',side_effect=lambda path:SimpleNamespace(root=path)))
        stack.enter_context(patch.object(e.disk,'inventory',side_effect=lambda path:originals[path.parent.name]))
        stack.enter_context(patch.object(e.disk,'current',side_effect=lambda files:(None,{'selected.gsr':files['test-selection']},
                                                              {'capsule':{'cut':files['test-cut']}})))
        return replay,originals

    def test_real_encoded_boundaries_require_fresh_local_ballot_and_installation(self):
        replay,_=self.fixture();result=e.boundaries(self.root,replay)
        self.assertEqual((10,11,'node-4'),(result['fromCut'],result['toCut'],result['proposer']))
        self.assertTrue(result['adoptedAtFinal']);self.assertTrue(result['installedAtBarrier']);self.assertFalse(result['publicReady'])
        self.assertEqual([9,10,10,11],[call.args[1] for call in replay.packet.call_args_list])

    def test_semantic_negative_receipts_and_selections_reject_exactly(self):
        replay,_=self.fixture()
        paths=list(self.root.iterdir());originals={p:p.read_bytes() for p in paths}
        for name,reason in e.EXTRA_NEGATIVES.items():
            with self.subTest(name=name):
                e.boundaries(self.root,replay);e.mutate(self.root,name)
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):e.boundaries(self.root,replay)
                for p,raw in originals.items():p.write_bytes(raw)

    def test_snapshot_cut_and_permanent_owner_cannot_be_replaced_by_receipt(self):
        replay,originals=self.fixture();files=originals['joining-before-final-recovery'];before=copy.deepcopy(files)
        for key,value in (('test-cut',replay.states[9]['cut']),('root.gsr',b'foreign-root'),
                          ('node.gsr',e.f.encode('records','NODE',dict(root=replay.root,identity=Inputs(3,True).identities[0])))):
            files[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'^joining same-view original boundary$'):
                e.boundaries(self.root,replay)
            files.clear();files.update(before)

    def test_persisted_fence_requires_a_new_ballot_even_if_allocator_lags(self):
        replay,originals=self.fixture();files=originals['joining-before-final-recovery']
        selected=e.f.decode((self.root/'joining-final-recovery-selection.gsr').read_bytes(),'records','SELECTED')
        files['grants.gsr']=e.f.encode('records','PROMISE',dict(root=replay.root,view=selected['view'],
            ballot=selected['ballot'],basisId=None))
        with self.assertRaisesRegex(ValueError,'^joining same-view original selection$'):e.boundaries(self.root,replay)

    def test_selection_bytes_must_be_the_installed_original(self):
        replay,originals=self.fixture();originals['joining-after-final-recovery']['test-selection']=b'foreign-selection'
        with self.assertRaisesRegex(ValueError,'^joining same-view installed selection$'):e.boundaries(self.root,replay)

    def test_invalid_original_and_unrelated_mutation_failure_cannot_qualify(self):
        for results,reason in (([ValueError('bad original')],'^bad original$'),
                               ([{},ValueError('unrelated')],'^joining same-view unrelated negative:')):
            with patch.object(e,'validate',side_effect=results),patch.object(e.c.collection,'inventory',return_value={}), \
                 patch.object(e,'mutate'),patch.object(e.shutil,'copytree') as copying:
                with self.assertRaisesRegex(ValueError,reason):e.qualify(self.root,e.PROFILE)
                if len(results)==1:copying.assert_not_called()

    def test_other_profiles_refuse_before_reading_originals(self):
        for profile in ('3-ADD','4-REPLACE','5-REPLACE',None):
            with patch.object(e.complete,'validate') as original,self.assertRaisesRegex(ValueError,'^joining same-view declared profile$'):
                e.validate(self.root,profile)
            original.assert_not_called()

    def test_semantic_success_does_not_qualify_physical_storage_or_phase3(self):
        replay,_=self.fixture();replay.step=Mock()
        original=dict(status='PASS',completePhysicalQualified=False,phase3Complete=False,finalAndColdReopenQualified=False)
        with patch.object(e.complete,'validate',return_value=original),patch.object(e.c,'Replay',return_value=replay), \
             patch.object(e.c.collection,'inventory',return_value={}):
            result=e.validate(self.root,e.PROFILE)
        self.assertTrue(result['sameViewSemanticQualified'])
        for key in ('sameViewPhysicalQualified','completePhysicalQualified','phase3Complete','finalAndColdReopenQualified'):
            self.assertFalse(result[key])

    def test_same_view_runner_requires_its_exact_declared_case(self):
        for profile,complete in (('3-ADD',True),('4-REPLACE',True),('3-REPLACE',False)):
            with self.assertRaisesRegex(ValueError,'^same-view execution requires complete 3-REPLACE$'):
                runner.run(self.root/'out','mvn',profile,complete=complete,same_view=True)
        self.assertFalse((self.root/'out').exists())
        fixture=prefix_tests.JoiningProfileRunTest();fixture.setUp()
        try:
            for method in (runner.METHOD,runner.COMPLETE_METHOD):
                fixture.report(method=method)
                with self.assertRaisesRegex(ValueError,'^joining prefix exact passing test$'):
                    runner.junit(fixture.root,runner.SAME_VIEW_METHOD)
            fixture.report(method=runner.SAME_VIEW_METHOD)
            self.assertEqual(runner.SAME_VIEW_METHOD,runner.junit(fixture.root,runner.SAME_VIEW_METHOD)['method'])
        finally:fixture.doCleanups()

    def test_failed_same_view_execution_keeps_failure_without_retry_or_fallback(self):
        def source(repo,work):work.mkdir();return dict(head='a'*40,files={})
        output=self.root/'run'
        with patch.object(runner.h,'source_copy',side_effect=source),patch.object(runner.h,'execute',return_value=dict(exit=1)) as execute, \
             patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='toolchain',stderr='')),redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'^joining prefix Maven failed;'):
                runner.run(output,'mvn','3-REPLACE',complete=True,same_view=True)
        execute.assert_called_once();self.assertIn('#'+runner.SAME_VIEW_METHOD,' '.join(execute.call_args.args[0]))
        receipt=json.loads((output/'receipt.json').read_bytes())
        self.assertTrue(receipt['sameViewRecoveryRequested']);self.assertEqual('FAIL',receipt['status']);self.assertEqual(0,receipt['retries'])
        for key in ('sameViewSemanticQualified','sameViewPhysicalQualified','semanticFinalAndColdQualified','phase3Complete'):
            self.assertFalse(receipt[key])

    def test_runner_cannot_promote_an_ordinary_completion_or_physical_claim(self):
        original=dict(status='PASS',profile='3-REPLACE',phase3Complete=False,finalAndColdReopenQualified=False,
                      semanticFinalAndColdQualified=True,sameViewSemanticQualified=True,sameViewPhysicalQualified=False)
        for label,changes,accepted in (('good',{},True),('ordinary',{'sameViewSemanticQualified':False},False),
                                      ('promoted',{'sameViewPhysicalQualified':True},False),
                                      ('missing',{'sameViewPhysicalQualified':None},False)):
            with self.subTest(label=label):
                output=self.root/label
                def source(repo,work):
                    (work/runner.h.MODULE/'target/v53-native-dispatch/run-original').mkdir(parents=True)
                    return dict(head='a'*40,files={})
                def execute(command,work,path,**kwargs):
                    if path.name=='replay.json':
                        self.assertIn(e.__name__,command)
                        path.write_text(json.dumps(dict(original=dict(original,**changes),
                            negatives=[dict(case=k,status='REJECTED',reason=v) for k,v in e.NEGATIVES.items()])))
                    return dict(exit=0)
                with patch.object(runner.h,'source_copy',side_effect=source),patch.object(runner.h,'execute',side_effect=execute), \
                     patch.object(runner.h,'check_source'),patch.object(runner.h,'inventory',return_value={}), \
                     patch.object(runner,'junit',return_value={}), \
                     patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='toolchain',stderr='')),redirect_stdout(io.StringIO()):
                    if accepted:
                        result=runner.run(output,'mvn','3-REPLACE',complete=True,same_view=True)
                        self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['sameViewSemanticQualified'])
                    else:
                        with self.assertRaisesRegex(ValueError,'^joining same-view replay scope$'):
                            runner.run(output,'mvn','3-REPLACE',complete=True,same_view=True)
                        result=json.loads((output/'receipt.json').read_bytes())
                        self.assertEqual('FAIL',result['status']);self.assertFalse(result['sameViewSemanticQualified'])
                    self.assertFalse(result['sameViewPhysicalQualified']);self.assertFalse(result['phase3Complete'])


if __name__=='__main__':unittest.main()

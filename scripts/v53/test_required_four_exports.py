"""Conditional reader composition; no native required-four PASS is inferred."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import required_four_exports as e
from . import required_four_evidence as topology


class RequiredFourExportTest(unittest.TestCase):
    def test_explicit_topology_cannot_be_used_for_another_profile_or_nonboolean_flag(self):
        for profile,flag in (('3-ADD',True),('4-REPLACE',True),('5-REPLACE',1),('5-REPLACE','true')):
            with self.subTest(profile=profile,flag=flag),patch.object(e.exports.e.n.s,'Replay') as model:
                with self.assertRaisesRegex(ValueError,'required-four profile'):e.exports.context('/unused',profile,required_four=flag)
                model.assert_not_called()

    def test_context_keeps_all_six_owners_and_removes_node_three_only(self):
        steps=[]
        identities=[dict(node='node-'+str(i),storage=f'00000000-0000-0000-0000-{i:012d}',host='127.0.0.1',port=40000+i) for i in range(1,7)]
        model=SimpleNamespace(old=topology.OLD,targets=topology.NEW,joining='node-6',root='root',
                              states=[dict(identities=identities)],step=steps.append)
        with patch.object(e.exports.e.n.s,'Replay',return_value=model) as replay, \
             patch.object(e.collection,'read_json',return_value=[]),patch.object(e.exports.e.n,'causal',return_value=[]), \
             patch.object(e.exports.e.n,'transfers'),patch.object(e.exports.e,'generation_windows',return_value=[]) as windows, \
             patch.object(e.exports.e,'source_windows',return_value=[]),patch.object(e.exports.e,'record_windows',return_value=[]):
            actual=e.context('/unused');self.assertIs(actual.model,model)
            replay.assert_called_once_with(Path('/unused'),size=5,kind='REPLACE',required_four=True)
            self.assertEqual(list(range(1,12)),steps)
            self.assertEqual((*topology.OLD,'node-6'),windows.call_args.kwargs['nodes'])
            model.targets=['node-1','node-2','node-3','node-4','node-6']
            with self.assertRaisesRegex(ValueError,'required-four target'):e.context('/unused')

    def test_joint_retention_needs_all_three_available_remote_deliveries(self):
        view=dict(old=topology.OLD,new=topology.NEW,operation='joint')
        rows=[dict(request=dict(recipient=dict(node=node)),delivered=at) for node,at in
              (('node-2',10),('node-3',20),('node-6',30))]
        self.assertEqual(30,e.control.quorum_time(view,'node-1',rows,40))
        for omit in range(3):
            with self.assertRaisesRegex(ValueError,'original retention quorum'):
                e.control.quorum_time(view,'node-1',[row for i,row in enumerate(rows) if i!=omit],40)
        for at in (None,40):
            changed=copy.deepcopy(rows);changed[-1]['delivered']=at
            with self.assertRaisesRegex(ValueError,'original retention quorum'):
                e.control.quorum_time(view,'node-1',changed,40)

    def test_control_context_uses_required_four_and_original_intent_proofs(self):
        model=SimpleNamespace(kind='REPLACE',old=topology.OLD,phases=[{'CERTIFICATE':b'original'}]*9)
        context=SimpleNamespace(model=model,events=[])
        with patch.object(e.control.exports,'context',return_value=context) as source, \
             patch.object(e.control.c.n.phase,'blocks',return_value={}), \
             patch.object(e.control.f,'decode',return_value=dict(proofs=[dict(voter=node) for node in topology.OLD_LIVE])):
            reader=e.control_reader('/unused')
            source.assert_called_once_with('/unused','5-REPLACE',old_owner_lifetimes=None,required_four=True)
            self.assertEqual(set(topology.OLD_LIVE),reader.expected_confirmations)
            self.assertEqual(3,reader.expected_controls['retention'])

    def fixture(self):
        prior=dict(network=dict(committedTransfers=20,transferSessions=10,rejectedTransferAttempts=1))
        contents=dict(boundTransfers={'content':10},unqualifiedTransfers=10,
            boundSessions={'pending-joining-checkpoint':3,'other':2},unqualifiedSessionCount=4)
        controls=dict(observedCommittedContents=20,observedContentSessions=9)
        return prior,contents,controls

    def test_broken_physical_network_original_stops_before_authorization_and_copy(self):
        with patch.object(e.collection,'inventory',return_value={}),patch.object(e.network,'validate',side_effect=ValueError('original refused')), \
             patch.object(e,'content') as content,patch.object(e,'controls') as controls,patch.object(e.shutil,'copytree') as copied:
            for action in (e.validate,e.qualify):
                with self.assertRaisesRegex(ValueError,'^original refused$'):action('/unused')
            content.assert_not_called();controls.assert_not_called();copied.assert_not_called()

    def test_complete_accounting_and_actual_pending_readers_are_mandatory(self):
        prior,content,controls=self.fixture()
        e.coverage(content,prior['network'])
        for field in ('unqualifiedTransfers','unqualifiedSessionCount'):
            changed=copy.deepcopy(content);changed[field]+=1
            with self.assertRaisesRegex(ValueError,'complete session accounting'):e.coverage(changed,prior['network'])
        for count in (0,2,4):
            changed=copy.deepcopy(content);changed['boundSessions']['pending-joining-checkpoint']=count
            changed['unqualifiedSessionCount']+=3-count
            with self.assertRaisesRegex(ValueError,'original pending checkpoint readers'):e.coverage(changed,prior['network'])

    def test_composed_result_has_exact_scope_and_preserves_original(self):
        prior,content,controls=self.fixture()
        with patch.object(e.collection,'inventory',return_value={}),patch.object(e.network,'validate',return_value=prior), \
             patch.object(e,'content',return_value=content),patch.object(e,'controls',return_value=controls):
            result=e.validate('/unused');self.assertEqual(topology.PROFILE,result['profile'])
            self.assertTrue(result['temporalContentExportsQualified']);self.assertTrue(result['observedControlExportsQualified'])
            for flag in ('allExportFamiliesQualified','maintenanceAndPeerCompositionQualified','wholeRuntimeResourcesQualified',
                         'completePhysicalQualified','processDeathQualified','finalSourceCohortQualified','phase3Complete'):
                self.assertFalse(result[flag])
            for field in controls:
                controls[field]-=1
                with self.assertRaisesRegex(ValueError,'control complete transfer coverage'):e.validate('/unused')
                controls[field]+=1
            with patch.object(e.collection,'inventory',side_effect=[{},dict(changed=True)]):
                with self.assertRaisesRegex(ValueError,'export original changed'):e.validate('/unused')

    def test_existing_content_and_control_negatives_are_all_required(self):
        self.assertEqual(26,len(e.NEGATIVES))
        self.assertEqual(e.exports.NEGATIVES,{k.removeprefix('content/'):v for k,v in e.NEGATIVES.items() if k.startswith('content/')})
        self.assertEqual(e.control.NEGATIVES,{k.removeprefix('control/'):v for k,v in e.NEGATIVES.items() if k.startswith('control/')})
        self.assertIn('content/pending-after-retain',e.NEGATIVES)

    def test_negative_prerequisites_cannot_count_as_intended_rejection(self):
        for case in ('content/generation-alias','control/root-alias','control/completion-closed-owner'):
            with patch.object(e.network,'replay',side_effect=ValueError('network refused')),patch.object(e,'content') as content:
                with self.assertRaisesRegex(ValueError,'^network refused$'):e.rejection_stage('/unused',case)
                content.assert_not_called()
        with patch.object(e.network,'replay'),patch.object(e,'content',side_effect=ValueError('content refused')),patch.object(e,'controls') as controls:
            with self.assertRaisesRegex(ValueError,'^content refused$'):e.rejection_stage('/unused','control/root-alias')
            controls.assert_not_called()

    def test_shared_owner_lifetime_rejection_stays_in_the_content_layer(self):
        for case in ('content/pending-after-retain','control/completion-closed-owner'):
            with patch.object(e.network,'replay'),patch.object(e,'content',side_effect=ValueError('intended')) as content,patch.object(e,'controls') as controls:
                check=e.rejection_stage('/unused',case);content.assert_not_called()
                with self.assertRaisesRegex(ValueError,'^intended$'):check()
                controls.assert_not_called()

    def test_no_missing_mutation_or_physical_change_can_pass(self):
        original=dict(files={'authority':'original'},directories=[])
        for failure,changed,reason in ((StopIteration(),original,'missing export mutation target'),
                                      (None,dict(files={'authority':'substitute'},directories=[]),'negative changed physical inputs')):
            with patch.object(e,'validate',return_value={}),patch.object(e.collection,'inventory',side_effect=[original,changed]), \
                 patch.object(e.shutil,'copytree'),patch.object(e,'mutate',side_effect=failure),patch.object(e,'rejection_stage') as stage:
                with self.assertRaisesRegex(ValueError,reason):e.qualify('/unused')
                stage.assert_not_called()

    def test_accepted_or_unrelated_mutation_is_not_a_successful_negative(self):
        inventory=dict(files={},directories=[])
        for failure,reason in ((None,'mutation accepted'),(ValueError('unrelated'),'unrelated export negative')):
            def check():
                if failure:raise failure
            with patch.object(e,'validate',return_value={}),patch.object(e.collection,'inventory',return_value=inventory), \
                 patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e,'rejection_stage',return_value=check):
                with self.assertRaisesRegex(ValueError,reason):e.qualify('/unused')


if __name__=='__main__':unittest.main()

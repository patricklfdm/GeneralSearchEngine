import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_application_transient_prefixes as p
from . import native_carried_application_transient_plans as plans
from . import native_carried_application_protocol as protocol


class ApplicationTransientsTest(unittest.TestCase):
    def parts(self):
        names=[*p.FAMILIES,*p.prerequisite.prerequisite.FAMILIES,'application','old-end']
        values={name:[dict(life=2,eventIndex=at,node='node-1',point='POINT',files={'root.gsr':{'bytes':1,'sha256':'a'*64}})] for at,name in enumerate(names)}
        value=dict(values['old-end'][0],point='REPLAY_RESERVED');values['old-end']=[value];values['replay'].append(copy.deepcopy(value))
        return values

    def test_union_counts_equal_original_replay_once_without_changing_parts(self):
        parts=self.parts();before=copy.deepcopy(parts);rows,count=p.combine(parts)
        self.assertEqual(1,count);self.assertEqual(9,len(rows));self.assertEqual(parts,before)
        self.assertEqual(sorted((v['life'],v['eventIndex']) for v in rows),[(v['life'],v['eventIndex']) for v in rows])

    def test_conflicting_replay_or_wrong_family_or_third_observation_refuses(self):
        for case in ('files','node','point','family','third'):
            parts=self.parts()
            if case=='files':parts['replay'][-1]['files']={}
            elif case=='node':parts['replay'][-1]['node']='node-2'
            elif case=='point':parts['replay'][-1]['point']='REPLAY_BEFORE_RETURN'
            elif case=='family':parts['votes'].append(copy.deepcopy(parts['old-end'][0]))
            else:parts['replay'].append(copy.deepcopy(parts['replay'][-1]))
            with self.subTest(case=case),self.assertRaisesRegex(ValueError,'conflicting replay capture' if case in ('files','node','point') else 'unexpected callback overlap'):
                p.combine(parts)

    def test_missing_family_empty_family_or_missing_original_overlap_refuses(self):
        for case,reason in (('missing','complete union families'),('empty','nonempty union family'),('overlap','missing original replay overlap')):
            parts=self.parts()
            if case=='missing':parts.pop('application')
            elif case=='empty':parts['completion']=[]
            else:parts['replay'].pop()
            with self.subTest(case=case),self.assertRaisesRegex(ValueError,reason):p.combine(parts)

    def test_only_normal_recovery_completion_collection_is_admitted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'life-2').mkdir();rows=[dict(life=2)]
            with patch.object(p.completion.r,'lifetime',return_value={'capturedPrefixes':1}) as lifetime:
                result=p.replay_family(Path('/original'),root,'completion',rows)
            self.assertEqual(1,result['capturedPrefixes']);self.assertEqual(2,lifetime.call_args.args[2])
            (root/'life-1').mkdir()
            with self.assertRaisesRegex(ValueError,'exact recovery lifetime'):p.replay_family('/original',root,'completion',rows)
            (root/'life-1').rmdir()
            with self.assertRaisesRegex(ValueError,'original recovery rows'):p.replay_family('/original',root,'completion',[dict(life=1)])

    def test_unrelated_original_earns_no_new_capture_or_negative_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ('previous','transients'):(Path(temp)/name).mkdir()
            with patch.object(p.prerequisite,'validate',side_effect=ValueError('invalid original')),\
                 patch.object(p.model,'plans') as plan,patch.object(p,'replay') as replay:
                with self.assertRaisesRegex(ValueError,'invalid original'):p.qualify(temp)
            plan.assert_not_called();replay.assert_not_called()

    def test_projection_prerequisite_must_pass_before_any_expected_bytes(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(plans.maintenance.original,'validate',side_effect=ValueError('invalid original')),\
             patch.object(plans,'plans') as project:
            with self.assertRaisesRegex(ValueError,'invalid original'):plans.validate(temp)
        project.assert_not_called()

    def test_complete_callback_projection_still_cannot_claim_captured_bytes(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(plans.maintenance.original,'validate',return_value={}),\
             patch.object(plans,'plans',return_value=({'votes':[dict(life=1),dict(life=2)]},{})):
            value=plans.validate(temp)
        for field in ('capturedBytesQualified','fullTransientBytesQualified','wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'):self.assertFalse(value[field])

    def test_first_crash_completion_has_exact_interrupted_transaction_but_no_normal_return_credit(self):
        rows=[dict(node='node-1',event=event) for event in ('APPLY_VALIDATED','APPLY_PLAN_CREATED','APPLY_ACK_DIRECTORY_FORCED')]
        self.assertEqual([],protocol.completion_observed(rows))
        with self.assertRaisesRegex(ValueError,'incomplete transaction'):protocol.completion_observed(rows[:-1])
        rows.append(dict(node='node-1',event='APPLY_BEFORE_RETURN'))
        self.assertEqual(4,len(protocol.completion_observed(rows)))
        rows[-2]['node']='node-2'
        with self.assertRaisesRegex(ValueError,'outside transaction'):protocol.completion_observed(rows[:-1])

    def test_interrupted_vote_plan_gives_certificate_only_to_original_leader(self):
        before={node:{'pending.accept':b'old','ledger':b'before'} for node in ('node-1','node-2','node-3','node-4')}
        accepting=copy.deepcopy(before);maintained=copy.deepcopy(before)
        for v in maintained.values():v['ledger']=b'after maintenance'
        frames={'ACCEPT':b'accept','PROOF':b'proof','CERTIFICATE':b'certificate'};bound={}
        with patch.object(protocol.application,'maintain',return_value=maintained),\
             patch.object(protocol.p.data,'pending',return_value=(frames,())),\
             patch.object(protocol.forces.vote_files,'phase_bytes',side_effect=lambda frames,phase:frames[phase]),\
             patch.object(protocol.forces.vote_files,'transaction',side_effect=lambda state,raw,phase:[(phase,copy.deepcopy(state),raw)]),\
             patch.object(protocol.forces,'bind_votes',side_effect=lambda rows,node,plan,target:bound.update({node:plan})):
            protocol.interrupted_votes([],before,accepting,before,['node-1','node-2','node-3'],[])
        self.assertEqual(['ACCEPT','PROOF','CERTIFICATE'],[v[0] for v in bound['node-1']])
        self.assertEqual(['ACCEPT','PROOF'],[v[0] for v in bound['node-2']]);self.assertEqual([],bound['node-4'])
        self.assertEqual(b'before',bound['node-1'][0][1]['ledger']);self.assertEqual(b'after maintenance',bound['node-1'][1][1]['ledger'])
        self.assertEqual(b'proof',bound['node-1'][2][1]['pending.accept']);self.assertEqual(b'old',before['node-1']['pending.accept'])

    def test_declared_negative_inventory_includes_all_four_existing_families(self):
        self.assertEqual(116,len(p.NEGATIVES))
        self.assertEqual('application completion exact recovery lifetime',p.NEGATIVES['completion:missing-lifetime'])


if __name__=='__main__':unittest.main()

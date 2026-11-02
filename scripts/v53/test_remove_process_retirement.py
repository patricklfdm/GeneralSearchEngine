"""Original interrupted transaction, retained state and rejection isolation."""
from pathlib import Path
import unittest
from unittest.mock import patch

from . import remove_process_retirement as r
from . import test_remove_retirement_evidence as generation_fixture
from . import test_joining_retirement_replay as source_fixture


class RemoveProcessRetirementTest(unittest.TestCase):
    def test_generation_cut_selects_first_matching_prefix_and_finishes_only_that_transaction(self):
        fixture=generation_fixture.RemoveRetirementEvidenceTest()
        for total in (6,7):
            after,steps,_=fixture.generation(total)
            point='RETIREMENT_FILE_DELETED';first=next(i for i,v in enumerate(steps) if v[0]==point)
            expected_recovery=fixture.generation(total,recover=steps[first][1])
            with patch.object(r.old,'generation_plan',return_value=expected_recovery) as recover,patch.object(r.p,'source_interruption') as source:
                result,prefix,resumed,count=r.interrupted({},'node-1',{},point,after,steps,{})
            self.assertEqual(steps[first][1],recover.call_args.kwargs['recover'])
            self.assertEqual(after,result);self.assertEqual(steps[:first+1],prefix);self.assertEqual(0,count)
            self.assertEqual(r.old.physical(after),resumed[-1][1]);source.assert_not_called()

    def test_each_source_cut_finishes_the_original_source_without_replaying_completed_generation(self):
        files,identifier,current,coverage,_,kept=source_fixture.JoiningRetirementReplayTest().decision_inputs()
        generation_steps=[('RETIREMENT_BEFORE_RETURN',r.old.physical(files))]
        for point in r.p.run.POINTS:
            if point.startswith('RETIREMENT_'):continue
            with self.subTest(point=point),patch.object(r.c,'current',return_value=current):
                result,prefix,recovery,count=r.interrupted({},'node-1',{},point,files,generation_steps,coverage)
            self.assertEqual(1,count);self.assertEqual(generation_steps[0],prefix[0]);self.assertEqual(point,prefix[-1][0])
            self.assertEqual(kept,result['grants.gsr']);self.assertNotIn('sources/'+identifier,result)
            self.assertEqual(files['floor-copies/floor.gsr'],result['floor-copies/floor.gsr'])
            self.assertFalse(any(name.startswith('RETIREMENT_') for name,_ in recovery))
            self.assertEqual(r.old.physical(result),recovery[-1][1] if recovery else prefix[-1][1])

    def test_unknown_or_unreachable_cut_cannot_choose_a_different_transaction(self):
        with self.assertRaisesRegex(ValueError,'cut kind'):r.interrupted({},'node-1',{},'OTHER',{},[],{})
        with self.assertRaisesRegex(ValueError,'reachable original retirement cut'):
            r.interrupted({},'node-1',{},'RETIREMENT_NOT_CAPTURED',{},[('RETIREMENT_CREATED',{})],{})

    def test_reuse_removes_only_previous_floor_and_preserves_derived_recovered_state(self):
        files={'floor-copies':None,'floor-copies/floor.gsr':b'f','floor-copies/id/a.image':b'i',
               'floor-copies-other':b'keep','selector.gsr':b's','grants.gsr':b'compacted','peer-retention.gsr':b'continuous'}
        result=r.strip_floor(files)
        self.assertEqual({'floor-copies-other':b'keep','selector.gsr':b's','grants.gsr':b'compacted','peer-retention.gsr':b'continuous'},result)
        self.assertIn('floor-copies/floor.gsr',files)

    def test_possible_and_renewal_endpoints_require_exact_original_coverage(self):
        point=dict(cut=dict(index=1),root='a');renewal=dict(cut=dict(index=2),root='b')
        plan=dict(peers=[dict(possible=[point],renewals=[renewal])]);own=dict(packet={},members={})
        for available in ({1:point,2:renewal},{1:point},{1:dict(point,root='other'),2:renewal}):
            with patch.object(r.r.peer.peers,'decode',return_value=dict(plan=plan)),patch.object(r.r.peer.t.confirmation,'endpoints',return_value=available):
                if available=={1:point,2:renewal}:self.assertEqual(available,r.coverage({r.r.peer.FILE:b'original'},own))
                else:
                    with self.assertRaisesRegex(ValueError,'retained endpoint coverage'):r.coverage({r.r.peer.FILE:b'original'},own)

    def test_exact_callback_sequence_cannot_be_replaced_by_counts_or_claimed_authority(self):
        steps=[('RETIREMENT_CREATED',{}),('RETIREMENT_PROPOSAL_WRITTEN',{})]
        rows=[(i,dict(node='node-1',event=name)) for i,(name,_) in enumerate(steps)]
        r.compare_callbacks(rows,steps,'bad sequence')
        for changed in (list(reversed(rows)),rows[:-1],rows+[rows[-1]]):
            with self.assertRaisesRegex(ValueError,'^bad sequence$'):r.compare_callbacks(changed,steps,'bad sequence')
        changed=[rows[0],(1,dict(rows[1][1],claimedHash='a'*64))]
        with self.assertRaisesRegex(ValueError,'callback shape'):r.compare_callbacks(changed,steps,'bad sequence')

    def test_capacity_is_checked_at_every_intermediate_state(self):
        six={str(i)+'.image':dict(bytes=1,sha256='a'*64) for i in range(6)}
        eight=dict(six,**{'six.image':dict(bytes=1),'seven.image':dict(bytes=1)})
        self.assertEqual(6,r.capacity([('start',six),('end',{})]))
        with self.assertRaisesRegex(ValueError,'unchanged physical capacity'):r.capacity([('start',six),('middle',eight),('end',{})])

    def test_failed_original_retention_prevents_transaction_claim(self):
        with patch.object(r.p.run.h,'inventory',return_value={}),patch.object(r.r,'validate',side_effect=ValueError('bad retention')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^bad retention$'):r.validate('/original')
        replay.assert_not_called()

    def test_changed_original_cannot_complete_composition(self):
        with patch.object(r.p.run.h,'inventory',side_effect=[{},dict(changed=True)]),patch.object(r.r,'validate'),\
             patch.object(r.p,'profile_at',return_value={}),patch.object(r,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):r.validate('/original')

    def test_original_failure_and_worker_bound_prevent_negative_submission(self):
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^bad original$'):r.qualify('/original')
        pool.assert_not_called()
        for workers in (0,5,True,1.1):
            with patch.object(r,'validate') as validate,self.assertRaisesRegex(ValueError,'replay workers'):r.qualify('/original',workers=workers)
            validate.assert_not_called()

    def negative(self,*,changed=False,other=False,precondition=None,rejection=None):
        before=dict(files={'selector':'a','history/wire.json':'wire'},directories=[])
        after=dict(files={'selector':'a','history/wire.json':'wrong'},directories=[]) if changed else before
        events=[dict(node='node-1',event='FLOOR_RESERVED')]
        with patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),patch.object(r.p.run.h,'inventory',return_value=after),\
             patch.object(r.n,'observations',side_effect=[(events,[]),([] if other else events,[])]),\
             patch.object(r.r,'replay',side_effect=precondition),patch.object(r,'replay',side_effect=rejection):
            return r.negative('/original',{},before,'duplicate-delete')

    def test_negative_cannot_change_files_or_other_observations_or_fail_the_prior_layer(self):
        for kwargs,reason in ((dict(changed=True),'physical or wire inputs'),(dict(other=True),'other observations'),
                              (dict(precondition=ValueError('bad retention')),'bad retention')):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(ValueError,reason):self.negative(**kwargs)

    def test_wrong_reason_or_accepted_mutation_never_qualifies(self):
        with self.assertRaisesRegex(ValueError,'unrelated retirement negative'):self.negative(rejection=ValueError('unrelated'))
        with self.assertRaisesRegex(ValueError,'mutation accepted'):self.negative()
        result=self.negative(rejection=ValueError(r.NEGATIVES['duplicate-delete']))
        self.assertEqual('REJECTED',result['status']);self.assertEqual('PASS',result['retentionReplay'])


if __name__=='__main__':unittest.main()

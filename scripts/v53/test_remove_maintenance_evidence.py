"""Conditional force-prefix tests; complete originals are a separate gate."""
import copy
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remove_maintenance_evidence as m
from . import transition_round_evidence as r


class RemoveMaintenanceEvidenceTest(unittest.TestCase):
    def test_owner_subset_requires_complete_distinct_floor_cohort(self):
        for group,voters,owners in (({'node-1':{}},('node-1','node-2'),('node-1',)),
                                    ({'node-1':{}},('node-1','node-1'),('node-1',)),
                                    ({'node-1':{}},('node-1',),()),
                                    ({'node-1':{}},('node-1',),('node-2',)),
                                    ({'node-1':{}},('node-1',),('node-1','node-1'))):
            with self.subTest(voters=voters,owners=owners),patch.object(m,'covering_floor') as floor:
                with self.assertRaisesRegex(ValueError,'exact owner/cohort'):m.maintenance(group,voters,owners=owners)
                floor.assert_not_called()

    def test_pending_peer_supplies_unchanged_generation_without_becoming_retirement_owner(self):
        local={'pending.accept':m.c.EMPTY,'grants.gsr':b'journal',m.d.s.FILE:b'ledger'}
        peer={'pending.accept':b'original pending vote','grants.gsr':b'owned journal','sources/old/source.gscp':b'owned source'}
        group={'local':local,'peer':peer};before=copy.deepcopy(group)
        cap=dict(root='root',cut=dict(index=2));higher=dict(root='root',cut=dict(index=3))
        def current(files):return ('generations/a/',{'promise.gsr':b'current'},dict(capsule=higher if files.get('pending.accept')==b'original pending vote' else cap))
        with patch.object(m.c,'current',side_effect=current),patch.object(m,'covering_floor') as floor, \
                patch.object(m.observation,'observe_same_cut',return_value=b'observed') as observed, \
                patch.object(m.c,'anchor',side_effect=lambda cap:cap), \
                patch.object(m.confirmation,'endpoints',return_value={}), \
                patch.object(m.d.s.r,'decode',return_value=dict(plan=dict(peers=[]))), \
                patch.object(m.c,'journal',return_value=[('PROMISE',b'journal',dict(basisId=None,ballot=dict(counter=2))) ]):
            result=m.maintenance(group,('local','peer'),owners=('local',))
        self.assertEqual(before,group);self.assertEqual(peer,result['peer'])
        self.assertEqual(b'observed',result['local'][m.d.s.FILE])
        floor.assert_called_once();self.assertEqual(before,floor.call_args.args[1])
        # The higher copy covers the floor but cannot narrow same-cut debt.
        observed.assert_called_once_with(b'ledger',local,local,defer_renewal=True)

    def projection(self,*,uncovered_source=False,uncovered_debt=False,unsettled=False):
        point=dict(cut=dict(index=4));old=dict(cut=dict(index=0))
        members={'promise.gsr':b'current'};packet=dict(capsule=dict(root='root'))
        files={'pending.accept':m.c.EMPTY,'grants.gsr':b'original','generations/a':None,'generations/a/current':b'current',
               'generations/b':None,'generations/b/old':b'old',m.d.s.FILE:b'ledger'}
        rows=[]
        for identifier,ballot in [('old',1),('current',2),('latest',3)]:
            files['sources/'+identifier]=None;files['sources/'+identifier+'/source.gscp']=identifier.encode()
            rows.extend([('PROMISE',identifier.encode(),dict(basisId=identifier,ballot=dict(counter=ballot))),
                         ('BASIS',(identifier+'-basis').encode(),{}),('SELECTED',(identifier+'-selected').encode(),{})])
        if unsettled:files['applied-end']=None
        before=copy.deepcopy(files)
        with ExitStack() as stack:
            for target,name,kwargs in [
                (m.c,'current',dict(return_value=('generations/a/',members,packet))),
                (m,'covering_floor',dict(return_value={})),
                (m.observation,'observe_same_cut',dict(return_value=b'observed')),
                (m.confirmation,'endpoints',dict(return_value={4:point,**({} if uncovered_source else {0:old})})),
                (m.d.s.r,'decode',dict(return_value=dict(plan=dict(peers=[dict(possible=[dict(cut=dict(index=99))] if uncovered_debt else [point])])))),
                (m.c,'journal',dict(return_value=rows)),
                (m.c.p,'decode',dict(return_value=dict(capsule=old))),
                (m.c,'anchor',dict(side_effect=lambda cap:cap))]:stack.enter_context(patch.object(target,name,**kwargs))
            result=m.maintenance({'node-1':files},('node-1',))['node-1']
        self.assertEqual(before,files)
        return result,rows

    def test_only_obsolete_covered_source_is_deleted_current_and_latest_stay_owned(self):
        result,rows=self.projection()
        self.assertNotIn('sources/old',result);self.assertNotIn('generations/b',result)
        self.assertEqual(b'current',result['sources/current/source.gscp'])
        self.assertEqual(b'latest',result['sources/latest/source.gscp'])
        self.assertEqual(b''.join(raw for _,raw,_ in rows[3:]),result['grants.gsr'])
        self.assertEqual(b'observed',result[m.d.s.FILE])

    def test_obsolete_source_without_covered_ancestor_cannot_be_retired(self):
        with self.assertRaisesRegex(ValueError,'source retirement coverage'):self.projection(uncovered_source=True)

    def test_retained_debt_without_covered_ancestor_is_not_erased(self):
        with self.assertRaisesRegex(ValueError,'retained coverage'):self.projection(uncovered_debt=True)

    def test_applied_end_still_owns_the_source(self):
        with self.assertRaisesRegex(ValueError,'unsettled publication'):self.projection(unsettled=True)

    def fixture(self,ordinal=1):
        voters=('node-1','node-2','node-3');rows=[]
        if ordinal>1:
            rows.append(dict(node='node-1',event='DRIVER_PUBLISHED',index=ordinal+3))
            for node in voters:
                rows.extend(dict(node=node,event=event) for event in m.FLOOR+m.RETIRE+m.RELEASE+
                    ('PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN',
                     'SELECTED_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN'))
        rows.append(dict(node='node-1',event='CONTINUOUS_INSTALLED',ordinal=ordinal,selection=m.e.digest(b'selected')))
        for node in voters:
            rows.extend(dict(node=node,event=event) for event in m.FLOOR+m.RETIRE+m.SOURCE+m.RELEASE+('ACCEPT_CANDIDATE_CREATED',))
        rows.append(dict(node='node-1',event='DRIVER_PUBLISHED',index=ordinal+4))
        before={n:{'sources/old/source.gscp':b'original'} for n in voters};after={n:{} for n in voters}
        return rows,voters,before,after

    def check(self,rows,voters,before,after,ordinal=1):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/f'selected-{ordinal}.gsr').write_bytes(b'selected')
            with patch.object(m.d,'read',return_value=rows):m.boundaries(root,ordinal,voters,before,after)

    def test_each_original_maintenance_lifetime_has_its_own_order(self):
        for ordinal in (1,2,3):self.check(*self.fixture(ordinal),ordinal)

    def test_missing_source_force_cannot_use_later_peer_force(self):
        rows,voters,before,after=self.fixture()
        rows.remove(next(v for v in rows if v['node']=='node-1' and v['event']=='SOURCE_RETIREMENT_FORCED'))
        with self.assertRaisesRegex(ValueError,'exact pre-slot retirement: node-1'):self.check(rows,voters,before,after)

    def test_early_accept_and_late_release_cannot_complete_retirement(self):
        for point in ('ACCEPT_CANDIDATE_CREATED','FLOOR_RELEASE_BEFORE_RETURN'):
            rows,voters,before,after=self.fixture();row=next(v for v in rows if v['node']=='node-1' and v['event']==point)
            rows.remove(row)
            if point=='ACCEPT_CANDIDATE_CREATED':rows.insert(1,row)
            else:rows.insert(-1,row)
            with self.subTest(point=point),self.assertRaisesRegex(ValueError,'exact pre-slot retirement: node-1'):
                self.check(rows,voters,before,after)

    def test_duplicate_or_missing_deletion_cannot_match_retired_files(self):
        for count in (0,2):
            rows,voters,before,after=self.fixture();at=next(i for i,v in enumerate(rows) if v['node']=='node-1' and v['event']=='SOURCE_RETIREMENT_FILE_DELETED')
            row=rows.pop(at);rows[at:at]=[copy.deepcopy(row) for _ in range(count)]
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'exact pre-slot retirement: node-1'):
                self.check(rows,voters,before,after)

    def test_unexpected_pregrant_source_retirement_is_not_ignored(self):
        rows,voters,before,after=self.fixture(2);rows.insert(1,dict(node='node-1',event='SOURCE_RETIREMENT_FORCED'))
        with self.assertRaisesRegex(ValueError,'exact pre-grant retirement: node-1'):self.check(rows,voters,before,after,2)

    def test_missing_pregrant_floor_cannot_borrow_later_slot_floor(self):
        rows,voters,before,after=self.fixture(2);rows.remove(next(v for v in rows if v['node']=='node-1' and v['event']=='FLOOR_AUTHORITY_FORCED'))
        with self.assertRaisesRegex(ValueError,'exact pre-grant retirement: node-1'):self.check(rows,voters,before,after,2)

    def test_empty_retired_inventory_cannot_claim_source_transaction(self):
        rows,voters,before,after=self.fixture()
        with self.assertRaisesRegex(ValueError,'original retired source files'):self.check(rows,voters,after,after)

    def test_pending_vote_is_rejected_before_observation_or_retirement(self):
        with patch.object(m.c,'current',return_value=('generation/',{},dict(capsule={}))),patch.object(m,'covering_floor') as floor:
            with self.assertRaisesRegex(ValueError,'unsettled publication'):m.maintenance({'node-1':{'pending.accept':b'pending'}},('node-1',))
        floor.assert_not_called()

    def test_new_profile_negatives_preserve_legacy_cases(self):
        self.assertEqual(r.NEGATIVES,r.negative_cases(None))
        self.assertEqual(16,len(r.negative_cases('4-REMOVE')))
        self.assertEqual(r.negative_cases('4-REMOVE'),r.negative_cases('5-REMOVE'))
        with self.assertRaisesRegex(ValueError,'REMOVE profile'):r.negative_cases('3-REMOVE')

    def test_failed_original_prevents_profile_mutation(self):
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'profile_mutation') as mutation:
            with self.assertRaisesRegex(ValueError,'bad original'):r.qualify('/unused','5-REMOVE')
        mutation.assert_not_called()


if __name__=='__main__':unittest.main()

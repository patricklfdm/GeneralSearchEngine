"""Conditional journal lifetimes; native qualification remains original-first."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import joining_owner_close as r,joining_owner_close_negatives as n
from . import native_resource_evidence as native
from . import joining_continuation_evidence as continuation
from .test_resource_transitions import charge,row,trace


def fixture():
    node='node-6';events=[];boundaries=[];rows=[row('START')]
    for scope in r.SCOPES:
        journal=charge('JOURNAL','journal',20);generation=charge('GENERATION','generation',10)
        rows.extend([row('RESERVE',added=[journal],metadata=20,counts={'JOURNAL':1}),
                     row('RESERVE',added=[generation],metadata=30,counts={'JOURNAL':1,'GENERATION':1})])
        for event in (r.OPEN,r.BEGIN):
            events.append(dict(node=node,scope=scope,event=event));boundaries.append(dict(eventIndex=len(events)-1,node=node,sequence=len(rows)-1,usage=copy.deepcopy(rows[-1]['usage'])))
        rows.extend([row('RELEASE',[generation],metadata=20,counts={'JOURNAL':1}),row('RELEASE',[journal])])
        events.append(dict(node=node,scope=scope,event=r.RETURNED));boundaries.append(dict(eventIndex=len(events)-1,node=node,sequence=len(rows)-1,usage=copy.deepcopy(rows[-1]['usage'])))
    return events,{node:trace(rows)},boundaries,node


class JoiningOwnerCloseTest(unittest.TestCase):
    def cold_events(self,marked):
        node='node-6';events=[]
        if marked:
            events=[dict(node=node,scope=scope,event=event) for scope in r.SCOPES[:-1] for event in (r.OPEN,r.BEGIN,r.RETURNED)]
        cold=['CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED',
              'JOINING_RETENTION_SEED_RECOVERY_FORCED','JOINING_RETENTION_SEED_RECOVERY_PARENT_FORCED',
              'JOINING_RETENTION_DONE_RECOVERY_FORCED','JOINING_RETENTION_DONE_RECOVERY_PARENT_FORCED',
              'LEARNER_RETENTION_RECOVERY_ACTIVE_FORCED','LEARNER_RETENTION_RECOVERY_PARENT_FORCED',
              'RETENTION_RECOVERY_ACTIVE_FORCED','RETENTION_RECOVERY_PARENT_FORCED',
              'FUTURE_RETENTION_RECOVERY_FORCED','FUTURE_RETENTION_RECOVERY_PARENT_FORCED','ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED']
        cold+=([r.OPEN,'FIXTURE_OPEN_RETURNED',r.BEGIN,r.RETURNED,'FIXTURE_CLOSE_RETURNED'] if marked else
               ['FIXTURE_OPEN_RETURNED','FIXTURE_CLOSE_RETURNED'])
        return events+[dict(node=node,scope='stable-cold-owner',event=event) for event in cold]

    def test_physical_cold_replay_accepts_complete_marked_or_historical_unmarked_order(self):
        for marked in (False,True):
            events=self.cold_events(marked);before=copy.deepcopy(events)
            continuation.cold_order(events,joining='node-6');self.assertEqual(before,events)

    def test_physical_cold_replay_rejects_partial_foreign_and_reordered_close_markers(self):
        for change in ('missing-open','missing-return','duplicate','wrong-owner','reordered','other-lifetime-missing','unknown-marker'):
            events=self.cold_events(True)
            if change=='missing-open':events.pop(-5)
            elif change=='missing-return':events.pop(-2)
            elif change=='duplicate':events.insert(-2,copy.deepcopy(events[-2]))
            elif change=='wrong-owner':events[-2]['node']='node-5'
            elif change=='reordered':events[-5],events[-4]=events[-4],events[-5]
            elif change=='other-lifetime-missing':events.pop(0)
            else:events[-2]['event']='JOINING_OWNER_UNKNOWN'
            with self.subTest(change=change),self.assertRaises(ValueError):continuation.cold_order(events,joining='node-6')

    def test_physical_cold_replay_keeps_original_force_order(self):
        for marked in (False,True):
            events=self.cold_events(marked)
            index=next(i for i,v in enumerate(events) if v['event']=='CURRENT_FILES_FORCED')
            events[index],events[index+1]=events[index+1],events[index]
            with self.subTest(marked=marked),self.assertRaisesRegex(ValueError,'original cold reseal order'):
                continuation.cold_order(events,joining='node-6')

    def test_five_distinct_lifetimes_require_actual_open_and_close_boundaries(self):
        data=fixture();before=copy.deepcopy(data);result=r.replay(*data)
        self.assertEqual(list(r.SCOPES),list(result['lifetimes']));self.assertEqual(10,result['releasedLeases']);self.assertEqual(before,data)
        self.assertTrue(result['joiningCloseIntervalsQualified']);self.assertFalse(result['physicalShutdownOrderQualified']);self.assertFalse(result['phase3Complete'])

    def test_all_twelve_exact_negatives_reject_without_changing_original(self):
        data=fixture();before=copy.deepcopy(data);result=n.replay(data)
        self.assertEqual([dict(case=k,status='REJECTED',reason=v) for k,v in n.NEGATIVES.items()],result);self.assertEqual(before,data)

    def test_invalid_original_cannot_count_mutations(self):
        data=fixture();data[1]['node-6']['failed']=True
        with patch.object(n,'mutate') as mutate,self.assertRaisesRegex(ValueError,'incomplete observation'):n.replay(data)
        mutate.assert_not_called()

    def test_markers_require_exact_identity_shape_and_order(self):
        for case in ('extra-key','wrong-node','wrong-scope','wrong-event','reordered','extra-lifetime'):
            events=fixture()[0]
            if case=='extra-key':events[0]['sequence']=3
            elif case=='wrong-node':events[0]['node']='node-5'
            elif case=='wrong-scope':events[0]['scope']='foreign'
            elif case=='wrong-event':events[0]['event']='JOINING_OWNER_UNKNOWN'
            elif case=='reordered':events[0],events[1]=events[1],events[0]
            else:events.extend(copy.deepcopy(events[:3]))
            with self.subTest(case=case),self.assertRaises(ValueError):r.intervals(events,'node-6')

    def test_boundary_fields_cannot_use_aliases_boolean_indices_or_forged_usage(self):
        for field,value in [('eventIndex',True),('node','node-5'),('sequence',True),('sequence',-1),('usage',{})]:
            data=fixture();data[2][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):r.replay(*data)

    def test_new_source_entry_rejects_old_unmarked_history_before_physical_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'events.json').write_bytes(b'[]')
            with patch.object(native.publication,'validate') as physical,self.assertRaisesRegex(ValueError,'complete ordered lifetimes'):
                native.validate(p,'5-REPLACE-required-four',joined_closes=True)
            physical.assert_not_called()
        for profile,flag in [('stable',True),('5-REPLACE-required-four',1)]:
            with self.assertRaisesRegex(ValueError,'joined closes policy'):native.validate('/unused',profile,joined_closes=flag)

    def test_original_stable_cold_fixture_marker_is_allowed_after_journal_return(self):
        data=fixture();events,_,boundaries,node=data
        events.append(dict(node=node,scope='stable-cold-owner',event='FIXTURE_CLOSE_RETURNED'))
        boundaries.append(dict(boundaries[-1],eventIndex=len(events)-1))
        self.assertTrue(r.replay(*data)['joiningCloseIntervalsQualified'])


if __name__=='__main__':unittest.main()

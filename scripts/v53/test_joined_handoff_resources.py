"""Handoff lifetime tests; synthetic fixtures are not native qualification."""
import copy
import unittest
from unittest.mock import patch

from . import joined_handoff_resources as r, joined_handoff_negatives as n
from . import native_resource_evidence as native
from .test_resource_transitions import charge, trace
from .floor_resource_negatives import recount


def fixture():
    old = [charge('GENERATION','learner-prepared',40), charge('GENERATION','learner-voter-stage',100),
           charge('SOURCE','pending',50), charge('LEARNER','received',60),
           charge('APPLICATION','learner-typed-backup',64*r.t.MIB), charge('APPLICATION','original',8),
           charge('JOURNAL','pending-journal',6000), charge('MISC','learner-plan',2*r.t.MIB)]
    custody = [dict(v,owner='learner-custody-'+str(i)) for i,v in enumerate(old)]
    new = [charge('GENERATION','a',70),charge('APPLICATION','generation-a:image',8),
           charge('JOURNAL','membership-grants',32*r.t.MIB),charge('MISC','current-authority',2*r.t.MIB)]
    plan = dict(node='node-6',predecessor=[dict(unit=v['unit'],bytes=v['bytes']) for v in old],
                native=[{k:v for k,v in c.items() if k!='claimSource'} for c in new],deletions=2)
    events=[];boundaries=[];rows=[dict(event='START',removed=[],added=[])]
    def mutation(name,removed=(),added=()):
        rows.append(dict(event=name,removed=copy.deepcopy(list(removed)),added=copy.deepcopy(list(added))))
    def point(scope,name):
        boundaries.append(dict(eventIndex=len(events),node='node-6',sequence=len(rows)-1,usage={}))
        events.append(dict(scope=scope,event=name,node='node-6'))
    def write(file):
        for action in ('CREATED','PREFIX_WRITTEN','WRITTEN','FORCED','PARENT_FORCED'):
            point('retirement','JOINED_RETIREMENT_'+action+':'+file)
    for v in old:mutation('RESERVE',added=[v])
    for action in ('DIRECTORY_FORCED','CREATED','PREFIX_WRITTEN','WRITTEN','FORCED','PARENT_FORCED'):
        point('custody','LEARNER_CUSTODY_'+action)
    for index,(scope,name) in enumerate(r.POINTS):
        if index==1:mutation('TRANSFER',old,custody)
        if index==7:mutation('REPLACE',custody,new)
        point(scope,name)
        if index==2:
            point('retirement','JOINED_RETIREMENT_DIRECTORY_FORCED');write('retirement.json')
        if index==3:
            for i in range(plan['deletions']):
                for prefix in ('JOINED_RETIREMENT_BEFORE_DELETE:','JOINED_RETIREMENT_DELETED:','JOINED_RETIREMENT_DELETE_FORCED:'):
                    point('retirement',prefix+str(i))
            write('retired.json')
    for v in new:mutation('RELEASE',[v])
    traces={'node-6':trace([dict(v,usage={}) for v in rows])};recount(traces,boundaries)
    return plan,events,traces,boundaries


class JoinedHandoffResourcesTest(unittest.TestCase):
    def test_one_pool_retains_originals_then_replaces_atomically(self):
        data=fixture();before=copy.deepcopy(data);result=r.replay(*data)
        self.assertEqual(data,before)
        self.assertEqual(8,result['predecessorLeases']);self.assertEqual(4,result['nativeLeases'])
        self.assertEqual(6,result['deletionCallbacks']);self.assertTrue(result['continuousHandoffQualified'])
        for key in ('physicalPeakQualified','wholeRuntimeResourcesQualified','processDeathQualified',
                    'explicitJoiningCloseIntervalsQualified','finalSourceCohortQualified','phase3Complete'):
            self.assertFalse(result[key])

    def test_every_coherent_negative_has_its_declared_rejection(self):
        result=n.replay(fixture())
        self.assertEqual(list(n.NEGATIVES),[v['case'] for v in result])
        self.assertTrue(all(v['status']=='REJECTED' for v in result))

    def test_original_must_pass_before_any_mutation(self):
        data=fixture();data[2]['node-6']['failed']=True
        with patch.object(n,'mutate') as mutate,self.assertRaisesRegex(ValueError,'incomplete observation'):
            n.replay(data)
        mutate.assert_not_called()

    def test_loader_and_physical_precondition_are_not_optional(self):
        with patch.object(native.collection,'inventory',return_value={}),\
             patch.object(native,'validate',side_effect=ValueError('bad original')) as original,\
             patch.object(r,'derive') as derive,patch.object(native,'load') as load,\
             self.assertRaisesRegex(ValueError,'bad original'):
            n.qualify('/unused')
        original.assert_called_once();derive.assert_not_called();load.assert_not_called()

    def test_changed_original_cannot_finish_qualification(self):
        data=fixture()
        with patch.object(native.collection,'inventory',side_effect=[{'before':1},{'after':1}]),\
             patch.object(native,'validate',return_value={'status':'PASS'}),\
             patch.object(r,'derive',return_value=data[0]),\
             patch.object(native,'load',return_value=(None,data[2],data[3],data[1])),\
             self.assertRaisesRegex(ValueError,'qualification changed original'):
            n.qualify('/unused')

    def test_checkpoint_identity_boolean_sequence_and_limits_are_not_advisory(self):
        for kind in ('event-index','node','sequence','usage','limit'):
            data=fixture();point=data[3][0]
            if kind=='event-index':point['eventIndex']=False
            elif kind=='node':point['node']='node-1'
            elif kind=='sequence':point['sequence']=True
            elif kind=='usage':point['usage']['metadata']+=1
            else:data[2]['node-6']['stagingLimit']+=1
            with self.subTest(kind=kind),self.assertRaises(ValueError):r.replay(*data)

    def test_zero_close_is_required_even_after_valid_handoff(self):
        data=fixture();value=data[2]['node-6'];value['changes'].pop();recount(data[2],data[3])
        with self.assertRaisesRegex(ValueError,'outstanding charges at close'):r.replay(*data)

    def test_extra_and_duplicate_lifecycle_callbacks_are_not_ignored(self):
        data=fixture();at=r.positions(data[1],data[0]['node'])[0]
        data[1].append(copy.deepcopy(data[1][at]));data[3].append(copy.deepcopy(data[3][at]))
        with self.assertRaisesRegex(ValueError,'unique original lifecycle'):r.replay(*data)


if __name__=='__main__':unittest.main()

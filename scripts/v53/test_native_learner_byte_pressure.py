"""Small independent reader fixtures, not evidence of native authority."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_learner_byte_pressure as b
from .test_resource_transitions import trace as make_trace

n,t=b.n,b.t


def observation(mode):
    misc=n.charge('MISC','learner-plan',2*t.MIB);typed=n.charge('APPLICATION','learner-typed-backup',64*t.MIB)
    generation=n.charge('GENERATION','learner-prepared:'+'a'*64,10)
    first=n.charge('LEARNER','learner-store',10);app=n.charge('APPLICATION','learner-store:first.image',4)
    terminal=n.charge('LEARNER','learner-cancellation',20);last=n.charge('APPLICATION','cancel:last.image',5)
    state={};changes=[];rows=[];events=[]
    d=dict(state={t.key(v):v for v in (misc,typed,generation,app,terminal,last)},steady=64*t.MIB+29,
           packet=15,images={'a'*64:5},peer={'nodeId':'node-1'})
    limits=(384*t.MIB,b.limit(mode,d),64*t.MIB)
    def change(event,removed=(),added=()):
        for v in removed:del state[t.key(v)]
        for v in added:state[t.key(v)]=v
        changes.append(dict(sequence=len(changes),event=event,removed=sorted(copy.deepcopy(removed),key=t.order_key),
                            added=sorted(copy.deepcopy(added),key=t.order_key),usage=t.usage(state,limits)))
    def mark(kind,name,point=''):
        rows.append(dict(ordinal=len(rows),kind=kind,name=name,point=point,sequence=len(changes)-1,usage=t.usage(state,limits)))
    def callback(point):events.append(point);mark('CALLBACK','resume',point)
    change('START');mark('POOL','start')
    for v in (misc,first,app,typed):change('RESERVE',added=[v])
    claim=dict(generation,bytes=0,claimSource='learner-store');change('GENERATION_CLAIM',added=[claim])
    callback('LEARNER_PREPARED_BEFORE_SELECT');change('GENERATION_COMMIT',removed=[claim,first],added=[generation])
    callback('LEARNER_PREPARED_BEFORE_RETURN')
    for v in (terminal,last):change('RESERVE',added=[v])
    callback('LEARNER_CANCEL_ACTIVE_PLAN_FORCED');callback(b.POINT);mark('PROBE_BEGIN',mode,b.POINT)
    control=n.charge('CONTROL','received-records-original',4096);change('RESERVE',added=[control])
    transfer='11111111-1111-4111-8111-111111111111';image='22222222-2222-4222-8222-222222222222'
    probe=dict(transfer=transfer,session='33333333-3333-4333-8333-333333333333',source=d['peer'],scratch='/actual/source',
               images=[],outcome='REJECTED',reason='shared staging capacity',scratchRemoved=True)
    if mode=='source-exact':
        source=n.charge('SOURCE',transfer,15);received=n.charge('APPLICATION',image,5)
        for v in (source,received):change('RESERVE',added=[v])
        mark('PROBE_COMPLETE',mode)
        for v in (received,source):change('RELEASE',removed=[v])
        probe.update(images=[dict(transfer=image,digest='a'*64,bytes=5)],outcome='ACCEPTED',reason='')
    change('RELEASE',removed=[control]);mark('PROBE_RETURN',mode,b.POINT);mark('SNAPSHOT','returned')
    for name,released in (('cancel',(terminal,last)),('typed',()),('store',(typed,app,generation,misc))):
        mark('CLOSE_BEGIN','resume-'+name)
        for v in released:change('RELEASE',removed=[v])
        mark('CLOSE_RETURN','resume-'+name)
    mark('SNAPSHOT','closed');d['events']=copy.deepcopy(events)
    trace=make_trace(changes);trace['stagingLimit']=limits[1]
    result=dict(status='PARTIAL',mode=mode,steadyStagingBytes=d['steady'],stagingLimit=limits[1],packetBytes=15,imageBytes=5,
                sameOriginalColdRecovery=True,wholeRuntimeResourcesQualified=False,phase3Complete=False)
    return mode,d,trace,rows,events,[probe],result


class LearnerBytePressureTest(unittest.TestCase):
    def test_actual_limits_have_zero_one_byte_and_complete_source_headroom(self):
        for mode in b.MODES:
            value=observation(mode);saved=copy.deepcopy(value);result=b.bind(*value)
            self.assertEqual(3,result['closeIntervals']);self.assertEqual(saved,value)
            self.assertFalse(result['wholeRuntimeResourcesQualified']);self.assertFalse(result['phase3Complete'])
        d=observation('pool-full')[1]
        self.assertEqual(d['steady']+14,b.limit('packet-short',d));self.assertEqual(d['steady']+20,b.limit('source-exact',d))

    def test_every_observation_negative_requires_its_exact_cause(self):
        for name,reason in b.NEGATIVES.items():
            with self.subTest(name=name):
                value=observation('source-exact' if name=='foreign-transfer' else 'pool-full');b.mutate(value,name)
                with self.assertRaises(ValueError) as error:b.bind(*value)
                self.assertEqual(reason,str(error.exception))

    def test_original_authority_failure_prevents_any_byte_pressure_credit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'original').mkdir();(root/'pressure').mkdir()
            with patch.object(n,'validate',side_effect=ValueError('invalid original')),patch.object(b,'derive') as derive,patch.object(b,'mutate') as mutate:
                with self.assertRaisesRegex(ValueError,'invalid original'):b.qualify(root)
                derive.assert_not_called();mutate.assert_not_called()

    def test_missing_original_or_extra_mode_cannot_be_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'complete wrapper'):b.validate(tmp)

    def test_missing_refusal_cleanup_cannot_be_hidden_by_unchanged_totals(self):
        value=observation('pool-full');rows=value[3]
        begin=next(v for v in rows if v['kind']=='PROBE_BEGIN')
        end=next(v for v in rows if v['kind']=='PROBE_RETURN')
        end.update(sequence=begin['sequence'],usage=copy.deepcopy(begin['usage']))
        with self.assertRaisesRegex(ValueError,'refusal cleanup'):b.bind(*value)

    def test_wrong_callback_location_is_rejected_even_with_valid_accounting(self):
        value=observation('pool-full');rows=value[3]
        i=next(i for i,v in enumerate(rows) if v['kind']=='PROBE_BEGIN')
        rows[i-1],rows[i]=rows[i],rows[i-1]
        for j,row in enumerate(rows):row['ordinal']=j
        with self.assertRaisesRegex(ValueError,'callback placement'):b.bind(*value)

    def test_foreign_image_and_early_positive_complete_are_not_admitted(self):
        value=observation('source-exact');value[5][0]['images'][0]['transfer']='00000000-0000-0000-0000-000000000000'
        with self.assertRaisesRegex(ValueError,'exact complete source'):b.bind(*value)
        value=observation('source-exact');row=next(v for v in value[3] if v['kind']=='PROBE_COMPLETE')
        row['sequence']-=1;row['usage']=copy.deepcopy(value[2]['changes'][row['sequence']]['usage'])
        with self.assertRaisesRegex(ValueError,'exact complete source'):b.bind(*value)

    def test_claimed_full_qualification_and_non_integer_observations_fail(self):
        for field,val in (('ordinal',False),('sequence',True)):
            value=observation('pool-full');value[3][0][field]=val
            with self.assertRaisesRegex(ValueError,'exact boundary'):b.bind(*value)
        value=observation('pool-full');value[6]['wholeRuntimeResourcesQualified']=True
        with self.assertRaisesRegex(ValueError,'exact result'):b.bind(*value)


if __name__=='__main__':unittest.main()

"""Conditional floor byte/lifetime tests; full native admission is separate."""
import copy
import unittest
from unittest.mock import patch

from . import floor_resource_evidence as r
from .test_resource_transitions import charge,trace


def recount(rows):
    state={}
    for row in rows:
        for value in row['removed']:state.pop(r.t.key(value))
        for value in row['added']:state[r.t.key(value)]=value
        row['usage']=r.t.usage(state,(384*r.t.MIB,512*r.t.MIB,64*r.t.MIB))
    return trace(rows)


def repair(data):
    _,_,traces,boundaries=data
    for node,value in traces.items():traces[node]=recount(value['changes'])
    for point in boundaries:point['usage']=copy.deepcopy(traces[point['node']]['changes'][point['sequence']]['usage'])


def gap(data,key,at):
    """Release and reacquire between callbacks, retaining all observed totals."""
    _,_,traces,boundaries=data;node=boundaries[at]['node'];seq=boundaries[at]['sequence'];rows=traces[node]['changes']
    value=next(v for row in rows[:seq+1] for v in row['added'] if r.t.key(v)==key)
    rows[seq+1:seq+1]=[dict(event='RELEASE',removed=[value],added=[]),dict(event='RESERVE',removed=[],added=[value])]
    for point in boundaries:
        if point['node']==node and point['sequence']>seq:point['sequence']+=2
    repair(data)


def fixture(network=True,pinned=False):
    copies={node:dict(node=node,manifest=node.encode(),members={'source.gsr':b'original-'+node.encode(),
                'a.image':b'first image','b.image':b'second image'}) for node in ('node-1','node-2','node-3')}
    ordered=sorted((v for node,v in copies.items() if not pinned or node!='node-1'),
                   key=lambda v:((v['node']=='node-1') if network else False,r.sha(v['manifest'])))
    extents=[r.extents(v,'floor:'+r.sha(v['manifest'])) for v in ordered]
    pin=r.extents(copies['node-1'],'a',pinned=True) if pinned else {}
    events=[dict(node='node-1',event=name) for name in r.maintenance.m.floor_events(copies,'node-1',network,pinned=pinned)]
    floor=dict(node='node-1',start=0,end=len(events)-1,points=list(range(len(events))),network=network,copies=extents,pin=pin)
    rows=[dict(event='START',removed=[],added=[])];state={};boundaries=[]
    def reserve(values):
        for (unit,owner),size in values.items():
            if (unit,owner) in state:continue
            value=charge(unit,owner,size);rows.append(dict(event='RESERVE',removed=[],added=[value]));state[unit,owner]=value
    def release(keys):
        for key in keys:rows.append(dict(event='RELEASE',removed=[state.pop(key)],added=[]))
    reserve(pin)
    for values in (extents[:1] if network else extents):reserve(values)
    ordinal=0
    for at,event in enumerate(events):
        if event['event']=='FLOOR_COPY_CREATED':reserve(extents[ordinal]);ordinal+=1
        boundaries.append(dict(node='node-1',eventIndex=at,sequence=len(rows)-1,usage={}))
        if event['event']=='FLOOR_RELEASE_CLEARED':release([key for key in state if key[1].startswith('floor:')])
    release(list(state));data=([floor],events,{'node-1':recount(rows)},boundaries);repair(data)
    return data


class FloorResourceEvidenceTest(unittest.TestCase):
    def test_direct_network_and_pinned_copy_lifetimes(self):
        for network,pinned in ((False,False),(True,False),(True,True)):
            with self.subTest(network=network,pinned=pinned):
                data=fixture(network,pinned);result=r.replay(*data)
                self.assertEqual(6 if pinned else 9,result['copyLeases'])
                self.assertEqual(int(pinned),result['pinnedFloors']);self.assertTrue(result['floorStorageLifetimesQualified'])
                self.assertFalse(result['physicalPeakQualified']);self.assertFalse(result['wholeRuntimeResourcesQualified'])

    def test_metadata_includes_manifest_and_all_non_image_originals(self):
        value=dict(manifest=b'123',members={'z.image':b'99999','a.image':b'11','source.gsr':b'1234'})
        self.assertEqual({('SOURCE','floor:x'):7,('APPLICATION','floor:x:0'):2,('APPLICATION','floor:x:1'):5},r.extents(value,'floor:x'))

    def test_repeated_floor_with_same_original_copies_uses_new_complete_leases(self):
        data=fixture(pinned=True);later=fixture(pinned=True)
        event_offset=len(data[1]);sequence_offset=len(data[2]['node-1']['changes'])-1
        for floor in later[0]:
            floor['start']+=event_offset;floor['end']+=event_offset
            floor['points']=[v+event_offset for v in floor['points']]
        for point in later[3]:point['eventIndex']+=event_offset;point['sequence']+=sequence_offset
        data[0].extend(later[0]);data[1].extend(later[1]);data[3].extend(later[3])
        data[2]['node-1']['changes'].extend(later[2]['node-1']['changes'][1:]);repair(data)
        result=r.replay(*data)
        self.assertEqual(2,result['floors']);self.assertEqual(12,result['copyLeases']);self.assertEqual(2,result['pinnedFloors'])

    def test_consistent_forged_metadata_and_image_counters_are_rejected(self):
        for unit in ('SOURCE','APPLICATION'):
            data=fixture();rows=data[2]['node-1']['changes']
            key=next(r.t.key(v) for row in rows for v in row['added'] if v['unit']==unit)
            for row in rows:
                for v in row['added']+row['removed']:
                    if r.t.key(v)==key:v['bytes']+=1
            repair(data)
            with self.subTest(unit=unit),self.assertRaisesRegex(ValueError,'exact live copy extents'):r.replay(*data)

    def test_original_copy_digest_and_image_ordinal_cannot_be_swapped(self):
        for suffix in (':foreign',':99'):
            data=fixture();rows=data[2]['node-1']['changes'];key=next(r.t.key(v) for row in rows for v in row['added'] if v['unit']=='APPLICATION')
            for row in rows:
                for v in row['added']+row['removed']:
                    if r.t.key(v)==key:v['owner']+=suffix
            repair(data)
            with self.subTest(suffix=suffix),self.assertRaisesRegex(ValueError,'exact live copy extents'):r.replay(*data)

    def test_uncharged_copy_between_callbacks_cannot_hide_behind_equal_totals(self):
        data=fixture();key=next(iter(data[0][0]['copies'][0]));gap(data,key,10)
        with self.assertRaisesRegex(ValueError,'complete copy release interval'):r.replay(*data)

    def test_pin_gap_between_callbacks_is_rejected(self):
        data=fixture(pinned=True);key=next(iter(data[0][0]['pin']));gap(data,key,10)
        with self.assertRaisesRegex(ValueError,'continuous original pin coverage'):r.replay(*data)

    def test_pin_extent_cannot_be_supplied_by_copy_or_other_generation(self):
        for mode in ('smaller','wrong-slot'):
            data=fixture(pinned=True);key=next(iter(data[0][0]['pin']))
            for row in data[2]['node-1']['changes']:
                for v in row['added']+row['removed']:
                    if r.t.key(v)==key:
                        if mode=='smaller':v['bytes']-=1
                        else:v['owner']='b'
            repair(data)
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'continuous original pin coverage'):r.replay(*data)

    def test_conservative_pin_reservation_does_not_require_false_exact_size(self):
        data=fixture(pinned=True);key=next(iter(data[0][0]['pin']))
        for row in data[2]['node-1']['changes']:
            for v in row['added']+row['removed']:
                if r.t.key(v)==key:v['bytes']+=1
        repair(data);self.assertTrue(r.replay(*data)['floorStorageLifetimesQualified'])

    def test_unbound_temporary_copy_is_not_hidden_by_zero_close(self):
        data=fixture();v=charge('SOURCE','floor:unbound',1);rows=data[2]['node-1']['changes']
        rows.extend([dict(event='RESERVE',removed=[],added=[v]),dict(event='RELEASE',removed=[v],added=[])]);repair(data)
        with self.assertRaisesRegex(ValueError,'unbound copy reservation'):r.replay(*data)

    def test_missing_floor_or_checkpoint_and_changed_usage_are_refused(self):
        for mode in ('floor','checkpoint','usage'):
            data=fixture()
            if mode=='floor':data[0].clear()
            elif mode=='checkpoint':data[3].pop()
            else:data[3][0]['usage']['metadata']+=1
            with self.subTest(mode=mode),self.assertRaises(ValueError):r.replay(*data)

    def test_all_coherent_negatives_reject_the_declared_reason(self):
        from . import floor_resource_negatives as negatives
        result=negatives.replay(fixture(pinned=True))
        self.assertEqual(list(negatives.NEGATIVES),[v['case'] for v in result])

    def test_invalid_original_does_not_count_as_negative_success(self):
        from . import floor_resource_negatives as negatives
        data=fixture(pinned=True);data[2]['node-1']['truncated']=True
        with patch.object(negatives,'mutate') as mutate,self.assertRaisesRegex(ValueError,'incomplete observation'):
            negatives.replay(data)
        mutate.assert_not_called()

    def test_full_entry_requires_complete_native_admission(self):
        from . import floor_resource_negatives as negatives
        with patch.object(negatives.native.collection,'inventory',return_value={}), \
             patch.object(negatives.native,'validate',side_effect=ValueError('bad original')),patch.object(negatives.native,'load') as load:
            with self.assertRaisesRegex(ValueError,'bad original'):negatives.qualify('/unused')
        load.assert_not_called()


if __name__=='__main__':unittest.main()

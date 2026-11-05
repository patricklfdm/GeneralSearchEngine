"""Original-interval derivation and repeated borrow matching, no native claim."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import required_four_direct_exports as r
from . import direct_export_negatives as negatives
from .test_direct_export_evidence import fixture as single
from .test_joining_metadata_extents import frame
from .test_transport_resource_evidence import recount


def repeated(phase='MAINTENANCE'):
    traces,closes,expected=single(phase);trace=traces['node-1'];old=next(v for v in closes['node-1']['rows'] if v['event']==phase+'_BORROW_ACQUIRED')['owner']
    name=old[:-36]+'00000000-0000-0000-0000-000000000003'
    value=next(copy.deepcopy(v) for row in trace['changes'] for v in row['added'] if v['owner']==old);value['owner']=name
    spacer=dict(unit='CONTROL',owner='interval-point',bytes=1,claimSource='')
    at=len(trace['changes']);rows=trace['changes']
    rows.extend([dict(event='RESERVE',added=[value],removed=[]),dict(event='RESERVE',added=[spacer],removed=[]),
                 dict(event='RELEASE',added=[],removed=[spacer]),dict(event='RELEASE',added=[],removed=[value])])
    traces['node-1']=recount(rows)
    close_rows=closes['node-1']['rows']
    for event,point in (('ACQUIRED',at),('CLOSE_BEGIN',at+2),('RETURNED',at+3)):
        close_rows.append(dict(sequence=0,event=phase+'_BORROW_'+event,call=0,resourceSequence=point,owner=name,children=[]))
    negatives.renumber(closes['node-1'])
    plan=dict(expected[0],through=at+1)
    plan['before' if phase=='MAINTENANCE' else 'after']=at if phase=='MAINTENANCE' else at-1
    expected.append(plan)
    return traces,closes,expected


def native_inputs():
    root='a'*64;selection=r.f.decode(frame('SELECTED',root=root),'records','SELECTED');sources=[]
    for ordinal,node in enumerate(('node-1','node-2')):
        identifier=selection['sources'][ordinal]['basisId']
        basis=frame('BASIS',root=root,voter=node,basisId=identifier,ballot=selection['ballot']);value=r.f.decode(basis,'records','BASIS')
        promise=frame('PROMISE',root=root,basisId=identifier,ballot=selection['ballot'])
        selection['sources'][ordinal]['basisDigest']=r.sha(basis)
        sources.append(dict(node=node,start=2*ordinal+1,returnEvent=2*ordinal,end=13,basis=basis,promise=promise,value=value))
    names=[('node-1','GRANT_BEFORE_RETURN'),('node-1','GRANT_CAPTURED'),('node-2','GRANT_BEFORE_RETURN'),('node-2','GRANT_CAPTURED'),
           ('node-1','SELECTED_FORCED'),('node-2','SELECTED_FORCED'),('node-2','INSTALL_BEFORE_RETURN'),('node-1','INSTALL_BEFORE_RETURN'),
           ('node-1','FLOOR_RESERVED'),('node-1','FLOOR_COPY_HANDED_OFF'),('node-1','FLOOR_RELEASE_BEFORE_RETURN'),
           ('node-2','FLOOR_RESERVED'),('node-2','FLOOR_RELEASE_BEFORE_RETURN')]
    events=[dict(node=node,event=event) for node,event in names]
    for source in sources:events[source['start']]['basis']=r.sha(source['basis'])
    boundaries=[dict(eventIndex=i,node=v['node'],sequence=i+1) for i,v in enumerate(events)]
    owners={node:dict(node=node,manifest=frame('GENERATION',node=node,root=root),members={'source.gscp':b'original packet'}) for node in ('node-1','node-2')}
    inputs=[dict(start=8,own=owners['node-1'],copies=owners),dict(start=11,own=owners['node-2'],copies=owners)]
    selected=r.f.encode('records','SELECTED',selection)
    return SimpleNamespace(events=events,sources=sources,model=SimpleNamespace(phases=[{'SELECTED':selected},{'SELECTED':selected}],root=root),
                           floor_inputs=inputs,pinned_floors=set()),boundaries


class RequiredFourDirectExportsTest(unittest.TestCase):
    def test_same_original_content_has_distinct_owned_calls_in_each_interval(self):
        for phase in r.direct.close.DIRECT_ROLES:
            data=repeated(phase);before=copy.deepcopy(data);result=r.direct.replay(*data)
            with self.subTest(phase=phase):
                self.assertEqual('PASS',result['status']);self.assertEqual(2,result['directExports']);self.assertEqual(before,data)

    def test_ambiguous_original_interval_is_not_arbitrarily_assigned(self):
        data=single('ACTIVATION');extra=dict(data[2][0]);extra['bytes']+=1;data[2].append(extra)
        with self.assertRaisesRegex(ValueError,'ambiguous original interval'):r.direct.replay(*data)

    def test_missing_repeated_call_cannot_reuse_the_first_success(self):
        data=repeated();data[2][1]['before']+=1;data[2][1]['through']+=1
        # Both points still fit the second real call. Remove its observation,
        # keeping the actual allocation; inventory must fail first.
        name=next(v['owner'] for v in reversed(data[1]['node-1']['rows']) if v['event']=='MAINTENANCE_BORROW_ACQUIRED')
        data[1]['node-1']['rows']=[v for v in data[1]['node-1']['rows'] if v['owner']!=name];negatives.renumber(data[1]['node-1'])
        with self.assertRaisesRegex(ValueError,'unclaimed allocation'):r.direct.replay(*data)

    def test_malformed_expectations_fail_before_matching(self):
        for fault in ('boolean','phase','node','extra','outside'):
            data=single();plan=data[2][0]
            if fault=='boolean':plan['through']=True
            elif fault=='phase':plan['phase']=[]
            elif fault=='node':plan['node']='node-99'
            elif fault=='extra':plan['ignored']=1
            else:plan['through']=10**9
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'original expectation'):r.direct.replay(*data)

    def test_original_selections_and_only_network_floors_require_borrows(self):
        reader,boundaries=native_inputs();before=copy.deepcopy((reader,boundaries));plans=r.derive(reader,boundaries)
        self.assertEqual(['ACTIVATION','SELECTED','MAINTENANCE'],[v['phase'] for v in plans])
        self.assertEqual(4096,plans[-1]['bytes']);self.assertEqual(9,plans[-1]['before']);self.assertEqual(11,plans[-1]['through'])
        self.assertEqual(vars(before[0]),vars(reader));self.assertEqual(before[1],boundaries)

    def test_wrong_or_missing_source_promise_and_grant_are_rejected(self):
        for fault,reason in (('basis','original local source'),('promise','original local promise'),('grant','original grant return')):
            reader,boundaries=native_inputs()
            if fault=='basis':reader.sources[0]['basis']=reader.sources[1]['basis']
            elif fault=='promise':reader.sources[0]['promise']=reader.sources[1]['promise']
            else:reader.events[0]['event']='OMITTED_GRANT'
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,reason):r.derive(reader,boundaries)

    def test_every_actual_installation_and_selection_force_is_required(self):
        for event in ('INSTALL_BEFORE_RETURN','SELECTED_FORCED'):
            reader,boundaries=native_inputs();reader.events.append(dict(node='node-99',event=event))
            boundaries.append(dict(eventIndex=len(boundaries),node='node-99',sequence=99))
            with self.subTest(event=event),self.assertRaisesRegex(ValueError,'complete activation coverage'):r.derive(reader,boundaries)

    def test_selected_installation_must_precede_source_retirement(self):
        reader,boundaries=native_inputs();reader.sources[0]['end']=7
        with self.assertRaisesRegex(ValueError,'original local source'):r.derive(reader,boundaries)

    def test_original_boundary_node_and_sequence_types_are_checked(self):
        for fault in ('node','index','sequence'):
            reader,boundaries=native_inputs()
            if fault=='node':boundaries[0]['node']='node-2'
            elif fault=='index':boundaries[0]['eventIndex']=False
            else:boundaries[0]['sequence']=True
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'exact event boundary'):r.derive(reader,boundaries)

    def test_wrong_floor_manifest_cannot_borrow_another_node(self):
        reader,boundaries=native_inputs();reader.floor_inputs[0]['own']['manifest']=frame('GENERATION',node='node-2',root='a'*64)
        with self.assertRaisesRegex(ValueError,'original floor generation'):r.derive(reader,boundaries)

    def test_native_replay_preserves_complete_inventory_prerequisite(self):
        reader,boundaries=native_inputs()
        with patch.object(r.direct,'replay',side_effect=ValueError('original inventory failed')):
            with self.assertRaisesRegex(ValueError,'original inventory failed'):r.replay({}, {},reader,boundaries)

    def test_required_four_negative_entry_cannot_skip_original_native_admission(self):
        with patch.object(negatives.a.collection,'inventory',return_value={}),patch.object(negatives.a,'validate',side_effect=ValueError('invalid native original')) as original,patch.object(r,'derive') as derive:
            with self.assertRaisesRegex(ValueError,'invalid native original'):negatives.validate('/unused','5-REPLACE-required-four')
            original.assert_called_once_with(negatives.Path('/unused'),'5-REPLACE-required-four',control_closes=True,export_ownership=True,direct_exports=True)
            derive.assert_not_called()

    def test_each_original_grant_return_must_belong_to_its_capture(self):
        for fault in ('foreign-return','foreign-capture','missing-return'):
            reader,boundaries=native_inputs()
            if fault=='foreign-return':reader.sources[1]['returnEvent']=0
            elif fault=='foreign-capture':reader.events[1]['basis']='e'*64
            else:reader.sources[0].pop('returnEvent')
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'original grant return'):r.derive(reader,boundaries)


if __name__=='__main__':unittest.main()

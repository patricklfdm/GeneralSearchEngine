"""Conditional receiving byte/lifetime regressions; native admission is separate."""
import copy
import unittest
from unittest.mock import patch
from uuid import UUID

from . import receive_resource_evidence as r, receive_resource_negatives as negatives
from .test_resource_transitions import charge
from .test_floor_resource_evidence import recount


def fixture(terminal='TRANSFER'):
    rows=[dict(event='START',removed=[],added=[])];events=[];boundaries=[];expected=[]
    source=str(UUID(int=11));learner=str(UUID(int=12));image=str(UUID(int=13));node='node-1'
    def change(event,removed=(),added=()):rows.append(dict(event=event,removed=list(removed),added=list(added)))
    def event(name):
        at=len(events);events.append(dict(node=node,event=name))
        boundaries.append(dict(eventIndex=at,node=node,sequence=len(rows)-1,usage={}))
        return at
    def offer(identifier,unit,size):
        at=event('TRANSFER_OFFER')
        value=dict(node=node,id=identifier,unit=unit,size=size,offerSent=at,offerDelivered=at,
                   metadata=None,floor=None,imageReservation=None,packet=(node,identifier))
        expected.append(value);return value
    def commit(row):
        row['commitSent']=event('COMMIT_SENT');row['commitDelivered']=event('COMMIT_DELIVERED')
    source_row=offer(source,'SOURCE',40);s=charge('SOURCE',source,40)
    change('RESERVE',added=[s]);source_row['firstChunkSent']=event('CHUNK_SENT');commit(source_row)
    force=event('FLOOR_COPY_DIRECTORY_FORCED');change('RELEASE',[s])
    source_row['floor']=dict(forced=force,handed=event('FLOOR_COPY_HANDED_OFF'))
    learner_row=offer(learner,'LEARNER',20);l=charge('LEARNER',learner,20)
    change('RESERVE',added=[l]);learner_row['firstChunkSent']=event('CHUNK_SENT')
    lower=event('PACKET_CHUNK_DELIVERED');a=charge('APPLICATION',image,7);change('RESERVE',added=[a]);commit(learner_row)
    image_row=offer(image,'APPLICATION',7);image_row['firstChunkSent']=event('CHUNK_SENT');commit(image_row)
    image_row.update(packet=(node,learner),imageReservation=(lower,learner_row['commitSent']))
    delivered=event('GENERATION_METADATA_DELIVERED');grown=dict(l,bytes=30);change('STORAGE_GROW',[l],[grown])
    reserved=event('LEARNER_SOURCE_METADATA_RESERVED');forced=event('LEARNER_SOURCE_DIRECTORY_FORCED')
    learner_row['metadata']=dict(delivered=delivered,reserved=reserved,forced=forced,size=30)
    if terminal=='TRANSFER':
        owned=dict(grown,owner='learner-custody-0');owned_image=dict(a,owner='learner-custody-1')
        change('TRANSFER',[grown,a],[owned,owned_image]);change('RELEASE',[owned]);change('RELEASE',[owned_image])
    else:
        unit=terminal.split('_')[0];claim=charge(unit,'prepared',0,learner);owned=charge(unit,'prepared',30)
        change(unit+'_CLAIM',added=[claim]);change(terminal,[grown,claim],[owned]);change('RELEASE',[owned])
        owned_image=dict(a,owner='learner-custody-image');change('TRANSFER',[a],[owned_image]);change('RELEASE',[owned_image])
    plan=dict(transfers=expected,bases=set(),floorHandoffs=1)
    data=(plan,events,{node:recount(rows)},boundaries);negatives.recount(data[2],data[3]);return data


class ReceiveResourceEvidenceTest(unittest.TestCase):
    def test_original_extents_and_three_atomic_learner_custody_transitions(self):
        for terminal in ('TRANSFER','GENERATION_COMMIT','SOURCE_COMMIT'):
            with self.subTest(terminal=terminal):
                data=fixture(terminal);before=copy.deepcopy(data);result=r.replay(*data)
                self.assertEqual(3,result['transfers']);self.assertEqual(1,result['floorHandoffs'])
                self.assertEqual({'SOURCE':1,'LEARNER':1,'APPLICATION':1},result['units'])
                self.assertTrue(result['receivingTransferChargesQualified']);self.assertEqual(data,before)
                for flag in ('postHandoffLearnerCustodyQualified','otherStorageLifetimesQualified',
                             'physicalPeakQualified','wholeRuntimeResourcesQualified','phase3Complete'):
                    self.assertFalse(result[flag])

    def test_coherent_negatives_reject_all_declared_reasons(self):
        for terminal in ('TRANSFER','GENERATION_COMMIT','SOURCE_COMMIT'):
            with self.subTest(terminal=terminal):
                data=fixture(terminal);before=copy.deepcopy(data);result=negatives.replay(data)
                self.assertEqual(list(negatives.NEGATIVES),[v['case'] for v in result])
                self.assertEqual(data,before)

    def test_valid_original_is_required_before_any_mutation(self):
        data=fixture();data[2]['node-1']['truncated']=True
        with patch.object(negatives,'mutate') as mutate,self.assertRaisesRegex(ValueError,'incomplete observation'):
            negatives.replay(data)
        mutate.assert_not_called()

    def test_full_entry_requires_independent_native_original(self):
        with patch.object(negatives.native.collection,'inventory',return_value={}), \
             patch.object(negatives.native,'validate',side_effect=ValueError('bad original')),patch.object(negatives.native,'load') as load:
            with self.assertRaisesRegex(ValueError,'bad original'):negatives.qualify('/unused')
        load.assert_not_called()

    def test_missing_transfer_cannot_hide_in_other_storage(self):
        data=fixture();data[0]['transfers'].pop(0)
        with self.assertRaisesRegex(ValueError,'unbound staging lease'):r.replay(*data)

    def test_missing_journal_reservation_cannot_hide_in_other_storage(self):
        data=fixture();identifier=data[0]['transfers'][0]['id']
        for row in data[2]['node-1']['changes']:
            for charge in row['removed']+row['added']:
                if charge['owner']==identifier:charge['owner']='unbound-non-uuid'
        negatives.recount(data[2],data[3])
        with self.assertRaisesRegex(ValueError,'complete staging inventory'):r.replay(*data)

    def test_same_bytes_under_wrong_category_cannot_satisfy_source(self):
        data=fixture();identifier=data[0]['transfers'][0]['id']
        for row in data[2]['node-1']['changes']:
            for charge in row['removed']+row['added']:
                if charge['owner']==identifier:charge['unit']='LEARNER'
        negatives.recount(data[2],data[3])
        with self.assertRaisesRegex(ValueError,'original staging category'):r.replay(*data)

    def test_original_basis_uuid_is_distinct_from_receiving_uuid(self):
        data=fixture();identifier=str(UUID(int=14));value=charge('SOURCE',identifier,50)
        data[0]['bases'].add(('node-1',identifier));rows=data[2]['node-1']['changes']
        rows.extend([dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])])
        negatives.recount(data[2],data[3]);result=r.replay(*data)
        self.assertEqual(1,result['identifiedPersistentBasisOwners']);self.assertEqual(3,result['transfers'])
        data[0]['bases'].clear()
        with self.assertRaisesRegex(ValueError,'unbound staging lease'):r.replay(*data)

    def test_missing_or_duplicate_originals_and_checkpoints_fail(self):
        for mode in ('empty','duplicate','checkpoint','wrong-node','bool-index','bool-sequence','usage','handoffs'):
            data=fixture();point=data[3][data[0]['transfers'][0]['offerDelivered']]
            if mode=='empty':data[0]['transfers'].clear()
            elif mode=='duplicate':data[0]['transfers'].append(copy.deepcopy(data[0]['transfers'][0]))
            elif mode=='checkpoint':data[3].pop()
            elif mode=='wrong-node':point['node']='node-2'
            elif mode=='bool-index':point['eventIndex']=False
            elif mode=='bool-sequence':point['sequence']=False
            elif mode=='usage':point['usage']['metadata']+=1
            else:data[0]['floorHandoffs']=2
            with self.subTest(mode=mode),self.assertRaises(ValueError):r.replay(*data)

    def test_learner_needs_original_generation_metadata_and_image_parent(self):
        for mode in ('metadata','parent'):
            data=fixture()
            if mode=='metadata':data[0]['transfers'][1]['metadata']=None
            else:data[0]['transfers'][2]['packet']=('node-1',data[0]['transfers'][0]['id'])
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'learner metadata|learner image parent'):r.replay(*data)

    def test_learner_cannot_release_instead_of_retaining_custody(self):
        data=fixture();rows=data[2]['node-1']['changes'];at=next(i for i,v in enumerate(rows) if v['event']=='TRANSFER')
        old=rows[at]['removed'];rows[at:]=[dict(event='RELEASE',removed=[v],added=[]) for v in old]
        negatives.recount(data[2],data[3])
        with self.assertRaisesRegex(ValueError,'retained learner custody'):r.replay(*data)

    def test_image_cannot_release_instead_of_retaining_custody(self):
        data=fixture('SOURCE_COMMIT');rows=data[2]['node-1']['changes'];at=next(i for i,v in enumerate(rows) if v['event']=='TRANSFER')
        rows[at:]=[dict(event='RELEASE',removed=rows[at]['removed'],added=[])]
        negatives.recount(data[2],data[3])
        with self.assertRaisesRegex(ValueError,'retained learner image custody'):r.replay(*data)

    def test_full_native_entry_integrates_receiving_after_physical_admission(self):
        from . import native_resource_evidence as native
        with patch.object(native.collection,'inventory',return_value={}), \
             patch.object(native.publication,'validate',side_effect=ValueError('physical original rejected')), \
             patch.object(r,'derive') as derive:
            with self.assertRaisesRegex(ValueError,'physical original rejected'):native.validate('/unused','5-REPLACE-required-four')
        derive.assert_not_called()

class ReceiveResourceDerivationTest(unittest.TestCase):
    """Boundary derivation after mocked physical admission, never native acceptance."""
    def model(self):
        from types import SimpleNamespace
        plan,events,_,_=fixture();rows=[];contents=[];groups=[]
        packet=b'original-packet';image=b'original-image';peer=dict(node='node-2');sender=dict(node='node-1')
        def content(row,kind,raw):
            q=dict(sender=sender,recipient=peer,trace='source-session',payload=dict(id=row['id']))
            offer=dict(request=q,response=dict(payload=dict(digest=r.e.sha(raw))),sent=row['offerSent'],delivered=row['offerDelivered'])
            commit=dict(sent=row['commitSent'],delivered=row['commitDelivered'])
            result=dict(kind=kind,raw=raw,offer=offer,commit=commit)
            chunk=dict(kind='CHUNK',answer='CHUNK',request=q,sent=row['firstChunkSent'],delivered=row['firstChunkSent'])
            rows.append(chunk);contents.append(result);return result,chunk
        learner=plan['transfers'][1];application=plan['transfers'][2]
        capsule,last=content(learner,'CAPSULE',packet);last['delivered']=application['imageReservation'][0]
        app,_=content(application,'APPLICATION',image);groups.append([capsule,app])
        metadata=learner['metadata'];own=dict(manifest=b'original-manifest',members={'source.gscp':packet,'state.gsr':b'state','a.image':image})
        record=dict(kind='RECORD',raw=own['manifest'],offer=dict(request=dict(sender=sender,recipient=peer),
                    sent=application['firstChunkSent'],received=application['commitSent']),
                    commit=dict(delivered=metadata['delivered'],offered=application['commitDelivered']))
        groups.append([record])
        reader=SimpleNamespace(groups=groups,events=events,rows=rows,contents=contents,floor_inputs=[],
                               pinned_floors=set(),sources=[],windows=[],current=lambda *args:own)
        packet_value=dict(images={r.e.sha(image):len(image)})
        return reader,packet_value,own

    def derive(self,reader,packet):
        with patch.object(r.e.disk.p,'decode',return_value=packet),patch.object(r.e,'learner_alias',return_value='prefix'), \
             patch.object(r.e,'authorize_generation') as authorize:
            result=r.derive(reader)
        authorize.assert_called_once_with(reader.groups[1],reader.windows)
        return result

    def test_expected_sizes_come_from_original_bytes_not_resource_journals(self):
        reader,packet,own=self.model();result=self.derive(reader,packet)
        learner,image=result['transfers']
        self.assertEqual(len(own['members']['source.gscp']),learner['size'])
        self.assertEqual(len(own['manifest'])+len(own['members']['source.gscp'])+len(own['members']['state.gsr']),learner['metadata']['size'])
        self.assertEqual(len(own['members']['a.image']),image['size'])
        self.assertEqual((learner['node'],learner['id']),image['packet'])
        self.assertEqual(reader.rows[0]['delivered'],image['imageReservation'][0])

    def test_declared_image_digest_and_size_must_match_original_packet(self):
        for mode in ('size','digest'):
            reader,packet,_=self.model()
            if mode=='size':packet['images'][next(iter(packet['images']))]+=1
            else:reader.groups[0][1]['raw']+=b'x'
            with patch.object(r.e.disk.p,'decode',return_value=packet),patch.object(r.e,'learner_alias',return_value='prefix'), \
                 self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'original declared image'):r.derive(reader)

    def test_metadata_requires_exact_original_generation_and_complete_reservation_events(self):
        for mode in ('manifest','packet','missing','duplicate','extra'):
            reader,packet,own=self.model()
            if mode=='manifest':own['manifest']+=b'x'
            elif mode=='packet':own['members']['source.gscp']+=b'x'
            elif mode=='missing':
                next(v for v in reader.events if v['event']=='LEARNER_SOURCE_METADATA_RESERVED')['event']='OTHER'
            elif mode=='duplicate':reader.groups.append(copy.deepcopy(reader.groups[1]))
            else:reader.events.append(dict(node='node-2',event='LEARNER_SOURCE_METADATA_RESERVED'))
            with patch.object(r.e.disk.p,'decode',return_value=packet),patch.object(r.e,'learner_alias',return_value='prefix'), \
                 patch.object(r.e,'authorize_generation'),self.subTest(mode=mode),self.assertRaises(ValueError):r.derive(reader)

    def test_original_generation_authorization_cannot_be_replaced_by_byte_match(self):
        reader,packet,_=self.model()
        with patch.object(r.e.disk.p,'decode',return_value=packet),patch.object(r.e,'learner_alias',return_value='prefix'), \
             patch.object(r.e,'authorize_generation',side_effect=ValueError('foreign original capability')), \
             self.assertRaisesRegex(ValueError,'foreign original capability'):r.derive(reader)

    def test_transfer_and_persistent_basis_uuid_must_not_collide(self):
        reader,packet,_=self.model();identifier=reader.contents[0]['offer']['request']['payload']['id']
        reader.sources=[dict(node='node-1',value=dict(basisId=identifier))]
        with patch.object(r.e.disk.p,'decode',return_value=packet),patch.object(r.e,'learner_alias',return_value='prefix'), \
             patch.object(r.e,'authorize_generation'),self.assertRaisesRegex(ValueError,'basis and transfer identity collision'):r.derive(reader)

    def test_missing_original_chunk_or_reused_transfer_identity_is_rejected(self):
        for mode in ('missing','reuse','foreign'):
            reader,packet,_=self.model()
            if mode=='missing':reader.rows.clear()
            elif mode=='reuse':reader.groups.append(copy.deepcopy(reader.groups[0]))
            else:
                reader.rows=copy.deepcopy(reader.rows)
                reader.rows[0]['request']['recipient']=dict(node='node-3')
            with patch.object(r.e.disk.p,'decode',return_value=packet),patch.object(r.e,'learner_alias',return_value='prefix'), \
                 self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'missing original chunks|reused transfer identity'):r.derive(reader)

class ReceiveFloorDerivationTest(unittest.TestCase):
    def model(self):
        from types import SimpleNamespace
        identifier=str(UUID(int=21));q=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'),
            trace='session',payload=dict(id=identifier,digest='retained-current-packet'))
        content=dict(kind='CAPSULE',raw=b'original-packet',offer=dict(request=q,sent=0,delivered=1),commit=dict(sent=3,delivered=4))
        events=[dict(node='node-1',event=name) for name in ('OFFER_SENT','OFFER_DELIVERED','CHUNK_SENT','COMMIT_SENT',
            'COMMIT_DELIVERED','FLOOR_RESERVED','FLOOR_COPY_DIRECTORY_FORCED','FLOOR_COPY_HANDED_OFF','FLOOR_RELEASE_BEFORE_RETURN')]
        remote=dict(node='node-2',manifest=b'original-manifest',members={'source.gscp':content['raw']},packet=dict(capsule='capsule'))
        return SimpleNamespace(groups=[[content]],contents=[content],events=events,
            rows=[dict(kind='CHUNK',answer='CHUNK',request=q,sent=2)],sources=[],pinned_floors=set(),
            floor_inputs=[dict(start=5,own=dict(node='node-1',start=-1),copies={'node-2':remote})])

    def derive(self,reader):
        with patch.object(r.e.disk.p,'decode',return_value=dict(images={})),patch.object(r.e,'learner_alias',return_value=None), \
             patch.object(r.e.native,'current_reference',return_value='retained-current-packet'):
            return r.derive(reader)

    def test_exact_original_remote_copy_identifies_one_receive_handoff(self):
        result=self.derive(self.model())
        self.assertEqual(1,result['floorHandoffs']);self.assertEqual(dict(forced=6,handed=7),result['transfers'][0]['floor'])

    def test_peer_scope_bytes_and_copy_handoff_inventory_cannot_be_substituted(self):
        for mode in ('peer','scope','bytes','missing-force','missing-handoff'):
            reader=self.model();content=reader.contents[0]
            if mode=='peer':reader.floor_inputs[0]['copies']['node-2']['node']='node-3'
            elif mode=='scope':content['offer']['request']['payload']['digest']='other-scope'
            elif mode=='bytes':reader.floor_inputs[0]['copies']['node-2']['members']['source.gscp']=b'other-packet'
            elif mode=='missing-force':reader.events[6]['event']='OTHER'
            else:
                # A second copy without its handoff cannot borrow the first's event.
                reader.floor_inputs[0]['copies']['node-3']=dict(reader.floor_inputs[0]['copies']['node-2'],node='node-3')
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'original floor packet|exact floor handoffs'):
                self.derive(reader)


if __name__=='__main__':unittest.main()

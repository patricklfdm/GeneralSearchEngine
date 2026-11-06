"""Conditional persistent source lifetimes; complete native qualification is separate."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID

from . import basis_resource_evidence as r,basis_resource_negatives as negatives
from .test_resource_transitions import charge
from .test_floor_resource_evidence import recount


def fixture(*,reopen=True,retired=True,marked_close=True):
    rows=[dict(event='START',removed=[],added=[])];events=[];boundaries=[];node='node-1'
    identifier=str(UUID(int=11));image=b'image';digest=r.e.sha(image);packet=b'original-packet'
    values=[charge('SOURCE',identifier,len(packet)),charge('APPLICATION',identifier+':'+digest,len(image))]
    def event(name,scope=None):
        at=len(events);events.append(dict(node=node,event=name,**({} if scope is None else dict(scope=scope))))
        boundaries.append(dict(eventIndex=at,node=node,sequence=len(rows)-1,usage={}))
        return at
    def reserve():
        for value in values:rows.append(dict(event='RESERVE',removed=[],added=[value]))
    def release():
        for value in values:rows.append(dict(event='RELEASE',removed=[value],added=[]))
    lower=event('CURRENT_BEFORE_CAPTURE');reserve();created=event('SOURCE_BEFORE_CREATE');captured=event('GRANT_CAPTURED')
    segment=dict(reserveAfter=lower,reserveBy=created,liveFrom=created,liveThrough=captured,releaseBy=None,kind='capture');segments=[segment]
    if reopen:
        segment['liveThrough']=event('LAST_OWNER_EVENT');release()
        segment['releaseBy']=event('CURRENT_VALIDATED','stable-cold-owner')
        lower=event('CURRENT_DIRECTORY_FORCED','stable-cold-owner');reserve()
        ready=event('JOINING_RETENTION_SEED_RECOVERY_FORCED','stable-cold-owner')
        segment=dict(reserveAfter=lower,reserveBy=ready,liveFrom=ready,liveThrough=ready,releaseBy=None,kind='reopen');segments.append(segment)
    segment['liveThrough']=event('SOURCE_RETIREMENT_CAPTURED' if retired else 'FIXTURE_OPEN_RETURNED');release()
    if retired or marked_close:segment['releaseBy']=event('SOURCE_RETIREMENT_CLEARED' if retired else 'FIXTURE_CLOSE_RETURNED')
    plan=dict(node=node,id=identifier,extents={r.t.key(v):v['bytes'] for v in values},segments=segments,retired=retired)
    data=([plan],events,{node:recount(rows)},boundaries);negatives.recount(data[2],data[3]);return data


class BasisResourceEvidenceTest(unittest.TestCase):
    def test_retirement_reopen_and_unmarked_shutdown_scopes(self):
        for reopen,retired,marked in ((False,True,True),(True,True,True),(True,False,True),(False,False,False)):
            with self.subTest(reopen=reopen,retired=retired,marked=marked):
                data=fixture(reopen=reopen,retired=retired,marked_close=marked);before=copy.deepcopy(data);result=r.replay(*data)
                self.assertEqual(1,result['sources']);self.assertEqual(2*(1+reopen),result['leases']);self.assertEqual(int(reopen),result['reopenedLifetimes'])
                self.assertEqual(0 if marked else 2,result['unmarkedFinalCloseLeases']);self.assertEqual(data,before)
                self.assertTrue(result['persistentBasisChargesQualified'])
                for flag in ('unmarkedShutdownPhysicalOrderQualified','otherStorageLifetimesQualified','physicalPeakQualified','wholeRuntimeResourcesQualified','phase3Complete'):
                    self.assertFalse(result[flag])

    def test_all_coherent_negatives_reject_their_own_reason(self):
        data=fixture();before=copy.deepcopy(data);result=negatives.replay(data)
        self.assertEqual(list(negatives.NEGATIVES),[v['case'] for v in result]);self.assertEqual(data,before)

    def test_observed_shutdown_requires_source_held_at_begin_and_released_by_return(self):
        for mode in ('original','early','late'):
            data=fixture(reopen=False,retired=False);segment=data[0][0]['segments'][-1];segment['closeKind']='network-owner'
            data[1][segment['liveThrough']]['event']=r.closing.BEGIN
            data[1][segment['releaseBy']]['event']=r.closing.RETURNED
            if mode=='early':data[3][segment['liveThrough']]['sequence']=3
            if mode=='late':data[3][segment['releaseBy']]['sequence']=3
            negatives.recount(data[2],data[3])
            if mode=='original':self.assertEqual(2,r.replay(*data)['observedOwnerCloseLeases'])
            else:
                reason='continuous original owner lifetime' if mode=='early' else 'exact release interval'
                with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,reason):r.replay(*data)

    def test_invalid_original_is_rejected_before_any_mutation(self):
        data=fixture();data[2]['node-1']['failed']=True
        with patch.object(negatives,'mutate') as mutate,self.assertRaisesRegex(ValueError,'incomplete observation'):negatives.replay(data)
        mutate.assert_not_called()

    def test_full_entry_requires_independent_physical_native_original(self):
        with patch.object(negatives.native.collection,'inventory',return_value={}), \
             patch.object(negatives.native,'validate',side_effect=ValueError('bad original')),patch.object(negatives.native,'load') as load:
            with self.assertRaisesRegex(ValueError,'bad original'):negatives.qualify('/unused')
        load.assert_not_called()

    def test_missing_duplicate_originals_or_event_checkpoints_are_rejected(self):
        for mode in ('empty','duplicate','missing-boundary','wrong-node','bool-index','bool-sequence','usage'):
            data=fixture();point=data[3][0]
            if mode=='empty':data[0].clear()
            elif mode=='duplicate':data[0].append(copy.deepcopy(data[0][0]))
            elif mode=='missing-boundary':data[3].pop()
            elif mode=='wrong-node':point['node']='node-2'
            elif mode=='bool-index':point['eventIndex']=False
            elif mode=='bool-sequence':point['sequence']=False
            else:point['usage']['metadata']+=1
            with self.subTest(mode=mode),self.assertRaises(ValueError):r.replay(*data)

    def test_extra_reopen_gap_is_rejected_despite_equal_boundary_totals(self):
        data=fixture(reopen=False);negatives.mutate(data,'source-lifetime-gap')
        with self.assertRaisesRegex(ValueError,'exact owner lifetime count'):r.replay(*data)

    def test_immutable_source_cannot_grow_and_shrink_between_boundaries(self):
        data=fixture();rows=data[2]['node-1']['changes'];value=rows[1]['added'][0];grown=dict(value,bytes=value['bytes']+1)
        rows[2:2]=[dict(event='STORAGE_GROW',removed=[value],added=[grown]),dict(event='RELEASE',removed=[grown],added=[]),dict(event='RESERVE',removed=[],added=[value])]
        for point in data[3]:
            if point['sequence']>1:point['sequence']+=3
        negatives.recount(data[2],data[3])
        with self.assertRaisesRegex(ValueError,'exact source release|exact original source extent'):r.replay(*data)

    def test_extents_use_original_packet_bytes_and_digest_named_images(self):
        source=dict(value=dict(basisId=str(UUID(int=11))),members={'source.gscp':b'packet',r.e.sha(b'image')+'.image':b'image'})
        packet=dict(images={r.e.sha(b'image'):5})
        with patch.object(r.e.disk.p,'decode',return_value=packet):
            self.assertEqual({('SOURCE',source['value']['basisId']):6,('APPLICATION',source['value']['basisId']+':'+r.e.sha(b'image')):5},r.extents(source))
            source['members'][r.e.sha(b'image')+'.image']=b'wrong'
            with self.assertRaisesRegex(ValueError,'original image identity'):r.extents(source)

    def test_unlisted_or_missing_original_image_is_rejected(self):
        for extra in (False,True):
            source=dict(value=dict(basisId=str(UUID(int=11))),members={'source.gscp':b'packet'})
            if extra:source['members']['extra']=b'file'
            with patch.object(r.e.disk.p,'decode',return_value=dict(images={r.e.sha(b'image'):5})), \
                 self.subTest(extra=extra),self.assertRaisesRegex(ValueError,'original member inventory'):r.extents(source)

class BasisResourceDerivationTest(unittest.TestCase):
    """Boundary extraction following conditional original admission."""
    def model(self):
        node='node-6';identifier=str(UUID(int=31));image=b'original-image';digest=r.e.sha(image)
        members={'source.gscp':b'original-packet',digest+'.image':image}
        names=[('CURRENT_VALIDATED','retaining-owner'),('CURRENT_DIRECTORY_FORCED','retaining-owner'),
               ('CURRENT_BEFORE_CAPTURE','retaining-owner'),('SOURCE_BEFORE_CREATE','retaining-owner'),
               ('GRANT_CAPTURED','retaining-owner'),('FLOOR_COPY_BEFORE_RETURN','retaining-owner'),
               ('CURRENT_VALIDATED','repeated-basis-owner'),('CURRENT_DIRECTORY_FORCED','repeated-basis-owner'),
               ('JOINING_RETENTION_SEED_RECOVERY_FORCED','repeated-basis-owner'),('CURRENT_BEFORE_CAPTURE','repeated-basis-owner'),
               ('ALLOCATOR_BEFORE_RETURN','repeated-basis-owner'),('CURRENT_VALIDATED','continuation-owner'),
               ('CURRENT_DIRECTORY_FORCED','continuation-owner'),('JOINING_RETENTION_SEED_RECOVERY_FORCED','continuation-owner'),
               ('CURRENT_VALIDATED','continuation-owner'),('CURRENT_DIRECTORY_FORCED','continuation-owner'),
               ('SOURCE_RETIREMENT_CREATED','continuation-owner'),('SOURCE_RETIREMENT_WRITTEN','continuation-owner'),
               ('SOURCE_RETIREMENT_CAPTURED','continuation-owner'),('SOURCE_RETIREMENT_DIRECTORY_DELETED','continuation-owner'),
               ('SOURCE_RETIREMENT_CAPTURED','continuation-owner'),('SOURCE_RETIREMENT_CLEARED','continuation-owner')]
        events=[dict(node=node,event=name,scope=scope) for name,scope in names]
        files={'sources/'+identifier+'/'+name:raw for name,raw in members.items()}
        source=dict(node=node,value=dict(basisId=identifier),start=4,end=16,members=members)
        transaction=dict(node=node,steps=[dict(event=16,point='SOURCE_RETIREMENT_CREATED'),
            dict(event=17,point='SOURCE_RETIREMENT_WRITTEN',files=copy.deepcopy(files)),
            dict(event=19,capturedEvent=20,point='SOURCE_RETIREMENT_DIRECTORY_DELETED'),
            dict(event=21,point='SOURCE_RETIREMENT_CLEARED')])
        reader=SimpleNamespace(root=Path('/unused'),model=SimpleNamespace(joining=node),events=events,
                               sources=[source],capture_transactions=[transaction])
        return reader,dict(images={digest:len(image)}),files

    def derive(self,reader,packet,files):
        with patch.object(r.e.disk.p,'decode',return_value=packet),patch.object(r.e.disk,'inventory',return_value=files):return r.derive(reader)

    def test_reopen_is_distinct_from_same_owner_generation_reload(self):
        reader,packet,files=self.model();result=self.derive(reader,packet,files);segments=result[0]['segments']
        self.assertEqual(3,len(segments));self.assertEqual(['capture','reopen','reopen'],[v['kind'] for v in segments])
        self.assertEqual([3,8,13],[v['reserveBy'] for v in segments])
        self.assertEqual([5,10,20],[v['liveThrough'] for v in segments]);self.assertEqual([6,11,21],[v['releaseBy'] for v in segments])
        self.assertTrue(result[0]['retired'])

    def test_old_owner_generation_validation_never_creates_reopen_intervals(self):
        reader,packet,files=self.model()
        for event in reader.events:event['node']='node-1';event.pop('scope',None)
        reader.sources[0]['node']='node-1';reader.capture_transactions[0]['node']='node-1'
        result=self.derive(reader,packet,files);segments=result[0]['segments']
        self.assertEqual(1,len(segments));self.assertEqual(20,segments[0]['liveThrough'])
        self.assertEqual(21,segments[0]['releaseBy'])

    def test_explicit_network_close_binds_unretired_source_to_actual_invocation(self):
        reader,packet,files=self.model();reader.events=reader.events[:6]
        for event in reader.events:event['node']='node-1';event.pop('scope',None)
        reader.events.extend(dict(node='node-1',event=name) for name in (r.closing.BEGIN,r.closing.RETURNED))
        reader.sources[0].update(node='node-1',end=len(reader.events));reader.capture_transactions.clear()
        result=self.derive(reader,packet,files);segment=result[0]['segments'][-1]
        self.assertEqual(6,segment['liveThrough']);self.assertEqual(7,segment['releaseBy']);self.assertEqual('network-owner',segment['closeKind'])
        # The last event is RETURNED, after release. It must never be used as
        # a boundary through which storage is still required to be charged.
        reader.events[-1]['event']='MISSING'
        with self.assertRaisesRegex(ValueError,'owner close complete pair'):self.derive(reader,packet,files)

    def test_each_joining_reopen_releases_between_actual_close_begin_and_return(self):
        from . import joining_owner_close as close
        reader,packet,files=self.model();events=[];captured=None;created=None
        for scope in close.SCOPES:
            names=['CURRENT_VALIDATED','CURRENT_DIRECTORY_FORCED','JOINING_RETENTION_SEED_RECOVERY_FORCED',close.OPEN]
            if scope=='retaining-owner':names+=['CURRENT_BEFORE_CAPTURE','SOURCE_BEFORE_CREATE','GRANT_CAPTURED']
            if scope=='stable-cold-owner':names+=['FIXTURE_OPEN_RETURNED']
            names+=[close.BEGIN,close.RETURNED]
            if scope=='stable-cold-owner':names+=['FIXTURE_CLOSE_RETURNED']
            for name in names:
                if name=='GRANT_CAPTURED':captured=len(events)
                if name=='SOURCE_BEFORE_CREATE':created=len(events)
                events.append(dict(node='node-6',scope=scope,event=name))
        reader.events=events;reader.sources[0].update(start=captured,end=len(events));reader.capture_transactions=[]
        spans=close.intervals(events,'node-6');result=self.derive(reader,packet,files);segments=result[0]['segments']
        self.assertEqual(created,segments[0]['reserveBy']);self.assertEqual(4,len(segments))
        for scope,segment in zip(close.SCOPES[1:],segments):
            self.assertEqual(spans[scope][1],segment['liveThrough']);self.assertEqual(spans[scope][2],segment['releaseBy'])
            self.assertEqual('joining-owner',segment['closeKind'])
        # Treating the previous RETURNED as a still-live boundary would falsely
        # require the old source to remain charged after the actual close.
        self.assertTrue(all(v['liveThrough']<v['releaseBy'] for v in segments))
        events[spans['retaining-owner'][2]]['event']='MISSING_RETURN'
        with self.assertRaisesRegex(ValueError,'complete ordered lifetimes'):self.derive(reader,packet,files)

    def test_reopen_must_preserve_original_source_inventory_and_bytes(self):
        for mode in ('missing','changed','extra'):
            reader,packet,files=self.model();name=next(iter(files))
            if mode=='missing':files.pop(name)
            elif mode=='changed':files[name]+=b'x'
            else:files[name+'-extra']=b'x'
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'original reopened source bytes'):self.derive(reader,packet,files)

    def test_retirement_must_name_the_exact_original_source(self):
        reader,packet,files=self.model();written=reader.capture_transactions[0]['steps'][1]['files'];name=next(iter(written));written[name]+=b'x'
        with self.assertRaisesRegex(ValueError,'original retiring source bytes'):self.derive(reader,packet,files)

    def test_missing_duplicate_retirement_and_source_creation_are_rejected(self):
        for mode in ('missing','duplicate','extra-create','duplicate-source','missing-delete','missing-clear'):
            reader,packet,files=self.model()
            if mode=='missing':reader.capture_transactions.clear()
            elif mode=='duplicate':reader.capture_transactions.append(copy.deepcopy(reader.capture_transactions[0]))
            elif mode=='extra-create':reader.events.append(dict(node='node-2',event='SOURCE_BEFORE_CREATE'))
            elif mode=='duplicate-source':reader.sources.append(copy.deepcopy(reader.sources[0]))
            elif mode=='missing-delete':reader.capture_transactions[0]['steps'].pop(2)
            else:reader.capture_transactions[0]['steps'].pop()
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.derive(reader,packet,files)

    def test_unknown_owner_scope_cannot_authorize_a_resource_gap(self):
        reader,packet,files=self.model();reader.events[14]['scope']='unbound-owner'
        with self.assertRaisesRegex(ValueError,'original reopen scope'):self.derive(reader,packet,files)

    def test_reopen_requires_both_generation_force_and_seed_recovery(self):
        for at in (7,8,12,13):
            reader,packet,files=self.model();reader.events[at]['event']='REMOVED'
            with self.subTest(at=at),self.assertRaisesRegex(ValueError,'exact original boundary'):self.derive(reader,packet,files)

    def test_stable_cold_original_requires_explicit_open_and_close_boundaries(self):
        reader,packet,files=self.model();reader.events=reader.events[:16]
        reader.events.extend(dict(node='node-6',scope='stable-cold-owner',event=name) for name in
            ('CURRENT_VALIDATED','CURRENT_DIRECTORY_FORCED','JOINING_RETENTION_SEED_RECOVERY_FORCED','FIXTURE_OPEN_RETURNED','FIXTURE_CLOSE_RETURNED'))
        reader.sources[0]['end']=len(reader.events);reader.capture_transactions.clear()
        result=self.derive(reader,packet,files);last=result[0]['segments'][-1]
        self.assertEqual(19,last['liveThrough']);self.assertEqual(20,last['releaseBy']);self.assertFalse(result[0]['retired'])
        reader.events[-1]['event']='REMOVED'
        with self.assertRaisesRegex(ValueError,'exact original boundary: FIXTURE_CLOSE_RETURNED'):self.derive(reader,packet,files)


if __name__=='__main__':unittest.main()

"""Temporal-authority boundaries; synthetic fixtures are not native evidence."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_export_evidence as e
from . import test_joining_catalog_evidence as fixture


class JoiningExportEvidenceTest(unittest.TestCase):
    def inputs(self):
        _,parent,ids,root=fixture.JoiningCatalogEvidenceTest().phase()
        schema=e.f.catalog();catalog=e.f.sample(schema['records']['CATALOG']['schema'],schema['types'])
        catalog.update(root=root,cut=parent['cut'],identities=list(ids.values()),results=[],active=None)
        encoded=e.f.encode('records','CATALOG',catalog)
        cap=dict(root=root,cut=parent['cut'],catalog=e.sha(encoded),items=[])
        image=b'original image';h=e.sha(image)
        packet=dict(capsule=cap,objects={e.sha(encoded):encoded},images={h:len(image)},capsuleBytes=b'original capsule')
        members={'source.gscp':b'original packet',h+'.image':image,'promise.gsr':b'original promise'}
        windows=[dict(node=node,start=0,end=100,identity=ids[node],packet=packet,members=copy.deepcopy(members),manifest=b'original manifest') for node in ('node-1','node-2')]
        ballot=dict(counter=2,proposer='node-1',incarnation=ids['node-1']['storage'])
        q=dict(root=root,view=e.n.s.catalog.authority(root,cap['cut']['view']),ballot=ballot,sender=ids['node-1'],recipient=ids['node-2'],trace='trace')
        return windows,q

    def values(self,q,expected,start=10):
        return [dict(kind=kind,raw=raw,offer=dict(sent=start+4*i-1,received=start+4*i,offered=start+4*i+1,
                       request=dict(q,payload={'digest':reference})),commit={'offered':start+4*i+3})
                for i,(reference,raw,kind) in enumerate(expected)]

    def source(self):
        windows,q=self.inputs();own=windows[1]
        source=dict(node='node-2',start=1,end=90,basis=b'basis',promise=b'promise',
                    value=dict(view=q['view'],ballot=q['ballot']),packet=own['packet'],members=own['members'])
        expected=[(e.sha(source['basis']),source['basis'],'RECORD'),(e.sha(source['promise']),source['promise'],'RECORD'),
                  (e.sha(source['packet']['capsuleBytes']),source['members']['source.gscp'],'CAPSULE')]
        return windows,q,source,self.values(q,expected)

    def test_current_generation_is_exactly_one_time_interval_not_an_ever_seen_pool(self):
        windows,q=self.inputs();self.assertEqual(windows[1],e.current(windows,'node-2',10,20))
        for start,end in ((0,20),(10,100),(99,101)):
            with self.assertRaisesRegex(ValueError,'^joining export inactive current generation$'):e.current(windows,'node-2',start,end)
        with self.assertRaisesRegex(ValueError,'^joining export inactive current generation$'):e.current(windows+[windows[1]],'node-2',10,20)

    def test_generation_alias_and_all_original_metadata_are_required(self):
        windows,q=self.inputs();own=windows[1]
        expected=e.native.maintenance_generations(own['manifest'],own['members'],own['packet'])[1]
        values=self.values(q,expected);self.assertEqual('current-generation',e.authorize_generation(values,windows))
        changed=copy.deepcopy(values);changed[0]['offer']['request']['payload']['digest']='f'*64
        with self.assertRaisesRegex(ValueError,'^joining export current generation alias$'):e.authorize_generation(changed,windows)
        with self.assertRaisesRegex(ValueError,'^joining export exact current generation$'):e.authorize_generation(values[:-1],windows)

    def test_old_generation_manifest_cannot_be_relabelled_as_current_bytes(self):
        windows,q=self.inputs();own=windows[1];expected=e.native.maintenance_generations(own['manifest'],own['members'],own['packet'])[1]
        values=self.values(q,expected);values[0]['raw']=b'older manifest'
        with self.assertRaisesRegex(ValueError,'^joining export exact current generation$'):e.authorize_generation(values,windows)

    def test_prefix_correlation_cannot_invent_a_proposer_storage_identity(self):
        windows,q=self.inputs();own=windows[1]
        values=self.values(q,e.native.maintenance_generations(own['manifest'],own['members'],own['packet'])[1])
        values[0]['offer']['request']['ballot']=dict(q['ballot'],incarnation='00000000-0000-0000-0000-000000000099')
        with self.assertRaisesRegex(ValueError,'^joining export current permanent identities$'):e.authorize_generation(values,windows)

    def test_fresh_local_promise_revokes_live_capability_before_selector_replacement(self):
        events=[dict(node='node-2',event='other') for _ in range(10)]
        events[2]['event']=events[6]['event']='PROMISE_FORCED'
        events[4]=dict(node='node-1',event='PROMISE_FORCED')
        self.assertEqual(6,e.next_promise(events,'node-2',3,9))
        self.assertEqual(5,e.next_promise(events,'node-2',3,5))
        self.assertEqual(9,e.next_promise(events,'node-2',6,9))

    def test_source_cannot_be_used_before_capture_or_after_retirement(self):
        windows,q,source,values=self.source();e.authorize_source(values,windows,[source])
        for start,end in ((10,90),(1,values[-1]['commit']['offered'])):
            changed=dict(source,start=start,end=end)
            with self.assertRaisesRegex(ValueError,'^joining export inactive frozen source$'):e.authorize_source(values,windows,[changed])

    def test_source_bytes_require_the_original_owner_and_basis_alias(self):
        windows,q,source,values=self.source()
        for changed in ([dict(source,node='node-1')],[],[source,source]):
            with self.assertRaisesRegex(ValueError,'^joining export original source alias$'):e.authorize_source(values,windows,changed)
        values[1]['raw']=b'foreign promise'
        with self.assertRaisesRegex(ValueError,'^joining export exact frozen source$'):e.authorize_source(values,windows,[source])

    def test_source_transfer_cannot_borrow_an_image_missing_from_receiver(self):
        windows,q,source,values=self.source()
        name=next(k for k in windows[0]['members'] if k.endswith('.image'));del windows[0]['members'][name]
        with self.assertRaisesRegex(ValueError,'^joining export exact frozen source$'):e.authorize_source(values,windows,[source])

    def test_source_request_requires_original_ballot_and_current_view(self):
        windows,q,source,values=self.source();values[0]['offer']['request']['view']='f'*64
        with self.assertRaisesRegex(ValueError,'^joining export original source view/ballot$'):e.authorize_source(values,windows,[source])

    def test_empty_ancestry_is_not_a_malformed_frame(self):
        windows,q=self.inputs();self.assertEqual({},e.current_records(windows[1]))

    def test_unused_packet_ack_cannot_become_published_checkpoint_authority(self):
        windows,q=self.inputs();own=windows[1]
        schema=e.f.catalog();ack=e.f.encode('records','CHECKPOINT_ACK',e.f.sample(schema['records']['CHECKPOINT_ACK']['schema'],schema['types']))
        own['packet']['objects'][e.sha(ack)]=ack
        self.assertNotIn(e.sha(ack),e.current_records(own))

    def test_live_vote_receipt_cannot_use_another_ballot(self):
        windows,q=self.inputs();raw=b'original vote receipt';reference='d'*64
        records=[dict(node='node-2',start=1,end=50,reference=reference,raw=raw,ballot=q['ballot'],view=q['view'],family='native-vote-receipt')]
        values=self.values(q,[(reference,raw,'RECORD')]);self.assertEqual('native-vote-receipt',e.authorize_record(values,windows,records))
        values[0]['offer']['request']['ballot']=dict(q['ballot'],counter=3)
        with self.assertRaisesRegex(ValueError,'^joining export exact live record$'):e.authorize_record(values,windows,records)

    def test_record_is_unavailable_after_its_owner_capability_ends(self):
        windows,q=self.inputs();raw=b'checkpoint';reference=e.sha(raw)
        records=[dict(node='node-2',start=1,end=13,reference=reference,raw=raw,ballot=None,view=None,family='native-applied-checkpoint')]
        with self.assertRaisesRegex(ValueError,'^joining export unavailable original record$'):e.authorize_record(self.values(q,[(reference,raw,'RECORD')]),windows,records)

    def completed(self):
        windows,q=self.inputs();raw=b'original completed checkpoint';reference=e.sha(raw)
        q['view']='e'*64
        record=dict(node='node-2',start=1,end=50,reference=reference,raw=raw,
                    ballot=q['ballot'],view=q['view'],family='published-local-checkpoint')
        return windows,q,record,self.values(q,[(reference,raw,'RECORD')])

    def test_completed_checkpoint_old_view_requires_original_local_capability(self):
        windows,q,record,values=self.completed()
        with patch.object(e,'current_records',return_value={record['reference']:record['raw']}):
            self.assertEqual('published-local-checkpoint',e.authorize_record(values,windows,[record]))
            for change in (dict(family='journal'),dict(node='node-1'),dict(ballot=dict(q['ballot'],counter=3)),dict(end=13)):
                with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining export record original context$'):
                    e.authorize_record(values,windows,[dict(record,**change)])

    def test_completed_checkpoint_must_still_be_authenticated_and_exact(self):
        windows,q,record,values=self.completed()
        with patch.object(e,'current_records',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining export record original context$'):e.authorize_record(values,windows,[record])
        values[0]['raw']=b'another voter checkpoint'
        with patch.object(e,'current_records',return_value={record['reference']:record['raw']}):
            with self.assertRaisesRegex(ValueError,'^joining export exact completed checkpoint$'):e.authorize_record(values,windows,[record])

    def pending(self):
        windows,q=self.inputs();identities=e.f.decode(windows[0]['packet']['objects'][windows[0]['packet']['capsule']['catalog']],'records','CATALOG')['identities']
        joining=next(v for v in identities if v['node']=='node-4')
        q['recipient']=joining;raw=b'original pending ACK';values=self.values(q,[(e.sha(raw),raw,'RECORD')])
        events=[dict(node='node-4',scope='pending-intent',event='other') for _ in range(20)]
        for at,point in ((1,'LEARNER_JOINING_ACK_FORCED'),(2,'LEARNER_JOINING_ACK_PARENT_FORCED'),
                         (3,'LEARNER_JOINING_ACK_BEFORE_RETURN'),(15,'LEARNER_JOINING_RETAIN_CREATED')):
            events[at]['event']=point
        events[10]['scope']='pending-listener'
        model=SimpleNamespace(joining='node-4',phases=[{'SELECTED':b'selected'}]*9,states=[dict(identities=identities,cut=dict(view=dict(old=['node-1','node-2']))) for _ in range(10)])
        return q,raw,values,events,model

    def test_pending_checkpoint_requires_forced_parent_completed_return_and_live_pending_owner(self):
        q,raw,values,events,model=self.pending()
        with patch.object(e,'pending_ack',return_value=raw),patch.object(e.f,'decode',return_value=dict(view=q['view'],ballot=q['ballot'])):
            e.authorize_pending(values,events,model)
            for position,reason in ((1,'durability'),(2,'durability'),(3,'lifetime')):
                changed=copy.deepcopy(events);changed[position]['event']='missing'
                with self.subTest(position=position),self.assertRaisesRegex(ValueError,'^joining export pending ACK '+reason+'$'):
                    e.authorize_pending(values,changed,model)
            late=copy.deepcopy(values);late[0]['commit']['offered']=15
            with self.assertRaisesRegex(ValueError,'^joining export pending ACK lifetime$'):e.authorize_pending(late,events,model)
            events[10]['scope']='native-owner'
            with self.assertRaisesRegex(ValueError,'^joining export pending ACK original scope$'):e.authorize_pending(values,events,model)

    def test_invalid_original_does_not_generate_negative_successes(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify('/unused')
            copied.assert_not_called()

    def test_negative_must_preserve_every_physical_file_and_directory(self):
        original=dict(files={'original.gsr':'digest'},directories=['directory'])
        for changed in (dict(files={'original.gsr':'altered'},directories=['directory']),dict(files=original['files'],directories=[])):
            with patch.object(e,'validate',return_value={}),patch.object(e.n.s.collection,'inventory',side_effect=[original,changed]), \
                    patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e.n,'network') as network:
                with self.assertRaisesRegex(ValueError,'^joining export negative changed physical inputs$'):e.qualify('/unused')
                network.assert_not_called()

    def test_broken_transcript_cannot_count_as_authority_rejection(self):
        with patch.object(e,'validate',return_value={}),patch.object(e.n.s.collection,'inventory',return_value=dict(files={},directories=[])), \
                patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e.n,'network',side_effect=ValueError('broken transcript')),patch.object(e,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^broken transcript$'):e.qualify('/unused')
            replay.assert_not_called()

    def test_accepted_or_unrelated_negative_cannot_count_as_success(self):
        for failure,reason in ((None,'joining export mutation accepted: generation-alias'),
                               (ValueError('unrelated'),'joining unrelated export negative: generation-alias: unrelated')):
            with patch.object(e,'validate',return_value={}),patch.object(e.n.s.collection,'inventory',return_value=dict(files={},directories=[])), \
                    patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e.n,'network'),patch.object(e,'replay',side_effect=failure):
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):e.qualify('/unused')

    def test_physical_and_network_precondition_failure_stops_authorization(self):
        with patch.object(e.n.s.collection,'inventory',return_value={}),patch.object(e.n,'validate',side_effect=ValueError('invalid original')),patch.object(e,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.validate('/unused')
            replay.assert_not_called()

    def test_replay_must_preserve_original_inventory(self):
        with patch.object(e.n.s.collection,'inventory',side_effect=[{}, {'changed':1}]),patch.object(e.n,'validate'),patch.object(e,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining export original changed$'):e.validate('/unused')


if __name__=='__main__':unittest.main()

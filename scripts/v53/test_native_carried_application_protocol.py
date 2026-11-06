import copy
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from . import native_carried_application_protocol as m
from .test_native_carried_transition_physical import sample


class NativeCarriedApplicationProtocolTest(unittest.TestCase):
    def floor(self):
        manifest=sample('GENERATION');manifest.update(node='node-1',generation='a')
        raw=m.f.encode('records','GENERATION',manifest);digest=m.e.digest(raw)
        selector=m.f.encode('records','SELECTOR',dict(root=manifest['root'],node='node-1',generation='a',digest=digest))
        peer=m.f.encode('records','GENERATION',dict(manifest,node='node-2'));peer_hash=m.e.digest(peer)
        floor=sample('FLOOR');floor.update(root=manifest['root'],node='node-1',sources=[dict(voter=node,
            generation=value,catalog=manifest['catalog'],snapshot=manifest['application'])
            for node,value in (('node-1',digest),('node-2',peer_hash))])
        return {digest:{'generation.gsr':raw,'image.image':b'image'},
                peer_hash:{'generation.gsr':peer,'image.image':b'peer image'}},m.f.encode('records','FLOOR',floor),selector

    def test_pin_keeps_local_original_and_force_positions_before_proposal(self):
        copies,raw,selector=self.floor();before=copy.deepcopy(copies)
        rows,files,writes,dirs=m.forces.floor.transaction(copies,raw,handoff=True,local_selector=selector)
        self.assertEqual(['FLOOR_RESERVED','FLOOR_DIRECTORY_CREATED','FLOOR_LOCAL_ORIGINAL_FORCED',
            'FLOOR_LOCAL_SELECTOR_WRITTEN','FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED',
            'FLOOR_PROPOSAL_WRITTEN'],[v['event'] for v in rows[:7]])
        self.assertEqual(3,writes['floor-copies/local.gsr']);self.assertEqual(selector,files['floor-copies/local.gsr'])
        self.assertEqual(1,dirs['floor-copies']);self.assertEqual(2,len(dirs))
        local=m.f.decode(selector,'records','SELECTOR')['digest']
        self.assertFalse(any(n.startswith('floor-copies/'+local) for n in files))
        self.assertEqual(1,sum(n.endswith('.image') for n in files))
        self.assertEqual(before,copies)
        default=m.forces.floor.transaction(copies,raw,handoff=True)
        self.assertTrue(any(n.endswith('.image') for n in default[1]));self.assertNotIn('floor-copies/local.gsr',default[1])

    def test_pin_cannot_substitute_owner_digest_or_generation(self):
        copies,raw,selector=self.floor();value=m.f.decode(selector,'records','SELECTOR')
        for field,new in (('node','node-2'),('digest','f'*64),('generation','b')):
            altered=m.f.encode('records','SELECTOR',dict(value,**{field:new}))
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'floor exact'):
                m.forces.floor.transaction(copies,raw,local_selector=altered)
        changed=copy.deepcopy(copies);changed[value['digest']]['generation.gsr']=m.f.encode('records','GENERATION',
            dict(m.f.decode(changed[value['digest']]['generation.gsr'],'records','GENERATION'),node='node-2'))
        with self.assertRaisesRegex(ValueError,'floor exact pinned original'):
            m.forces.floor.transaction(changed,raw,local_selector=selector)

    def test_release_pin_does_not_delete_original_generation(self):
        files={'generations/a':None,'generations/a/original.image':b'original','floor-copies':None,
            'floor-copies/local.gsr':b'selector','floor-copies/proposal.gsr':b'floor','floor-copies/floor.gsr':b'floor'}
        before=m.forces.retirement.s.physical(files);steps=m.forces.release.transaction(before,b'authority')
        names=[point for point,_ in steps]
        self.assertLess(names.index('FLOOR_RELEASE_PROPOSAL_CLEARED'),names.index('FLOOR_RELEASE_LOCAL_CLEARED'))
        self.assertLess(names.index('FLOOR_RELEASE_LOCAL_CLEARED'),names.index('FLOOR_RELEASE_AUTHORITY_CLEARED'))
        self.assertEqual({k:v for k,v in before.items() if k.startswith('generations/')},steps[-1][1])
        self.assertTrue(all(state['generations/a/original.image']==before['generations/a/original.image'] for _,state in steps))

    def test_staged_owner_cannot_enter_maintenance(self):
        with patch.object(m.forces,'maintenance') as maintenance:
            self.assertEqual(([],dict(generations=0,sources=0,borrowed=0)),m.maintenance({'node-1':{'applied-end':None}},'node-1'))
            maintenance.assert_not_called()

    def test_three_sources_three_copies_pin_but_two_sources_do_not(self):
        for count,pin in ((2,False),(3,True)):
            files={'generations/a/manifest':b'current','generations/b/manifest':b'inactive'}
            files.update({'sources/'+str(i)+'/source.gscp':b'source' for i in range(count)})
            with patch.object(m.c,'current',return_value=('generations/a/',{'selected.gsr':b'selected'},{})),\
                 patch.object(m.p,'needs_maintenance',return_value=True),patch.object(m.p.floors,'floor_voters',return_value=('node-1','node-2','node-3')),\
                 patch.object(m.forces,'maintenance',return_value=([],{})) as maintenance:
                m.maintenance({'node-1':files},'node-1',campaign=True)
                maintenance.assert_called_once_with({'node-1':files},'node-1',pin_current=pin,campaign=True)

    def retire(self,events):
        files={'applied-end':None,'applied-end/ack.gsr':b'old ACK','selector.gsr':b'new selector'}
        clean={'selector.gsr':b'new selector'}
        cleanup=['STAGED_RETIREMENT_AUTHORITY_VALIDATED','SUPERSEDED_END_VALIDATED','STAGED_RETIREMENT_BEFORE_RETURN']
        with patch.object(m.p.data,'pending',return_value=({'ENTRY':b'entry','PAYLOAD':b'payload'},())),\
             patch.object(m.application,'retire',return_value=clean),patch.object(m.retirement,'authority',return_value=b'marker'),\
             patch.object(m.retirement.staging,'cleanup',return_value=(clean,cleanup)),\
             patch.object(m.forces.replay_files,'retirement',return_value=[('replay','REPLAY_BEFORE_RETURN',{})]):
            return m.retired([dict(node='node-1',event=v) for v in events],{'node-1':files})

    def original_prefix(self):
        return ['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED','NATIVE_RETIREMENT_CERTIFICATE_RETAINED',
            'STAGED_RETIREMENT_AUTHORITY_VALIDATED','REPLAY_BEFORE_RETURN','SUPERSEDED_END_VALIDATED','STAGED_RETIREMENT_BEFORE_RETURN']

    def test_only_fully_validated_retirement_prefix_can_be_removed(self):
        prefix=self.original_prefix();rows,files=self.retire(prefix+['ACCEPT_VALIDATED'])
        self.assertEqual([dict(node='node-1',event='ACCEPT_VALIDATED')],rows)
        self.assertEqual({'node-1':{'selector.gsr':b'new selector'}},files)
        for at in range(len(prefix)):
            for changed in (prefix[:at]+prefix[at+1:],prefix[:at]+[prefix[at]]+prefix[at:]):
                with self.subTest(at=at),self.assertRaises(ValueError):self.retire(changed+['ACCEPT_VALIDATED'])

    def test_old_ack_and_early_new_vote_cannot_be_hidden_by_projection(self):
        prefix=self.original_prefix()
        with self.assertRaisesRegex(ValueError,'emitted old ACK'):self.retire(prefix[:-1]+['APPLY_ACK_DIRECTORY_FORCED']+prefix[-1:])
        with self.assertRaisesRegex(ValueError,'exact retirement before new vote'):self.retire(prefix[:-1]+['ACCEPT_VALIDATED']+prefix[-1:])
        with self.assertRaisesRegex(ValueError,'unexpected retirement'):self.retire(prefix+['SUPERSEDED_END_VALIDATED'])

    def test_interleaved_socket_observation_survives_retirement_projection(self):
        prefix=self.original_prefix()
        for at in range(len(prefix)):
            rows,_=self.retire(prefix[:at]+['NETWORK_RECEIVED']+prefix[at:]+['ACCEPT_VALIDATED'])
            self.assertEqual(['NETWORK_RECEIVED','ACCEPT_VALIDATED'],[v['event'] for v in rows])

    def test_retirement_outside_slot_or_cold_open_is_rejected(self):
        rows=[dict(node='node-1',event='SUPERSEDED_END_FILE_DELETED'),dict(node='node-1',event='NODE_OPEN')]
        with self.assertRaisesRegex(ValueError,'unexpected retirement'):m.cold(rows,{'node-1':{}})
        with self.assertRaisesRegex(ValueError,'unexpected retirement'):m.campaign(rows,{}, {})

    def test_optional_adapter_cannot_claim_unimplemented_transient_coverage(self):
        with self.assertRaisesRegex(ValueError,'transient collectors unsupported'):
            m.slot([],{},None,{},first=True,unknown_prefixes=[])

    def test_bad_original_cannot_produce_negative_credit(self):
        with patch.object(m.p.process.collection,'inventory',return_value={}),patch.object(m,'validate',side_effect=ValueError('bad original')),\
             patch.object(m.shutil,'copytree') as copytree:
            with self.assertRaisesRegex(ValueError,'bad original'):m.qualify('/original')
            copytree.assert_not_called()

    def test_original_storage_cannot_be_mutated_for_protocol_negative_credit(self):
        first=dict(files={'pending.accept':'old'},directories=[]);second=dict(files={'pending.accept':'changed'},directories=[])
        with patch.object(m.p.process.collection,'inventory',side_effect=[first,second]),patch.object(m,'validate',return_value={}),\
             patch.object(m,'NEGATIVES',{'one':'reason'}),patch.object(m,'mutate'),patch.object(m.shutil,'copytree'),\
             patch.object(m,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'negative changed original storage'):m.qualify('/original')
            replay.assert_not_called()

    def test_original_change_during_replay_is_rejected(self):
        with patch.object(m.p.process.collection,'inventory',side_effect=[{},dict(changed=True)]),\
             patch.object(m.application,'validate',return_value=dict(physical=dict(kind='FINAL'))),patch.object(m,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original')

    def test_unrelated_failure_or_accepted_mutation_cannot_earn_negative_credit(self):
        inventory=dict(files={'pending.accept':'original'},directories=[])
        original=dict(original=dict(physical=dict(kind='FINAL')))
        for failure,reason in ((ValueError('unrelated'), 'wrong negative'),(None,'accepted negative')):
            with patch.object(m.p.process.collection,'inventory',return_value=inventory),patch.object(m,'validate',return_value=original),\
                 patch.object(m,'NEGATIVES',{'one':'expected'}),patch.object(m,'mutate'),patch.object(m.shutil,'copytree'),\
                 patch.object(m.p.process,'validate_application') as process,patch.object(m,'replay',side_effect=failure):
                with self.assertRaisesRegex(ValueError,reason):m.qualify('/original')
                process.assert_called_once()

    def test_network_projection_preserves_indices_and_unrelated_delivery(self):
        rows=[dict(node='node-1',event=event) for event in ('ROUND_INSTALLED','ROUND_SLOT_BEGIN',
            'OLD_CERTIFICATE','NETWORK_RECEIVED','NEW_ACCEPT','ROUND_SLOT_COMPLETE')]
        history=SimpleNamespace(ranges=[dict(kind='slot',before='original',start=0,stop=5)])
        with patch.object(m.forces,'group',return_value={}),\
             patch.object(m,'retired',return_value=(rows[3:5],{})) as retired:
            result=m.slot_projection(Path('/original'),history,rows)
            retired.assert_called_once_with(rows[2:5],{})
            self.assertEqual(len(rows),len(result))
            self.assertEqual(dict(event='VALIDATED_OLD_APPLICATION_RETIREMENT'),result[2])
            for index in (0,1,3,4,5):self.assertIs(rows[index],result[index])
        with patch.object(m.forces,'group',return_value={}),patch.object(m,'retired',side_effect=ValueError('bad retirement')):
            with self.assertRaisesRegex(ValueError,'bad retirement'):m.slot_projection(Path('/original'),history,rows)


if __name__=='__main__':unittest.main()

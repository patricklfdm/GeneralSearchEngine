"""Force-oracle refusal boundaries; complete histories are replayed separately."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import native_carried_transition_forces as m
from . import test_native_carried_transition_physical as fixtures


class NativeCarriedTransitionForcesTest(unittest.TestCase):
    def successor(self,mutation=None):
        files,members,packet,entry,payload,selected=fixtures.NativeCarriedTransitionPhysicalTest().command()
        packet['capsule']['root']=selected['root']
        value=dict(root=selected['root'],authority=selected['view'],ballot=selected['ballot'],
                   index=selected['cut']['index']+1,entry=m.e.digest(entry))
        accept=m.f.encode('records','ACCEPT',value);old=m.f.encode('records','ACCEPT',dict(value,ballot=dict(value['ballot'],counter=8)))
        source=dict(objects={m.e.digest(old):old,m.e.digest(entry):entry,m.e.digest(payload):payload})
        packet['objects'][m.e.digest(old)]=old
        frames=dict(SELECTOR=files['selector.gsr'],PROMISE=members['promise.gsr'],SELECTED=members['selected.gsr'],
                    ENTRY=entry,PAYLOAD=payload,ACCEPT=accept)
        if mutation in ('SELECTOR','PROMISE','SELECTED'):frames[mutation]=b'foreign original'
        elif mutation=='ballot':frames['ACCEPT']=old
        elif mutation in ('tail','entry','payload'):
            key={'tail':m.e.digest(old),'entry':m.e.digest(entry),'payload':m.e.digest(payload)}[mutation]
            packet['objects'].pop(key)
        elif mutation=='no-vote':frames={}
        with patch.object(m.p.data,'pending',return_value=(frames,())),patch.object(m.c,'current',return_value=('generations/a/',members,packet)):
            m.successors(source,m.e.digest(old),files,'node-1',packet['capsule'])

    def test_unresolved_tail_requires_exact_transferred_vote_and_all_retained_bytes(self):
        self.successor()
        for mutation in ('SELECTOR','PROMISE','SELECTED','ballot','no-vote'):
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'exact source successor'):self.successor(mutation)
        for mutation in ('tail','entry','payload'):
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'retained source tail'):self.successor(mutation)

    def test_source_tail_below_floor_still_requires_exact_published_floor(self):
        catalog=m.f.catalog();value=m.f.sample(catalog['records']['ACCEPT']['schema'],catalog['types'])
        value.update(root='a'*64,index=5);raw=m.f.encode('records','ACCEPT',value)
        cap=dict(root='a'*64,cut=dict(index=5));floor=m.f.sample(catalog['records']['FLOOR']['schema'],catalog['types'])
        floor.update(root=cap['root'],node='node-1');cap['cut']=floor['cut'];cap['cut']['index']=5
        files={'floor-copies/floor.gsr':m.f.encode('records','FLOOR',floor)}
        m.successors(dict(objects={m.e.digest(raw):raw}),m.e.digest(raw),files,'node-1',cap)
        with self.assertRaisesRegex(ValueError,'uncovered source tail'):
            m.successors(dict(objects={m.e.digest(raw):raw}),m.e.digest(raw),files,'node-2',cap)

    def test_ack_can_repeat_only_after_complete_original_vote_force(self):
        for phase in ('ACCEPT','PROOF'):
            original=m.vote_events(phase);ack=phase+'_ACK_BEFORE_RETURN'
            m.vote_order(original+[ack,ack],phase,ack=True)
            for index in range(len(original)):
                missing=original[:index]+original[index+1:]+[ack]
                early=original[:index]+[ack]+original[index:]
                duplicated=original[:index]+[original[index]]+original[index:]+[ack]
                for changed in (missing,early,duplicated):
                    with self.assertRaisesRegex(ValueError,'write and ACK'):m.vote_order(changed,phase,ack=True)
            with self.assertRaisesRegex(ValueError,'write and ACK'):m.vote_order(original,phase,ack=True)

    def test_cold_vote_recovery_cannot_be_inserted_inside_a_fresh_slot(self):
        for phase in ('ACCEPT','PROOF'):
            for point in ('ACTIVE_FORCED','ACTIVE_PARENT_FORCED'):
                original=m.vote_events(phase)
                for index in range(len(original)+1):
                    with self.assertRaisesRegex(ValueError,'write and ACK'):
                        m.vote_order(original[:index]+[phase+'_'+point]+original[index:],phase)

    def test_rename_prefix_cannot_imply_parent_force_or_return(self):
        for phase in ('ACCEPT','PROOF'):
            prefix=m.vote_events(phase,renamed=True);m.vote_order(prefix,phase,renamed=True)
            for point in ('PARENT_FORCED','BEFORE_RETURN','ACK_BEFORE_RETURN'):
                with self.assertRaisesRegex(ValueError,'write and ACK'):
                    m.vote_order(prefix+[phase+'_'+point],phase,renamed=True)

    def test_peer_ledger_revision_delta_requires_each_complete_write(self):
        expected=['RETENTION_'+v for v in m.LEDGER]*2
        rows=[dict(node='node-1',event=v) for v in expected]
        decode=lambda raw:dict(revision=7 if raw==b'before' else 9)
        with patch.object(m.d.s.r,'decode',side_effect=decode):
            m.ledger_order(rows,'node-1',b'before',b'after')
            for index in range(len(rows)):
                for changed in (rows[:index]+rows[index+1:],rows[:index]+[copy.deepcopy(rows[index])]+rows[index:]):
                    with self.assertRaisesRegex(ValueError,'exact peer ledger writes'):m.ledger_order(changed,'node-1',b'before',b'after')

    def test_original_is_required_before_any_negative_copy(self):
        with patch.object(m.process.collection,'inventory',return_value={}),patch.object(m,'validate',side_effect=ValueError('bad original')),\
                patch.object(m.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^bad original$'):m.qualify('/original')
            copied.assert_not_called()

    def test_force_mutation_cannot_change_original_storage_to_manufacture_rejection(self):
        before=dict(files={'pending.accept':'a'},directories=[]);after=dict(files={'pending.accept':'b'},directories=[])
        with patch.object(m.process.collection,'inventory',side_effect=[before,after]),patch.object(m,'validate',return_value={}) as validate,\
                patch.object(m,'NEGATIVES',{'one':'expected refusal'}),patch.object(m.shutil,'copytree'),patch.object(m,'mutate'):
            with self.assertRaisesRegex(ValueError,'negative changed original storage'):m.qualify('/original')
            validate.assert_called_once_with(Path('/original'))

    def test_original_change_during_replay_cannot_pass(self):
        with patch.object(m.process.collection,'inventory',side_effect=[{},dict(changed=True)]),\
                patch.object(m.p,'validate',return_value=dict(physical=dict(kind='FINAL',cut='PROOF_RENAMED'))),patch.object(m,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original')

    def test_vote_mutation_preserves_cold_transfer_and_targets_the_actual_slot(self):
        for name in ('accept-force','proof-force','certificate-force'):
            point=m.OMISSIONS[name][0]
            event=lambda p:dict(action='event',value=dict(node='node-1',incarnation=2,event=p))
            lives=[[],[event(point),event('NODE_OPEN'),event('ROUND_SLOT_BEGIN'),event(point)]]
            with patch.object(m.native,'rewrite_lives',side_effect=lambda root,edit:edit(lives)):m.mutate('/original',name)
            self.assertEqual([point,'NODE_OPEN','ROUND_SLOT_BEGIN'],[v['value']['event'] for v in lives[1]])

    def test_early_ack_mutation_stays_after_cold_recovery(self):
        event=lambda p:dict(action='event',value=dict(node='node-2',incarnation=2,event=p))
        points=['ACCEPT_PARENT_FORCED','NODE_OPEN','ROUND_SLOT_BEGIN','ACCEPT_PARENT_FORCED','ACCEPT_ACK_BEFORE_RETURN']
        lives=[[],[event(point) for point in points]]
        with patch.object(m.native,'rewrite_lives',side_effect=lambda root,edit:edit(lives)):m.mutate('/original','early-accept-ack')
        self.assertEqual(points[:3]+['ACCEPT_ACK_BEFORE_RETURN','ACCEPT_PARENT_FORCED'],[v['value']['event'] for v in lives[1]])


if __name__=='__main__':unittest.main()

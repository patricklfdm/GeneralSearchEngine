"""Force-oracle refusal boundaries; complete histories are replayed separately."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import native_carried_transition_forces as m
from . import test_native_carried_transition_physical as fixtures


class NativeCarriedTransitionForcesTest(unittest.TestCase):
    def test_floor_creation_keeps_the_original_ledger_until_post_floor_reconciliation(self):
        rows,files,writes,dirs=m.floor.transaction({'aa':{'generation.gsr':b'a','00.image':b'image'}},b'floor')
        initial={'root.gsr':b'root',m.d.s.FILE:b'projected later view'}
        steps=m.floor_steps(initial,rows,files,writes,dirs,peer_ledger=b'original preceding view')
        original=dict(bytes=len(b'original preceding view'),sha256=m.e.digest(b'original preceding view'))
        self.assertTrue(all(state[m.d.s.FILE]==original for _,state in steps))
        self.assertEqual(b'projected later view',initial[m.d.s.FILE])
        default=m.floor_steps(initial,rows,files,writes,dirs)
        self.assertNotEqual(default[-1][1][m.d.s.FILE],steps[-1][1][m.d.s.FILE])

    def test_floor_prefixes_preserve_original_files_and_publish_after_complete_copies(self):
        copies={'aa':{'generation.gsr':b'a','source.gscp':b's','00.image':b'i'},'bb':{'generation.gsr':b'b','11.image':b'j'}}
        rows,files,writes,dirs=m.floor.transaction(copies,b'floor')
        initial={'root.gsr':b'root','grants.gsr':b'journal'};steps=m.floor_steps(initial,rows,files,writes,dirs)
        self.assertEqual(m.retirement.s.physical(initial),steps[0][1]);self.assertNotIn('floor-copies',steps[0][1])
        for at,(point,state) in enumerate(steps):
            self.assertEqual(m.retirement.s.physical(initial)['grants.gsr'],state['grants.gsr'])
            if point.endswith('_FORCED') and rows[at-1]['event']==point.removesuffix('_FORCED')+'_WRITTEN':
                self.assertEqual(steps[at-1][1],state)
            for name,index in writes.items():self.assertEqual(index<=at,name in state)
            for name,index in dirs.items():self.assertEqual(index<=at,name in state)
        self.assertEqual(m.retirement.s.physical(dict(initial,**files,**{v:None for v in dirs})),steps[-1][1])

    def test_floor_callback_binding_excludes_copy_discovery_but_requires_all_release_events(self):
        names=['FLOOR_COPY_BEFORE_RETURN','FLOOR_RESERVED','FLOOR_COPY_HANDED_OFF','FLOOR_BEFORE_RETURN',
               'FLOOR_RELEASE_AUTHORITY_CREATED','FLOOR_RELEASE_BEFORE_RETURN','RETIREMENT_OLD_FILES_FORCED']
        rows=[dict(node='node-1',event=v) for v in names]
        plan=[('floor-release' if v.startswith('FLOOR_RELEASE_') else 'floor',v,{}) for v in names[1:-1]];actual=[]
        m.bind_prefixes(rows,'node-1',plan,actual,floors=True);self.assertEqual(names[1:-1],[v[0]['event'] for v in actual])
        with self.assertRaisesRegex(ValueError,'complete retirement prefix count'):m.bind_prefixes(rows[:-2]+rows[-1:],'node-1',plan,[],floors=True)

    def test_prefix_binding_keeps_original_rows_and_excludes_other_nodes(self):
        row=dict(node='node-1',event='RETIREMENT_CREATED',incarnation=2);state={'root.gsr':dict(bytes=4,sha256='a'*64)};result=[]
        m.bind_prefixes([dict(row,node='node-2'),dict(row,event='WIRE_RESPONSE'),row],'node-1',[('generation','RETIREMENT_CREATED',state)],result)
        self.assertIs(row,result[0][0]);self.assertIs(state,result[0][2])
        self.assertEqual('generation',result[0][1])

    def test_prefix_binding_cannot_omit_duplicate_or_reorder_original_callbacks(self):
        rows=[dict(node='node-1',event=v) for v in ('RETIREMENT_CREATED','RETIREMENT_PROPOSAL_WRITTEN')]
        plan=[('generation',v['event'],{}) for v in rows]
        for actual in (rows[:1],rows+rows[:1]):
            with self.assertRaisesRegex(ValueError,'^transition forces complete retirement prefix count$'):m.bind_prefixes(actual,'node-1',plan,[])
        with self.assertRaisesRegex(ValueError,'^transition forces original retirement prefix boundary$'):m.bind_prefixes(list(reversed(rows)),'node-1',plan,[])
        # Existing callers without a capture sidecar retain their exact receipt.
        m.bind_prefixes(rows,'node-1',None,None)

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

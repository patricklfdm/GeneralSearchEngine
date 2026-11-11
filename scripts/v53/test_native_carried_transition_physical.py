"""Boundary checks; retained native originals supply the complete byte replay."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import native_carried_transition_physical as m


def sample(kind):
    catalog=m.f.catalog()
    return m.f.sample(catalog['records'][kind]['schema'],catalog['types'])


class NativeCarriedTransitionPhysicalTest(unittest.TestCase):
    def test_checkpoint_endorsements_come_only_from_original_selected_voters(self):
        slot=m.NativeSlot.__new__(m.NativeSlot);slot.voters=('node-1','node-3','node-4')
        view=dict(old=['node-1','node-2','node-3','node-4'],new=['node-1','node-2','node-3','node-4'])
        self.assertEqual(set(slot.voters),slot.checkpoint_voters(view,'node-1'))
        view=dict(old=view['old'],new=['node-1','node-3','node-4'])
        self.assertEqual(set(slot.voters),slot.checkpoint_voters(view,'node-3'))
        view=dict(old=['node-1','node-3'],new=['node-1','node-3'])
        self.assertEqual({'node-1','node-3'},slot.checkpoint_voters(view,'node-4'))

    def command(self,kind='INTENT'):
        selected=sample('SELECTED');selected['ballot']['counter']=9
        entry=sample('ENTRY');payload=b'original command'
        entry.update(kind=kind,root=selected['root'],authority=selected['view'],
                     index=selected['cut']['index']+1,previous=selected['cut']['entry'],payload=m.e.digest(payload))
        entry['origin']['counter']=8;raw=m.f.encode('records','ENTRY',entry);selected['nextEntry']=m.e.digest(raw)
        members={'promise.gsr':b'current promise','selected.gsr':m.f.encode('records','SELECTED',selected)}
        packet=dict(capsule=dict(cut=selected['cut']),objects={m.e.digest(raw):raw,m.e.digest(payload):payload})
        return {'selector.gsr':b'current selector'},members,packet,raw,payload,selected

    def test_reaccept_preserves_original_entry_and_uses_new_selection_ballot(self):
        for kind in m.t.KINDS:
            files,members,packet,entry,payload,selected=self.command(kind)
            with patch.object(m.c,'current',return_value=('generations/a/',members,packet)):
                raw=m.vote(files,entry,payload)
            accept=m.f.encode('records','ACCEPT',dict(root=selected['root'],authority=selected['view'],
                ballot=selected['ballot'],index=selected['cut']['index']+1,entry=m.e.digest(entry)))
            expected=m.e.container([files['selector.gsr'],members['promise.gsr'],members['selected.gsr'],entry,accept],payload)
            self.assertEqual(expected,raw)
            self.assertNotEqual(selected['ballot'],m.f.decode(entry,'records','ENTRY')['origin'])

    def test_reaccept_rejects_changed_kind_cut_identity_or_payload(self):
        for field,value in [('kind','DATA'),('kind','BARRIER'),('root','f'*64),('authority','f'*64),
                            ('previous','f'*64),('index',99),('payload','f'*64)]:
            files,members,packet,entry,payload,selected=self.command()
            changed=m.f.encode('records','ENTRY',dict(m.f.decode(entry,'records','ENTRY'),**{field:value}))
            # Rebinding nextEntry alone cannot make an unrelated command valid.
            members['selected.gsr']=m.f.encode('records','SELECTED',dict(selected,nextEntry=m.e.digest(changed)))
            with self.subTest(field=field,value=value),patch.object(m.c,'current',return_value=('generations/a/',members,packet)):
                with self.assertRaisesRegex(ValueError,'exact successor vote'):m.vote(files,changed,payload)

    def test_cold_open_preserves_current_proof_but_transfers_old_vote_without_proof(self):
        files,members,packet,entry,payload,_=self.command('FINAL');files['pending.accept']=b'original proven vote'
        current=dict(SELECTOR=files['selector.gsr'],ENTRY=entry,PAYLOAD=payload,PROOF=b'old proof')
        group={'node-1':files};before=copy.deepcopy(group)
        with patch.object(m.data,'pending',return_value=(current,('PROOF',))),patch.object(m.c,'current',return_value=('generations/a/',members,packet)):
            self.assertEqual(group,m.cold(group,entry,payload))
            with patch.object(m.data,'pending',return_value=(dict(current,SELECTOR=b'older selector'),('PROOF',))):
                result=m.cold(group,entry,payload)
                self.assertEqual(m.vote(files,entry,payload),result['node-1']['pending.accept'])
                self.assertNotIn(b'old proof',result['node-1']['pending.accept'])
        self.assertEqual(before,group)

    def test_cold_open_cannot_replace_application_work_or_unretained_command(self):
        files,members,packet,entry,payload,_=self.command()
        for staging in ('applied-end','applied-end/ack.gsr'):
            with self.assertRaisesRegex(ValueError,'cold staged application'):
                m.cold({'node-1':dict(files,**{staging:b'original'})},entry,payload)
        frames=dict(SELECTOR=b'old',ENTRY=entry,PAYLOAD=payload)
        for digest in (m.e.digest(entry),m.e.digest(payload)):
            missing=copy.deepcopy(packet);missing['objects'].pop(digest)
            with patch.object(m.data,'pending',return_value=(frames,())),patch.object(m.c,'current',return_value=('generations/a/',members,missing)):
                with self.assertRaisesRegex(ValueError,'cold retained command'):m.cold({'node-1':files},entry,payload)

    def test_campaign_requires_both_governing_majorities_before_reading_snapshots(self):
        view=dict(old=['node-1','node-2','node-3','node-4'],new=['node-1','node-2','node-3'],operation=1)
        for nodes in (['node-1','node-2'],['node-1','node-4'],['node-1','node-2','node-5'],['node-2','node-3','node-4']):
            selected=sample('SELECTED');source=selected['sources'][0]
            selected['sources']=[dict(source,voter=node) for node in nodes]
            raw=m.f.encode('records','SELECTED',selected)
            with self.subTest(nodes=nodes),patch.object(Path,'read_bytes',return_value=raw),\
                    patch.object(m.c,'current',return_value=(None,None,dict(capsule=dict(cut=dict(view=view))))),\
                    patch.object(m.c,'inventory') as inventory:
                with self.assertRaisesRegex(ValueError,'original selected cohort|both governing majorities'):
                    m.campaign(Path('unused'),dict.fromkeys(view['old'],{}),1,1,3,b'original')
                inventory.assert_not_called()

    def test_fresh_barrier_is_new_but_carried_entry_cannot_be_rewritten(self):
        _,_,_,entry,_,_=self.command();fields=m.f.decode(entry,'records','ENTRY')
        walk=m.NativeSlot.__new__(m.NativeSlot);walk.old_index=fields['index'];walk.carried_entry=entry
        successor=dict(fields,origin=dict(fields['origin'],counter=9))
        self.assertEqual(entry,walk.entry_bytes(successor))
        for changed in (fields,dict(successor,payload='f'*64),dict(successor,authority='f'*64)):
            with self.assertRaisesRegex(ValueError,'unchanged inherited entry'):walk.entry_bytes(changed)
        barrier=dict(successor,index=fields['index']+1,kind='BARRIER',payload=m.e.digest(b''))
        self.assertEqual(m.f.encode('records','ENTRY',barrier),walk.entry_bytes(barrier))

    def test_invalid_original_cannot_supply_negative_credit(self):
        with patch.object(m.process.collection,'inventory',return_value={}),\
                patch.object(m,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(m.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):m.qualify('/original')
            validate.assert_called_once_with(Path('/original'));copied.assert_not_called()

    def test_accepted_or_unrelated_negative_cannot_pass_qualification(self):
        original=dict(physical=dict(kind='FINAL'))
        for result in (original,ValueError('unrelated failure')):
            with patch.object(m.process.collection,'inventory',return_value={}),patch.object(m,'validate',side_effect=[original,result]),\
                    patch.object(m,'negative_cases',return_value={'one':'expected rejection'}),\
                    patch.object(m.shutil,'copytree'),patch.object(m,'mutate'):
                with self.assertRaisesRegex(ValueError,'physical (accepted negative|wrong negative)'):m.qualify('/original')

    def test_original_change_between_readers_is_rejected(self):
        with patch.object(m.process.collection,'inventory',side_effect=[{},dict(changed=True)]),\
                patch.object(m.process,'validate',return_value=dict(kind='FINAL',cut='PROOF_RENAMED')),\
                patch.object(m,'physical',return_value={}):
            with self.assertRaisesRegex(ValueError,'physical original changed'):m.validate('/original')


if __name__=='__main__':unittest.main()

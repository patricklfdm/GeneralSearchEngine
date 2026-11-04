from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import carried_transition_evidence as m


class CarriedTransitionEvidenceTest(unittest.TestCase):
    def test_invalid_original_precedes_all_mutations(self):
        for kind in m.KINDS:
            with patch.object(m,'validate',side_effect=ValueError('original failed')) as original,patch.object(m.shutil,'copytree') as copied:
                with self.assertRaisesRegex(ValueError,'^original failed$'):m.qualify('/original',kind)
                original.assert_called_once_with(Path('/original'),kind);copied.assert_not_called()

    def test_declared_transition_scope_and_complete_slots(self):
        self.assertEqual((5,3,('INTENT','FINAL','BARRIER')),(m.shape('INTENT')[0],m.shape('INTENT')[1],tuple(v[0] for v in m.shape('INTENT')[2])))
        self.assertEqual((6,2,('FINAL','BARRIER')),(m.shape('FINAL')[0],m.shape('FINAL')[1],tuple(v[0] for v in m.shape('FINAL')[2])))
        for kind in ('DATA','BARRIER','CONTROL','',None,True):
            with patch.object(m,'layout') as layout,self.assertRaisesRegex(ValueError,'exact kind'):m.validate('/unused',kind)
            layout.assert_not_called()

    def test_linked_original_refuses_before_physical_reduction(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'actual').write_bytes(b'original');(root/'link').symlink_to('actual')
            with patch.object(m,'prelude') as prelude,self.assertRaisesRegex(ValueError,'regular original'):m.validate(root,'INTENT')
            prelude.assert_not_called()

    def service(self,kind):
        catalog=m.f.catalog();fields=m.f.sample(catalog['records']['ENTRY']['schema'],catalog['types'])
        fields.update(index=m.shape(kind)[0],kind=kind)
        service=m.NativeSlot.__new__(m.NativeSlot);service.old_index=fields['index'];service.carried_entry=m.f.encode('records','ENTRY',fields)
        return service,fields

    def test_carried_entry_only_changes_the_accept_ballot(self):
        for kind in m.KINDS:
            service,fields=self.service(kind);new=dict(fields,origin=dict(fields['origin'],counter=fields['origin']['counter']+1))
            self.assertEqual(service.carried_entry,service.entry_bytes(new))
            for key,value in (('payload','0'*64),('previous','0'*64),('kind','BARRIER'),('authority','0'*64),('root','0'*64)):
                with self.subTest(kind=kind,key=key),self.assertRaisesRegex(ValueError,'exact inherited command'):service.entry_bytes(dict(new,**{key:value}))
            with self.assertRaisesRegex(ValueError,'exact inherited command'):service.entry_bytes(fields)

    def test_fresh_barrier_uses_fresh_fields(self):
        service,fields=self.service('FINAL');fields.update(index=7,kind='BARRIER',payload=m.e.digest(b''))
        self.assertEqual(m.f.encode('records','ENTRY',fields),service.entry_bytes(fields))

    def test_current_floor_projection_follows_first_reaccept_only(self):
        service,_=self.service('INTENT');service.slot=5;service.voters=('node-1','node-2','node-3');service.group={'original':'before'}
        accepted={'original':'accepted'};projected={'original':'retained'}
        with patch.object(m.current,'maintenance',return_value=projected) as floor,patch.object(m.t.NativeSlot,'snapshot') as snapshot:
            service.snapshot('slot-5-accepted',accepted)
            floor.assert_called_once_with(accepted,service.voters,after_accept=True);self.assertIs(projected,service.group)
            snapshot.assert_called_once_with('slot-5-accepted',accepted)
            floor.reset_mock();service.snapshot('slot-5-proved',accepted);service.slot=6;service.snapshot('slot-6-accepted',accepted)
            floor.assert_not_called()

    def test_scope_cannot_promote_partial_history_or_boolean_numbers(self):
        for kind in m.KINDS:
            index,count,_=m.shape(kind);entry=b'original';expected=dict(status='PASS',kind=kind,oldIndex=index,oldEntry=m.e.digest(entry),
                activations=count,internalReady=True,publicReady=False,originalBudgetSeconds=600)
            for key,value in (('publicReady',True),('internalReady',1),('activations',True),('oldIndex',True),('originalBudgetSeconds',180),('phase3Complete',True)):
                with tempfile.TemporaryDirectory() as temp:
                    root=Path(temp);(root/'carried-transition-result.json').write_text(json.dumps(dict(expected,**{key:value})))
                    with patch.object(m,'layout'),patch.object(m,'prelude',return_value=(None,entry,b'')),self.assertRaisesRegex(ValueError,'^carried transition scope$'):
                        m.validate(root,kind)

    def test_same_negative_name_cannot_hide_a_different_failure(self):
        for failure in (None,ValueError('unrelated original failure')):
            with patch.object(m,'validate',side_effect=[{'status':'PASS'},failure] if failure else [{'status':'PASS'},{'status':'PASS'}]),\
                 patch.object(m,'negative_cases',return_value={'one':'expected rejection'}),patch.object(m.shutil,'copytree'),patch.object(m,'mutate'):
                with self.assertRaisesRegex(ValueError,'unrelated negative|mutation accepted'):m.qualify('/original','INTENT')

    def test_complete_negative_vectors_keep_exact_reason_and_kind(self):
        for kind in m.KINDS:
            cases=m.negative_cases(kind);self.assertEqual(30,len(cases))
            self.assertIn(str(m.shape(kind)[0]),cases['new-ballot-vote'])
            with patch.object(m,'validate',side_effect=[{'status':'PASS'},*[ValueError(v) for v in cases.values()]]),\
                 patch.object(m.shutil,'copytree'),patch.object(m,'mutate') as mutation:
                result=m.qualify('/original',kind)
            self.assertEqual([{'case':k,'status':'REJECTED','reason':v} for k,v in cases.items()],result['negatives'])
            self.assertEqual(list(cases),[v.args[2] for v in mutation.call_args_list])
            self.assertTrue(all(v.args[1]==kind for v in mutation.call_args_list))

    def test_missing_activation_and_early_ready_refuse_before_event_payloads(self):
        for kind in m.KINDS:
            count=m.shape(kind)[1];names=['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE']*count+['BEFORE_READY']
            missing=names.copy();missing.pop(3);early=names.copy();early.insert(3,early.pop())
            for invalid in (missing,early):
                with patch.object(m.lifecycle.d,'read',return_value=[dict(event='ROUND_'+name) for name in invalid]),\
                     self.assertRaisesRegex(ValueError,'exact lifecycle'):m.lifecycle.lifecycle(Path('/original'),carried=kind)


if __name__=='__main__':unittest.main()

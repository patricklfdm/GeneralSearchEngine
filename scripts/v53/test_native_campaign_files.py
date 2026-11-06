import unittest
from unittest.mock import patch
from . import native_campaign_files as m


class NativeCampaignFilesTest(unittest.TestCase):
    def fixture(self,node='node-1',selected=True):
        root='a'*64;identifier='00000000-0000-0000-0000-000000000020'
        old=m.f.encode('records','ALLOCATOR',dict(root=root,node=node,counter=1))
        new=m.f.encode('records','ALLOCATOR',dict(root=root,node=node,counter=2)) if node=='node-1' else old
        selector=lambda generation:m.f.encode('records','SELECTOR',dict(root=root,node=node,generation=generation,digest='b'*64))
        initial={'root.gsr':bytes(16)+bytes.fromhex(root),'allocator.gsr':old,'grants.gsr':b'old-journal',
                 'selector.gsr':selector('a'),'sources':None,'generations':None,'generations/a':None,
                 'generations/a/generation.gsr':b'old generation',m.LEDGER:b'old ledger','pending.accept':b'original vote'}
        promise=b'original-promise';basis=b'original-basis';chosen=b'original-selected'
        prefix='sources/'+identifier
        final=dict(initial,**{'allocator.gsr':new,'grants.gsr':initial['grants.gsr']+promise+basis,
            prefix:None,prefix+'/source.gscp':b'original source packet',prefix+'/00.image':b'original image'})
        if selected:final.update({'grants.gsr':final['grants.gsr']+chosen,'generations/b':None,'generations/b/generation.gsr':b'new generation',
            'generations/b/basis.gsr':basis,'generations/b/00.image':b'original image','selector.gsr':selector('b'),m.LEDGER:b'merged ledger'})
        prior=[('PROMISE',b'old-journal',{})]
        rows=[*prior,('PROMISE',promise,dict(ballot=dict(counter=2))),('BASIS',basis,dict(basisId=identifier))]
        if selected:rows.append(('SELECTED',chosen,{}))
        return initial,final,prior,rows

    def run_plan(self,node='node-1',selected=True,change=None):
        before,after,prior,rows=self.fixture(node,selected)
        if change:change(before,after)
        with patch.object(m.g,'journal',side_effect=[prior,rows]):steps=m.transaction(before,after,node,selected)
        return before,after,steps

    def at(self,steps,point):return next(state for _,name,state in steps if name==point)
    def identity(self,raw):return m.physical({'file':raw})['file']

    def test_original_files_and_full_projection_survive_every_stage(self):
        before,after,steps=self.run_plan()
        self.assertEqual(m.physical(before),steps[0][2]);self.assertEqual(m.physical(after),steps[-1][2])
        self.assertEqual({'allocator','grant','selected','install'},{kind for kind,_,_ in steps})
        for _,_,state in steps:self.assertEqual(self.identity(before['pending.accept']),state['pending.accept'])

    def test_allocator_keeps_old_active_until_exact_rename(self):
        before,after,steps=self.run_plan()
        self.assertEqual(self.identity(b''),self.at(steps,'ALLOCATOR_CREATED')['allocator.pending.gsr'])
        for point in ('ALLOCATOR_CREATED','ALLOCATOR_WRITTEN','ALLOCATOR_FORCED'):
            self.assertEqual(self.identity(before['allocator.gsr']),self.at(steps,point)['allocator.gsr'])
        self.assertEqual(self.identity(after['allocator.gsr']),self.at(steps,'ALLOCATOR_RENAMED')['allocator.gsr'])
        self.assertNotIn('allocator.pending.gsr',self.at(steps,'ALLOCATOR_RENAMED'))

    def test_intent_has_exact_original_selector_promise_basis_and_half_prefix(self):
        before,_,steps=self.run_plan();raw=before['selector.gsr']+b'original-promiseoriginal-basis'
        self.assertEqual(self.identity(b''),self.at(steps,'CAPTURE_INTENT_CREATED')['source.capture.gsr'])
        self.assertEqual(self.identity(raw[:len(raw)//2]),self.at(steps,'CAPTURE_INTENT_PREFIX_WRITTEN')['source.capture.gsr'])
        self.assertEqual(self.identity(raw),self.at(steps,'CAPTURE_INTENT_FORCED')['source.capture.gsr'])
        self.assertIn('source.capture.gsr',self.at(steps,'BASIS_FORCED'))
        self.assertNotIn('source.capture.gsr',self.at(steps,'CAPTURE_INTENT_DELETED'))

    def test_source_packet_and_image_are_empty_then_half_then_whole(self):
        _,after,steps=self.run_plan()
        for point,suffix in (('SOURCE_PACKET','/source.gscp'),('SOURCE_IMAGE','/00.image')):
            key=next(k for k in after if k.startswith('sources/') and k.endswith(suffix));raw=after[key]
            for ending,wanted in (('CREATED',b''),('PREFIX_WRITTEN',raw[:len(raw)//2]),('WRITTEN',raw),('FORCED',raw)):
                self.assertEqual(self.identity(wanted),self.at(steps,point+'_'+ending)[key])

    def test_basis_prefix_and_selection_extend_the_existing_original_journal(self):
        before,_,steps=self.run_plan();prefix=before['grants.gsr']+b'original-promise';basis=b'original-basis'
        self.assertEqual(self.identity(prefix+basis[:len(basis)//2]),self.at(steps,'BASIS_PREFIX_WRITTEN')['grants.gsr'])
        self.assertEqual(self.identity(prefix+basis),self.at(steps,'SELECTED_BEFORE_WRITE')['grants.gsr'])
        self.assertEqual(self.identity(prefix+basis+b'original-selected'),self.at(steps,'SELECTED_WRITTEN')['grants.gsr'])

    def test_installation_publishes_selector_after_members_and_merges_ledger_after_parent_force(self):
        before,after,steps=self.run_plan()
        self.assertNotIn('generations/b',self.at(steps,'INSTALL_RESERVED'))
        self.assertIn('generations/b',self.at(steps,'INSTALL_DIRECTORY_CREATED'))
        self.assertNotIn('generations/b/basis.gsr',self.at(steps,'INSTALL_MANIFEST_WRITTEN'))
        self.assertEqual(self.identity(before['selector.gsr']),self.at(steps,'INSTALL_SELECTOR_FORCED')['selector.gsr'])
        self.assertEqual(self.identity(after['selector.gsr']),self.at(steps,'INSTALL_SELECTOR_RENAMED')['selector.gsr'])
        self.assertNotIn('selector.pending.gsr',self.at(steps,'INSTALL_SELECTOR_RENAMED'))
        self.assertEqual(self.identity(before[m.LEDGER]),self.at(steps,'INSTALL_PARENT_FORCED')[m.LEDGER])
        self.assertEqual(self.identity(after[m.LEDGER]),self.at(steps,'INSTALL_BEFORE_RETURN')[m.LEDGER])

    def test_nonselected_remote_voter_only_writes_the_original_grant(self):
        _,after,steps=self.run_plan('node-3',False)
        self.assertEqual({'grant'},{kind for kind,_,_ in steps});self.assertEqual(m.physical(after),steps[-1][2])

    def test_unknown_final_files_and_changed_nontransaction_authority_reject(self):
        for change in (lambda before,after:after.update(unobserved=b'file'),lambda before,after:after.update({'pending.accept':b'changed vote'})):
            with self.assertRaisesRegex(ValueError,'^campaign prefix complete installed projection$'):self.run_plan(change=change)

    def test_install_callbacks_are_owned_by_the_same_selected_transaction(self):
        row=lambda node,point:dict(node=node,event=point)
        rows=[row('node-1','INSTALL_RESERVED'),row('node-1','SELECTED_BEFORE_WRITE'),row('node-1','SELECTED_BEFORE_RETURN'),
              row('node-2','INSTALL_RESERVED'),row('node-1','INSTALL_RESERVED'),row('node-1','INSTALL_BEFORE_RETURN'),row('node-1','INSTALL_RESERVED')]
        self.assertEqual([1,2,4,5],[at for at,_,_ in m.observed(rows)])
        for missing in (rows[:4],rows[:3]+[row('node-1','SELECTED_BEFORE_WRITE')]):
            with self.assertRaisesRegex(ValueError,'campaign prefix'):m.observed(missing)

    def test_each_selected_owner_must_complete_its_own_installation(self):
        rows=[dict(node=node,event=point) for node,point in [('node-1','SELECTED_BEFORE_RETURN'),('node-2','SELECTED_BEFORE_RETURN'),('node-1','INSTALL_BEFORE_RETURN')]]
        with self.assertRaisesRegex(ValueError,'^campaign prefix selected installation missing$'):m.observed(rows)
        rows.append(dict(node='node-2',event='INSTALL_BEFORE_RETURN'));self.assertEqual(4,len(m.observed(rows)))


if __name__=='__main__':unittest.main()

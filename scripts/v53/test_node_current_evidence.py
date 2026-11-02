from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import node_current_evidence as m


class NodeCurrentEvidenceTest(unittest.TestCase):
    def sample(self, kind):
        schema=m.f.catalog();return m.f.sample(schema['records'][kind]['schema'],schema['types'])

    def vote(self, *, changed=None, proof=False):
        selected=self.sample('SELECTED');selected['nextEntry']=None
        cap=dict(root=selected['root'],cut=selected['cut'])
        entry=self.sample('ENTRY');entry.update(root=selected['root'],authority=selected['view'],
            index=selected['cut']['index']+1,payload=m.e.digest(b'payload'))
        accept=dict(root=selected['root'],authority=selected['view'],ballot=selected['ballot'],
            index=entry['index'],entry=m.e.digest(m.f.encode('records','ENTRY',entry)))
        if changed:accept.update(changed)
        members={'promise.gsr':m.f.encode('records','PROMISE',self.sample('PROMISE')),
                 'selected.gsr':m.f.encode('records','SELECTED',selected)}
        selector=m.f.encode('records','SELECTOR',self.sample('SELECTOR'))
        vote=m.e.container([selector,members['promise.gsr'],members['selected.gsr'],
            m.f.encode('records','ENTRY',entry),m.f.encode('records','ACCEPT',accept)],b'payload')
        if proof:
            extra=m.f.encode('records','PROOF',self.sample('PROOF'));vote=vote[:8]+(len(vote)+len(extra)).to_bytes(4,'big')+vote[12:]+extra
        files={'selector.gsr':selector,'pending.accept':vote,'grants.gsr':b'original-journal',
            'sources/old':None,'sources/old/source.gscp':b'original-source',m.n.s.FILE:b'original-ledger'}
        return files,members,dict(capsule=cap)

    def test_current_reaccept_keeps_owned_sources_and_pending_bytes(self):
        files,members,packet=self.vote();before=deepcopy(files)
        projected={'pending.accept':m.c.EMPTY,'grants.gsr':b'pruned',m.n.s.FILE:b'observed'}
        with patch.object(m.c,'current',return_value=('generations/a/',members,packet)), \
                patch.object(m.current,'maintenance',return_value={'node-1':projected}) as project:
            result=m.maintenance({'node-1':files},('node-1',),after_accept=True)['node-1']
        self.assertEqual(before,files)
        self.assertEqual(m.c.EMPTY,project.call_args.args[0]['node-1']['pending.accept'])
        for name in ('pending.accept','grants.gsr','sources/old','sources/old/source.gscp'):
            self.assertEqual(files[name],result[name])
        self.assertEqual(b'observed',result[m.n.s.FILE])

    def test_old_pending_vote_does_not_authorize_maintenance(self):
        files,_,_=self.vote(proof=True);group={'node-1':files}
        with patch.object(m.current,'maintenance') as project:
            self.assertEqual(group,m.maintenance(group,('node-1',)));project.assert_not_called()

    def test_proof_cannot_be_erased_to_claim_new_accept(self):
        files,members,packet=self.vote(proof=True)
        with patch.object(m.c,'current',return_value=('generations/a/',members,packet)),patch.object(m.current,'maintenance') as project:
            with self.assertRaisesRegex(ValueError,'carried payload/extent'):
                m.maintenance({'node-1':files},('node-1',),after_accept=True)
            project.assert_not_called()

    def test_reaccepted_record_binds_current_ballot_index_and_entry(self):
        files,members,packet=self.vote();selected=m.f.decode(members['selected.gsr'],'records','SELECTED')
        for fields in (dict(ballot=dict(selected['ballot'],counter=selected['ballot']['counter']+1)),
                       dict(index=999),dict(entry='0'*64)):
            files,members,packet=self.vote(changed=fields)
            with self.subTest(fields=fields),patch.object(m.c,'current',return_value=('generations/a/',members,packet)), \
                    patch.object(m.current,'maintenance') as project:
                with self.assertRaisesRegex(ValueError,'current node exact reaccepted vote'):
                    m.maintenance({'node-1':files},('node-1',),after_accept=True)
                project.assert_not_called()

    def test_half_pending_cohort_uses_complete_floor_without_retiring_pending_owner(self):
        files,_,_=self.vote()
        group={'node-1':files,'node-2':dict(files,**{'pending.accept':m.c.EMPTY})};before=deepcopy(group)
        projected={'node-1':{'invalid':'must not replace this owner'},'node-2':{'new':'derived bytes'}}
        with patch.object(m.current,'maintenance',return_value=projected) as project:
            result=m.maintenance(group,('node-1','node-2'))
        project.assert_called_once_with(before,('node-1','node-2'),owners=['node-2'])
        self.assertEqual(before['node-1'],result['node-1']);self.assertEqual(projected['node-2'],result['node-2'])
        self.assertEqual(before,group)

    def test_half_pending_cohort_propagates_failed_covering_floor(self):
        files,_,_=self.vote()
        with patch.object(m.current,'maintenance',side_effect=ValueError('joining same-view exact covering ancestor')):
            with self.assertRaisesRegex(ValueError,'exact covering ancestor'):
                m.maintenance({'node-1':files,'node-2':dict(files,**{'pending.accept':m.c.EMPTY})},('node-1','node-2'))

    def test_unselected_grant_identity_is_only_a_fresh_suffix_and_selected_stays_exact(self):
        service=m.Service.__new__(m.Service);ballot=dict(counter=4)
        prior=[('PROMISE',b'old',dict(ballot=dict(counter=3),basisId='old'))]
        suffix=[('PROMISE',b'new',dict(ballot=ballot,basisId='new')),('BASIS',b'basis',dict(ballot=ballot,basisId='new'))]
        self.assertEqual('new',service.grant_identifier(prior,suffix,ballot,False))
        for rows in (suffix[::-1],suffix+suffix[:1],suffix[:1],
                     [('PROMISE',b'other',dict(ballot=dict(counter=5),basisId='new')),suffix[1]]):
            with self.subTest(rows=rows),self.assertRaisesRegex(ValueError,'unselected fresh grant suffix'):
                service.grant_identifier(prior,rows,ballot,False)
        with self.assertRaisesRegex(ValueError,'exact grant history'):
            service.grant_identifier(prior,suffix,ballot,True)
        legacy=m.p.p.Service.__new__(m.p.p.Service)
        with self.assertRaisesRegex(ValueError,'exact grant history'):
            legacy.grant_identifier(prior,suffix,ballot,False)

    def same_cut_grant(self,*,accepted=None,old_cut=0,current_promise=b'current',current_basis=b'current-basis',covered=True,extra_accepted=False):
        service=m.Service.__new__(m.Service);cap=dict(root='root',cut=dict(index=0))
        files={'pending.accept':m.c.EMPTY,'grants.gsr':b'journal','sources/old/source.gscp':b'old-source'}
        members={'promise.gsr':current_promise,'basis.gsr':current_basis}
        rows=[('PROMISE',b'old',dict(ballot=dict(counter=3),basisId='old')),
              ('BASIS',b'old-basis',dict(basisId='old',cut=dict(index=old_cut),accepted=accepted)),
              ('PROMISE',b'fresh',dict(ballot=dict(counter=4),basisId='fresh'))]
        if extra_accepted:
            files['sources/pending/source.gscp']=b'pending-source'
            rows[:0]=[('PROMISE',b'pending',dict(ballot=dict(counter=2),basisId='pending')),
                      ('BASIS',b'pending-basis',dict(basisId='pending',cut=dict(index=0),accepted='unresolved-tail'))]
        group={'node-1':{'original':'covering peer'},'node-3':{'original':'pre-grant'}}
        with patch.object(m.c,'current',return_value=('generations/a/',members,dict(capsule=cap))), \
                patch.object(m.c,'journal',return_value=rows), \
                patch.object(m,'floor_voters',return_value=('node-3','node-1')) as floor, \
                patch.object(m.current,'maintenance',return_value={'node-3':{'derived':'retired'}},
                    side_effect=None if covered else ValueError('joining same-view exact covering ancestor')) as project:
            result=service.after_grant(group,'node-3',files)
        return result,files,group,floor,project

    def test_same_cut_unselected_source_retires_only_after_complete_floor(self):
        result,files,group,floor,project=self.same_cut_grant()
        copies=dict(group,**{'node-3':files})
        floor.assert_called_once_with(copies,'node-3')
        project.assert_called_once_with(copies,('node-3','node-1'),owners=('node-3',))
        self.assertEqual({'derived':'retired'},result)
        with self.assertRaisesRegex(ValueError,'exact covering ancestor'):self.same_cut_grant(covered=False)

    def test_grant_keeps_accepted_other_cut_and_current_source_owned(self):
        for options in (dict(accepted='retained vote'),dict(old_cut=1),dict(current_promise=b'old'),dict(current_basis=b'old-basis')):
            with self.subTest(options=options):
                result,files,group,floor,project=self.same_cut_grant(**options)
                self.assertIs(result,files);floor.assert_not_called();project.assert_not_called()

    def test_unaccepted_source_cannot_authorize_retirement_of_another_accepted_tail(self):
        with self.assertRaisesRegex(ValueError,'same-cut retirement accepted tail'):
            self.same_cut_grant(extra_accepted=True)

    def test_invalid_original_precedes_negative_generation(self):
        with patch.object(m,'validate',side_effect=ValueError('invalid original')),patch.object(m.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):m.qualify('unused')
            copied.assert_not_called()

    def test_current_mode_does_not_guess_from_old_cut_name(self):
        with patch.object(m.p.p,'inventory') as inventory:
            for point in (*m.p.CUTS,'UNKNOWN',None):
                with self.assertRaisesRegex(ValueError,'rename scope'):m.physical('unused',point)
            inventory.assert_not_called()

    def test_reconciliation_barrier_does_not_invent_a_second_document(self):
        service=m.Service.__new__(m.Service)
        for slot,count in ((0,0),(1,0),(2,1),(3,1),(4,1),(5,2)):
            service.slot=slot
            self.assertEqual([(i,'node-owner-'+str(i)) for i in range(100,100+count)],service.data_documents())

    def test_new_negative_contract_preserves_all_rename_negatives(self):
        for point in m.p.RENAME_CUTS:
            cases=m.p.negative_cases(point)|m.EXTRA_NEGATIVES
            self.assertEqual(34,len(cases));self.assertTrue(set(m.p.NEGATIVES)<=set(cases))

    def test_default_owner_hooks_keep_historical_projection(self):
        service=m.p.p.Service.__new__(m.p.p.Service);group={'old':'bytes'};voters=('node-1','node-2')
        with patch.object(m.p.p.p.t,'maintenance',return_value='legacy') as project:
            self.assertEqual('legacy',service.maintenance(group,voters,after_accept=True))
            project.assert_called_once_with(group,voters)
        with patch.object(m.n.s,'merged',return_value=b'legacy') as merge:
            self.assertEqual(b'legacy',service.merge_peers(b'before',[b'source']))
            merge.assert_called_once_with(b'before',[b'source'])
        self.assertEqual(b'',service.installation_ancestry({},None,[]))

    def test_force_mutations_keep_child_and_merged_events_identical(self):
        for name,event,life in [('genesis-ledger-write','RETIREMENT_AUTHORITY_FORCED',1),
                               ('missing-source-retirement-force','SOURCE_RETIREMENT_FORCED',2),
                               ('missing-selected-retention-force','RETENTION_FORCED',2)]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'history').mkdir();(root/'process').mkdir()
                events=[dict(node='node-1',incarnation=life,event='BEFORE'),dict(node='node-1',incarnation=life,event=event),
                        dict(node='node-1',incarnation=life,event='AFTER')]
                (root/'history/events.json').write_bytes(m.f.canonical(events))
                child=[dict(action='event',value=v) for v in events]
                child.insert(1,dict(action='snapshot',value='before'))
                path=root/f'process/life-{life}.jsonl';path.write_bytes(b'\n'.join(m.f.canonical(v) for v in child)+b'\n')
                m.mutate(root,name);changed=m.p.process.transcript(path)
                self.assertEqual(m.n.read(root/'history/events.json'),[v['value'] for v in changed if v['action']=='event'])
                self.assertEqual(child[1],changed[1])


if __name__=='__main__':unittest.main()

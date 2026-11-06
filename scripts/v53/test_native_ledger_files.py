import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import native_ledger_files as m


class NativeLedgerFilesTest(unittest.TestCase):
    def initial(self):
        return {'root.gsr':b'root','retained':None,'retained/image':b'image',
                m.FILES['peer'][0]:b'p'*50,m.FILES['future'][0]:b'f'*50}

    def test_half_candidate_keeps_old_active_until_rename_and_preserves_other_files(self):
        for kind,(active,candidate) in m.FILES.items():
            initial=self.initial();before=initial[active];after=b'next original revision'*3
            steps=m.transaction(m.physical(initial),before,after,kind)
            self.assertEqual(7,len(steps));self.assertEqual(list(m.WRITES[kind]),[p for _,p,_ in steps])
            self.assertEqual(m.physical(initial)[active],steps[4][2][active])
            self.assertEqual(m.physical({candidate:after[:len(after)//2]})[candidate],steps[1][2][candidate])
            self.assertNotIn(candidate,steps[0][2]);self.assertNotIn(candidate,steps[5][2])
            self.assertEqual(m.physical(dict(initial,**{active:after})),steps[-1][2])
            for _,_,files in steps:
                for name,identity in m.physical(initial).items():
                    if name!=active:self.assertEqual(identity,files[name])

    def test_missing_active_stale_predecessor_partial_candidate_and_same_revision_reject(self):
        kind='peer';active,candidate=m.FILES[kind];initial=self.initial();before=initial[active]
        for files,old,new in (({},before,b'new'*20),(m.physical(initial),b'wrong',b'new'*20),
                              (m.physical(dict(initial,**{candidate:b'partial'})),before,b'new'*20),
                              (m.physical(initial),before,before)):
            with self.assertRaises(ValueError):m.transaction(files,old,new,kind)

    def fixture(self):
        initial=self.initial();after=dict(initial,**{m.FILES['peer'][0]:b'q'*51})
        points=[*m.RESEALS['peer'],*m.RESEALS['future'],'FLOOR_BEFORE_RETURN',*m.WRITES['peer'],
                'FLOOR_RELEASE_BEFORE_RETURN','GROUP_CRASH',*m.RESEALS['peer'],*m.RESEALS['future']]
        events=[dict(node=None if p=='GROUP_CRASH' else 'node-1',event=p) for p in points]
        tx=dict(node='node-1',start=5,end=11,scope=None,kind='maintenance',ledger='peer',
                before=initial[m.FILES['peer'][0]],after=after[m.FILES['peer'][0]])
        def seals(kind):
            return [dict(node='node-1',life=life,ledger=kind,indices=indices,raw=files[m.FILES[kind][0]])
                for life,indices,files in ((1,[0,1] if kind=='peer' else [2,3],initial),
                                          (2,[14,15] if kind=='peer' else [16,17],after))]
        peers=SimpleNamespace(events=events,history=SimpleNamespace(old=['node-1']),raw_changes=[tx],raw_reseals=seals('peer'),
                              initial_states=lambda:{'node-1':initial},run=lambda:{'status':'PASS'})
        future=SimpleNamespace(events=events,raw_changes=[],raw_reseals=seals('future'),run=lambda:{'status':'PASS'})
        anchors=[dict(life=1,eventIndex=4,node='node-1',point='FLOOR_BEFORE_RETURN',files=m.physical(initial)),
                 dict(life=1,eventIndex=12,node='node-1',point='FLOOR_RELEASE_BEFORE_RETURN',files=m.physical(after))]
        return peers,future,anchors,after

    def run_fixture(self,values):
        peers,future,anchors,after=values
        with patch.object(m,'Peers',return_value=peers),patch.object(m,'Future',return_value=future),\
                patch.object(m.forces,'replay',side_effect=lambda *a,**k:k['floor_prefixes'].extend(anchors)),\
                patch.object(m.forces,'group',return_value={'node-1':after}):
            return m.plans(Path('/original'),'FINAL','PROOF_RENAMED')

    def test_anchors_and_reseals_bind_to_continuous_state_across_both_lifetimes(self):
        rows,summary=self.run_fixture(self.fixture());self.assertEqual(15,len(rows))
        self.assertEqual(2,summary['anchorChecks']);self.assertEqual(1,summary['transactions']);self.assertEqual(8,summary['resealCallbacks'])
        self.assertEqual([0,1,2,3],[v['eventIndex'] for v in rows if v['life']==2])
        self.assertEqual(m.physical(self.fixture()[3]),rows[-1]['files'])

    def test_anchor_cannot_reset_a_derived_revision(self):
        values=self.fixture();values[2][-1]['files']=values[2][0]['files']
        with self.assertRaisesRegex(ValueError,'^ledger prefix anchor continuous revision$'):self.run_fixture(values)

    def test_write_cannot_borrow_an_unrelated_operation_anchor(self):
        values=self.fixture();values[2][0]['point']='INSTALL_PARENT_FORCED';values[0].events[4]['event']='INSTALL_PARENT_FORCED'
        with self.assertRaisesRegex(ValueError,'^ledger prefix exact operation anchor$'):self.run_fixture(values)

    def test_wrong_original_predecessor_rejects(self):
        values=self.fixture();values[0].raw_changes[0]['before']=b'x'*50
        with self.assertRaisesRegex(ValueError,'^ledger prefix continuous original predecessor$'):self.run_fixture(values)

    def test_reopen_cannot_rollback_the_in_memory_replayed_chain(self):
        values=self.fixture();values[0].raw_reseals[1]['raw']=self.initial()[m.FILES['peer'][0]]
        with self.assertRaisesRegex(ValueError,'^ledger prefix original reseal revision$'):self.run_fixture(values)

    def test_reopen_snapshot_cannot_supply_a_new_ledger_revision(self):
        values=self.fixture();values[3][m.FILES['future'][0]]=b'foreign future'
        with self.assertRaisesRegex(ValueError,'^ledger prefix cold original revision$'):self.run_fixture(values)

    def test_duplicate_anchor_or_missing_write_force_reject(self):
        values=self.fixture();values[2].append(copy.deepcopy(values[2][0]))
        with self.assertRaisesRegex(ValueError,'^ledger prefix duplicate original anchor$'):self.run_fixture(values)
        values=self.fixture();values[0].events[8]['event']='FOREIGN_EVENT'
        with self.assertRaisesRegex(ValueError,'^ledger prefix original transaction callbacks$'):self.run_fixture(values)

    def test_unrelated_ack_promotion_and_learner_events_are_not_ledger_byte_points(self):
        for name in ('FUTURE_RETENTION_BEFORE_RETURN','FUTURE_RETENTION_ACK_BEFORE_RETURN',
                     'FUTURE_RETENTION_PROMOTED','FUTURE_RETENTION_CLEARED','LEARNER_RETENTION_FORCED'):
            self.assertNotIn(name,m.POINTS)


if __name__=='__main__':unittest.main()

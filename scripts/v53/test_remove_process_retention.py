"""Continuous recovered ledgers and bounded original-first qualification."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import remove_process_retention as r


def opens():
    events=[dict(node='node-1',event=name) for name in r.p.OPEN]
    events.extend(dict(node='node-2',event=name) for name in r.p.OPEN)
    events.extend(dict(node='node-1',event=name) for name in r.p.OPEN[:5])
    for _ in range(2):events.extend(dict(node='node-1',event=name) for name in r.p.OPEN)
    return SimpleNamespace(events=events,history=SimpleNamespace(old=('node-1','node-2')),profile=dict(mode='kill'))


class RemoveProcessRetentionTest(unittest.TestCase):
    def test_current_revalidation_is_not_a_new_open_and_every_real_reseal_is_bound(self):
        rows=r.open_reseals(opens())
        self.assertEqual(['before-network','kill-opened-0','resume-opened-0'],[v['path'] for v in rows if v['node']=='node-1'])
        self.assertEqual(4,len(rows))
        for row in rows:self.assertLess(row['peer'],row['futureEvents'][0]);self.assertLess(row['futureEvents'][0],row['future'])

    def test_resumed_open_cannot_lose_reorder_or_invent_a_reseal(self):
        for kind in ('missing','reversed','extra','scope'):
            base=opens();rows=base.events;first=len(rows)-len(r.p.OPEN)
            if kind=='missing':del rows[first+6]
            elif kind=='reversed':rows[first+5],rows[first+6]=rows[first+6],rows[first+5]
            elif kind=='extra':rows.extend(dict(node='node-1',event=p) for p in r.future.RESEAL)
            else:rows[first+6]['scope']='other-process'
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'REMOVE process retention (exact open force order|unbound open reseal|original open owner)'):
                r.open_reseals(base)

    def test_peer_snapshot_compares_continuous_state_and_never_reseeds_it(self):
        reader=r.PeerReplay.__new__(r.PeerReplay);reader.root=Path('/history');reader.history=SimpleNamespace(old=('node-1',))
        reader.state={'node-1':b'derived-revision-three'};reader.comparisons=0;before=dict(reader.state)
        with patch.object(r.c,'inventory',return_value={r.peer.FILE:b'claimed-reset'}),self.assertRaisesRegex(ValueError,'exact original ledger'):
            reader.snapshot('resume-opened-0')
        self.assertEqual(before,reader.state)

    def test_future_reopen_cannot_replace_derived_bytes_or_claim_successful_callbacks(self):
        reader=r.FutureReplay.__new__(r.FutureReplay);reader.root=Path('/history');reader.state={'node-1':dict(raw=b'derived')}
        reader.callbacks=set();reader.reseals=0;reader.open_steps=[];before=copy.deepcopy(reader.state)
        row=dict(node='node-1',path='resume-opened-0',futureEvents=[1,2])
        with patch.object(r.c,'inventory',return_value={r.future.future.FILE:b'reset'}),self.assertRaisesRegex(ValueError,'exact continuous ledger'):
            reader.reopen_original(row)
        self.assertEqual(before,reader.state);self.assertEqual(set(),reader.callbacks);self.assertEqual(0,reader.reseals)

    def test_retention_writes_cannot_be_reused_by_two_causes(self):
        reader=r.PeerReplay.__new__(r.PeerReplay);reader.tx=[dict(node='node-1',start=2,end=4,scope=None)]
        reader.used={2};reader.steps=[]
        with patch.object(r.peer.peers,'decode',return_value=dict(owner=dict(node='node-1'))),self.assertRaisesRegex(ValueError,'original write owner'):
            reader.sequence('node-1',[(b'a',b'b','cause')],1,5,'maintenance')

    def test_original_floor_failure_prevents_any_retention_claim(self):
        with patch.object(r.p.run.h,'inventory',return_value={}),patch.object(r.m,'validate',side_effect=ValueError('bad floor')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^bad floor$'):r.validate('/original')
        replay.assert_not_called()

    def test_original_failure_prevents_negative_submission(self):
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^bad original$'):r.qualify('/original')
        pool.assert_not_called()

    def test_replay_worker_bound_precedes_original_read(self):
        for workers in (0,5,True,1.5):
            with patch.object(r,'validate') as validate,self.assertRaisesRegex(ValueError,'replay workers'):r.qualify('/original',workers=workers)
            validate.assert_not_called()

    def test_negative_cannot_change_physical_or_wire_or_unrelated_observations(self):
        before=dict(files={'owner/selector':'a','history/wire.json':'wire'},directories=[])
        for after,observations,message in (
            (dict(files={'owner/selector':'b','history/wire.json':'wire'},directories=[]),None,'physical or wire inputs'),
            (dict(files={'owner/selector':'a','history/wire.json':'new'},directories=[]),None,'physical or wire inputs'),
            (before,[([],[]),([dict(node='node-1',event='FLOOR_RESERVED')],[])],'other observations')):
            with patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),patch.object(r.p.run.h,'inventory',return_value=after),\
                 patch.object(r.n,'observations',side_effect=observations),patch.object(r,'PeerReplay') as replay:
                with self.assertRaisesRegex(ValueError,message):r.negative('/original',{},before,'peers','force-missing')
            replay.assert_not_called()

    def test_wrong_rejection_or_accepted_mutation_does_not_qualify(self):
        before=dict(files={},directories=[])
        for error,message in ((ValueError('unrelated'),'unrelated retention negative'),(None,'mutation accepted')):
            with patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),patch.object(r.p.run.h,'inventory',return_value=before),\
                 patch.object(r.n,'observations',return_value=([],[])),patch.object(r,'PeerReplay') as replay:
                replay.return_value.run.side_effect=error
                with self.assertRaisesRegex(ValueError,message):r.negative('/original',{},before,'peers','force-missing')


if __name__=='__main__':unittest.main()

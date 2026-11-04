"""Cold declarations remain event-bound and never reset the independent chain."""
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import joint_ledger_evidence as j
from . import test_joining_same_view_learner as learner_fixture


def event(point,node=j.NODE,scope=None):
    return dict(node=node,event=point,**({} if scope is None else dict(scope=scope)))


class JointLedgerTest(unittest.TestCase):
    def cold(self):
        return [event(p,scope=j.SCOPE) for p in ('CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED',
            'CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED','FLOOR_RELEASE_BEFORE_RETURN')]

    def test_declaration_requires_exact_original_owner_start(self):
        rows=self.cold();valid={j.NODE:(0,j.SCOPE)}
        self.assertEqual(valid,j.future.declared_old_lifetimes(rows,'node-6',valid))
        for value in ([],{j.NODE:(True,j.SCOPE)},{j.NODE:(-1,j.SCOPE)},{j.NODE:(1,j.SCOPE)},
                      {j.NODE:(0,'foreign')},{'node-6':(0,j.SCOPE)},{'node-9':(0,j.SCOPE)},{j.NODE:[0,j.SCOPE]}):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'declared original cold lifetime'):
                j.future.declared_old_lifetimes(rows,'node-6',value)

    def test_future_scope_is_explicit_and_cannot_cross_the_cold_boundary(self):
        before=[event(p) for p in j.future.WRITES];cold=self.cold();after=[event(p,scope=j.SCOPE) for p in j.future.WRITES]
        rows=before+cold+after;life={j.NODE:(len(before),j.SCOPE)}
        tx,_=j.future.observations(rows,joining='node-6',old_owner_lifetimes=life)
        self.assertEqual([None,j.SCOPE],[v['scope'] for v in tx])
        with self.assertRaisesRegex(ValueError,'joining future event shape'):j.future.observations(rows,joining='node-6')
        for at in (0,len(rows)-1):
            changed=copy.deepcopy(rows);changed[at]['scope']='foreign'
            with self.subTest(at=at),self.assertRaisesRegex(ValueError,'event shape|original event owner'):
                j.future.observations(changed,joining='node-6',old_owner_lifetimes=life)

    def test_learner_custody_stays_separate_and_cold_writes_keep_their_owner(self):
        custody=learner_fixture.JoiningSameViewLearnerTest().custody();rows=custody+self.cold()+[event(p,scope=j.SCOPE) for p in j.learner.WRITES]
        life={j.NODE:(len(custody),j.SCOPE)}
        tx,excluded=j.learner.observations(rows,'node-4',old_owner_lifetimes=life)
        self.assertEqual(11,len(excluded));self.assertEqual(j.SCOPE,tx[0]['scope'])
        with self.assertRaisesRegex(ValueError,'joining learner event shape'):j.learner.observations(rows,'node-4')
        rows[-1]['scope']='foreign'
        with self.assertRaisesRegex(ValueError,'joining learner original event owner'):
            j.learner.observations(rows,'node-4',old_owner_lifetimes=life)

    def test_allocator_optional_cold_scope_never_relaxes_ordinary_owners(self):
        b=j.ballot_profile.ballot;before=[event(p) for p in b.WRITES]
        rows=before+self.cold()+[event(p,scope=j.SCOPE) for p in b.WRITES];life={j.NODE:(len(before),j.SCOPE)}
        tx=b.allocations(rows,('node-1',j.NODE,'node-6'),'node-6',old_owner_lifetimes=life)
        self.assertEqual([None,j.SCOPE],[v['scope'] for v in tx])
        with self.assertRaisesRegex(ValueError,'allocator event shape'):b.allocations(rows,('node-1',j.NODE,'node-6'),'node-6')
        rows[-1]['scope']='foreign'
        with self.assertRaisesRegex(ValueError,'allocator owner scope'):
            b.allocations(rows,('node-1',j.NODE,'node-6'),'node-6',old_owner_lifetimes=life)

    def test_peer_reseal_compares_against_existing_state_instead_of_reseeding(self):
        r=j.PeerReplay.__new__(j.PeerReplay);r.root=Path('/original');r.events=self.cold();r.model=SimpleNamespace(joining='node-6')
        r.state={j.NODE:b'continuous-chain'};r.comparisons=0
        with patch.object(j.disk,'inventory',return_value={j.peer.FILE:b'continuous-chain'}) as inventory:
            r.reseal((5,j.NODE));self.assertEqual(1,r.comparisons)
            inventory.assert_called_once_with(r.root/'joint-floor-recovery/after-reopen')
        with patch.object(j.disk,'inventory',return_value={j.peer.FILE:b'bootstrap-reset'}):
            with self.assertRaisesRegex(ValueError,'exact original ledger'):r.reseal((5,j.NODE))
        self.assertEqual({j.NODE:b'continuous-chain'},r.state)

    def test_cold_owner_scope_switch_is_local_and_not_earlier(self):
        r=j.PeerReplay.__new__(j.PeerReplay);r.model=SimpleNamespace(joining='node-6')
        r.events=[event('earlier')]+self.cold()
        self.assertIsNone(r.write_scope(j.NODE,0));self.assertEqual(j.SCOPE,r.write_scope(j.NODE,1))
        self.assertIsNone(r.write_scope('node-1',6));self.assertEqual('continuation-owner',r.write_scope('node-6',6))

    def test_ballot_reopen_adds_comparison_not_seed_or_reservation(self):
        r=j.BallotReplay.__new__(j.BallotReplay);r.events=self.cold()
        self.assertEqual([(0,'original',(j.NODE,'joint-floor-recovery/after-reopen','joint-floor-reopen'))],r.reopen_actions())
        r.events.insert(-1,event('ALLOCATOR_BEFORE_WRITE',scope=j.SCOPE))
        with self.assertRaisesRegex(ValueError,'allocation during floor recovery'):r.reopen_actions()

    def test_original_failure_cannot_count_as_negative_rejection(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(j,'validate',side_effect=ValueError('invalid original')),patch.object(j,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):j.qualify(tmp)
            mutate.assert_not_called()

    def test_not_applicable_is_derived_only_from_missing_actual_joining_write(self):
        original=dict(ledgers=dict(learner=dict(joiningWrites=0),ballot=dict(adoptionFences=[dict(promiseAppended=True)])))
        pending,absent=j.cases(original)
        self.assertEqual(101,len(pending)+len(absent));self.assertEqual([('learner','wrong-write-scope')],[(v['stage'],v['case']) for v in absent])
        original['ledgers']['learner']['joiningWrites']=1
        self.assertEqual([],j.cases(original)[1])

    def test_unknown_negative_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            for stage,name in (('unknown','force-missing'),('peers','unknown')):
                with self.subTest(stage=stage),self.assertRaisesRegex(ValueError,'unknown negative'):j.mutate(tmp,stage,name)
            self.assertEqual([],list(Path(tmp).iterdir()))

    def test_peer_writes_cannot_add_claimed_revision_or_null_scope(self):
        for extra in (dict(claimedRevision=999),dict(scope=None)):
            rows=[event(point) for point in j.peer.WRITES];rows[3].update(extra)
            with self.subTest(extra=extra),self.assertRaisesRegex(ValueError,'peer write event shape'):j.peer.transactions(rows)

    def test_peer_owner_negative_targets_later_write_without_breaking_floor_precondition(self):
        writes=[event(p,scope=j.SCOPE) for p in j.peer.WRITES]
        events=self.cold()[:-1]+copy.deepcopy(writes)+self.cold()[-1:]+copy.deepcopy(writes)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'events.json';path.write_bytes(j.f.canonical(events));j.mutate(tmp,'peers','cold-write-owner')
            after=j.history.p.read(path);released=len(self.cold())-1+len(writes)
            self.assertEqual(events[:released+1],after[:released+1])
            self.assertTrue(all(row['scope']=='foreign-owner' for row in after[released+1:]))

    def test_unbound_ballot_uses_an_ordinary_owner_to_reach_its_designated_check(self):
        reader=SimpleNamespace(tx=[dict(node='node-1')],owners=('node-1',j.NODE,'node-3','node-6'),
            model=SimpleNamespace(joining='node-6'),events=self.cold())
        with tempfile.TemporaryDirectory() as tmp,patch.dict(j.READERS,{'ballot':lambda root:reader}):
            j.mutate(tmp,'ballot','unbound-reservation')
            rows=j.history.p.read(Path(tmp)/'events.json')[len(self.cold()):]
            self.assertEqual([event(p,'node-3') for p in j.ballot_profile.ballot.WRITES],rows)


if __name__=='__main__':unittest.main()

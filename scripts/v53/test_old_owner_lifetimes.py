"""Two cold owners retain distinct observations; legacy callers stay exact."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import old_owner_lifetimes as m
from . import joining_same_view_future as future
from . import joining_same_view_ballot as ballot
from . import joining_phase_evidence as phase
from . import current_lifecycle_evidence as current
from . import joining_same_view_learner as learner
from . import test_joining_same_view_learner as learner_fixture
from . import test_joining_grant_captures as grants

NODE='node-2'


def row(event,scope=None):return dict(node=NODE,event=event,**({} if scope is None else dict(scope=scope)))


class OldOwnerLifetimesTest(unittest.TestCase):
    def test_legacy_and_multiple_opens_choose_only_the_active_original_scope(self):
        old={NODE:(2,'cold')};self.assertIs(old,m.validate(old,reason='invalid'))
        life={NODE:((2,'child'),(7,'reopened'))};self.assertIs(life,m.validate(life,reason='invalid'))
        self.assertEqual([None,None,'child','child','child','child','child','reopened','reopened'],
                         [m.scope(life,NODE,i) for i in range(9)])
        self.assertEqual('network-owner',m.scope(life,NODE,0,'network-owner'))
        self.assertIsNone(m.scope(life,'node-1',9))

    def test_ambiguous_empty_reordered_and_duplicate_scope_declarations_fail(self):
        for value in [(),[],(True,'cold'),(-1,'cold'),(1,''),((2,'child'),(1,'reopened')),((2,'child'),(2,'reopened')),
                      ((2,'child'),(7,'child')),((2,'child'),),((2,'child'),('7','reopened'))]:
            # A one-element ordered tuple is unambiguous and valid.
            if value==((2,'child'),):self.assertEqual({NODE:value},m.validate({NODE:value},reason='invalid'));continue
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'invalid'):m.validate({NODE:value},reason='invalid')
        with self.assertRaisesRegex(ValueError,'invalid'):m.validate({NODE:(3,'cold')},maximum=3,reason='invalid')
        with self.assertRaisesRegex(ValueError,'invalid'):m.validate({NODE:(0,'cold')},owners=('node-1',),reason='invalid')

    def test_each_declared_open_requires_its_exact_original_current_observation(self):
        events=[row('CURRENT_VALIDATED','child'),row('CURRENT_VALIDATED','reopened')];life={NODE:((0,'child'),(1,'reopened'))}
        self.assertEqual(life,future.declared_old_lifetimes(events,'node-6',life))
        for at in (0,1):
            changed=copy.deepcopy(events);changed[at]['event']='IGNORED_CURRENT'
            with self.assertRaisesRegex(ValueError,'declared original cold lifetime'):future.declared_old_lifetimes(changed,'node-6',life)
        with self.assertRaisesRegex(ValueError,'declared original cold lifetime'):future.declared_old_lifetimes(events,NODE,life)

    def test_future_and_allocator_writes_cannot_cross_or_relabel_either_open(self):
        for module,names,reader in ((future,future.WRITES,lambda e,l:future.observations(e,joining='node-6',old_owner_lifetimes=l)[0]),
                                   (ballot,ballot.WRITES,lambda e,l:ballot.allocations(e,(NODE,),'node-6',old_owner_lifetimes=l))):
            events=[row(v) for v in names];pairs=[]
            for scope in ('child','reopened'):
                pairs.append((len(events),scope));events.append(row('CURRENT_VALIDATED',scope));events.extend(row(v,scope) for v in names)
            life={NODE:tuple(pairs)};tx=reader(events,life)
            self.assertEqual([None,'child','reopened'],[v['scope'] for v in tx])
            for start,scope in pairs:
                for replacement in (None,'other','reopened' if scope=='child' else 'child'):
                    changed=copy.deepcopy(events);changed[start+1]=row(names[0],replacement)
                    with self.subTest(module=module.__name__,scope=scope,replacement=replacement),self.assertRaises(ValueError):reader(changed,life)
            # Splitting one durable transaction across the cold boundary is not
            # made valid by giving every individual row its active scope.
            first=pairs[0][0];cross=[row(names[0]),row('CURRENT_VALIDATED','child'),*[row(v,'child') for v in names[1:]]]
            with self.assertRaisesRegex(ValueError,'exact .*force order'):reader(cross,{NODE:(1,'child')})

    def test_current_force_replay_accounts_for_every_cold_open_without_projection(self):
        events=[];pairs=[]
        for scope in ('child','reopened'):
            pairs.append((len(events),scope));events.extend(row(v,scope) for v in (*current.OPEN,'LEARNER_RETENTION_RECOVERY_ACTIVE_FORCED'))
        before=copy.deepcopy(events);owner=current.Ownership(events);owner.old_reopens({NODE:tuple(pairs)})
        self.assertEqual(len(current.OPEN)*2,len(owner.used));self.assertEqual(events,before)
        changed=copy.deepcopy(events);changed[pairs[1][0]+1]['event']='IGNORED_CURRENT_FORCE'
        with self.assertRaisesRegex(ValueError,'complete original interval'):current.Ownership(changed).old_reopens({NODE:tuple(pairs)})

    def test_slot_force_owner_does_not_reuse_the_child_after_final_reopen(self):
        names=phase.force_names();events=[];life=[]
        for scope in (None,'child','reopened'):
            if scope is not None:life.append((len(events),scope));events.append(row('CURRENT_VALIDATED',scope))
            events.extend(row(v,scope) for v in names)
        replay=SimpleNamespace(old=(NODE,),joining=None,phases=[{'CERTIFICATE':b'c'}]*3)
        with patch.object(phase.f,'decode',return_value={'proofs':[{'voter':NODE}]}):
            result=phase.blocks(events,replay,old_owner_lifetimes={NODE:tuple(life)});self.assertEqual(3,len(result))
            changed=copy.deepcopy(events);changed[life[1][0]+1]['scope']='child'
            with self.assertRaisesRegex(ValueError,'force owner lifetime'):phase.blocks(changed,replay,old_owner_lifetimes={NODE:tuple(life)})

    def test_learner_custody_and_two_original_voter_scopes_stay_distinct(self):
        events=learner_fixture.JoiningSameViewLearnerTest().custody();pairs=[]
        for scope in ('child','reopened'):
            pairs.append((len(events),scope));events.append(row('CURRENT_VALIDATED',scope));events.extend(row(v,scope) for v in learner.WRITES)
        tx,excluded=learner.observations(events,'node-4',old_owner_lifetimes={NODE:tuple(pairs)})
        self.assertEqual(11,len(excluded));self.assertEqual(['child','reopened'],[v['scope'] for v in tx])
        events[pairs[1][0]+1]['scope']='child'
        with self.assertRaisesRegex(ValueError,'learner original event owner'):learner.observations(events,'node-4',old_owner_lifetimes={NODE:tuple(pairs)})

    def test_grant_capture_selects_each_declared_scope_at_its_original_event(self):
        from pathlib import Path
        fixture=grants.JoiningGrantCapturesTest()
        rows=[dict(grants.observed(node,counter),capturedEvent=counter,
                   scope=('child' if counter==7 else 'reopened') if node==NODE else 'network-owner')
              for node in ('node-1',NODE) for counter in (7,8)]
        life={NODE:((7,'child'),(8,'reopened'))}
        with patch.object(grants.g,'inventory',side_effect=lambda path:(fixture.before(path.name),{},0)):
            self.assertEqual(7,grants.g.require_intermediate(Path('/original'),rows,old_owner_lifetimes=life))
            rows[-1]['scope']='child'
            with self.assertRaisesRegex(ValueError,'original cold lifetime'):
                grants.g.require_intermediate(Path('/original'),rows,old_owner_lifetimes=life)


if __name__=='__main__':unittest.main()

"""Conditional profile regressions; retained native replay is a separate gate."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_profile_initialization_evidence as e
from .test_joining_retention_evidence import Inputs

j = e.initialization


def head_fixture(directory, profile):
    size, kind, old, new = e.topology(profile); v = Inputs(size, kind == 'REPLACE')
    # The head confirms the sealed OLD view before INTENT enters JOINT.
    v.cap = copy.deepcopy(v.cap)
    v.cap['cut']['view'] = dict(generation=0, old=old, new=old, operation=None)
    v.request['expected'] = j.s.catalog.authority(v.cap['root'], v.cap['cut']['view'])
    catalog = j.f.decode(v.current['objects'][v.cap['catalog']], 'records', 'CATALOG')
    catalog['cut'] = v.cap['cut']
    raw = j.f.encode('records', 'CATALOG', catalog)
    v.cap['catalog'] = j.sha(raw); v.current['objects'][j.sha(raw)] = raw
    reader = j.Initialization.__new__(j.Initialization)
    reader.root = directory; reader.voters = tuple(old[:size//2+1])
    reader.replay = SimpleNamespace(root=v.cap['root'], joining=new[-1])
    packet = j.disk.packet_bytes(v.cap, v.current['objects'], v.current['images'])
    reader.owner = SimpleNamespace(joining=v.joining, request=v.request, history=SimpleNamespace(sources={8:{'source.gscp':packet}}))
    endpoint = j.disk.anchor(v.cap); lower = v.endpoint(3); reader.group = {}; wire = []
    for index, node in enumerate(reader.voters):
        identity = v.identities[index]
        request = dict(root=v.cap['root'], view=v.request['expected'], ballot=dict(counter=1, proposer=new[-1], incarnation=v.joining['storage']),
            trace='00000000-0000-0000-0020-'+str(index+1).zfill(12), sequence=1, sender=identity, recipient=v.joining,
            payload=dict(request=v.request))
        response = dict(request, sender=v.joining, recipient=identity,
            payload=dict(request=j.sha(j.f.canonical(v.request)), endpoint=endpoint))
        proof = dict(query=j.placement.encoded(j.f.encode('wire', 'LEARNER_HEAD_QUERY', request)),
                     ack=j.placement.encoded(j.f.encode('wire', 'LEARNER_HEAD_ACK', response)))
        wire.append(dict(request=proof['query'], response=proof['ack']))
        plan = dict(root=v.cap['root'], request=v.request, learner=v.joining, possible=[lower, endpoint])
        reader.group[node] = {'node.gsr':j.f.encode('records', 'NODE', dict(root=v.cap['root'], identity=identity)),
            j.learner.FILE:j.learner.frame(dict(root=v.cap['root'], owner=identity, revision=0, previous=None, plan=plan))}
        (directory/('joining-confirmed-'+node+'.json')).write_bytes(j.f.canonical(dict(plan, possible=[endpoint], renewals=[lower], confirmation=proof)))
    (directory/'joining-head-wire.json').write_bytes(j.f.canonical(wire))
    return reader, wire, endpoint, lower


class JoiningProfileInitializationEvidenceTest(unittest.TestCase):
    def test_all_old_majority_heads_confirm_without_losing_prior_debt(self):
        for profile in e.PROFILES:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temp:
                reader, _, point, lower = head_fixture(Path(temp), profile)
                before = copy.deepcopy(reader.group); reader.confirmations()
                for node in reader.voters:
                    after = j.learner.decode(reader.group[node][j.learner.FILE])
                    self.assertEqual([point], after['plan']['possible']); self.assertEqual([lower], after['plan']['renewals'])
                    self.assertEqual(1, after['revision']); self.assertEqual(j.sha(before[node][j.learner.FILE]), after['previous'])
                    self.assertEqual(node, after['owner']['node'])

    def test_missing_third_old_head_or_extra_offline_head_is_rejected(self):
        for profile in ('4-ADD', '4-REPLACE', '5-REPLACE'):
            for extra in (False, True):
                with self.subTest(profile=profile, extra=extra), tempfile.TemporaryDirectory() as temp:
                    reader, wire, _, _ = head_fixture(Path(temp), profile)
                    if extra: wire.append(wire[-1])
                    else: wire.pop()
                    (Path(temp)/'joining-head-wire.json').write_bytes(j.f.canonical(wire))
                    with self.assertRaisesRegex(ValueError, '^joining initialization original head exchange count$'):reader.confirmations()

    def test_third_old_owner_cannot_borrow_another_owners_head(self):
        for profile in ('4-ADD', '4-REPLACE', '5-REPLACE'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temp:
                reader, wire, _, _ = head_fixture(Path(temp), profile)
                wire[1], wire[2] = wire[2], wire[1]
                (Path(temp)/'joining-head-wire.json').write_bytes(j.f.canonical(wire))
                with self.assertRaisesRegex(ValueError, '^joining initialization exact original head exchange$'):reader.confirmations()

    def test_reconciliation_retains_the_removed_old_identity_in_joint_view(self):
        for profile in e.PROFILES:
            size, kind, old, new = e.topology(profile); v = Inputs(size, kind == 'REPLACE')
            state = dict(root=v.cap['root'], owner=v.identities[0], revision=0, previous=None,
                         plan=copy.deepcopy(v.peer_plans[0]))
            state['plan']['peers'].pop(); raw = j.peers.frame(state)
            local = {'node.gsr':j.f.encode('records', 'NODE', dict(root=v.cap['root'], identity=v.identities[0]))}
            joined = {'node.gsr':j.f.encode('records', 'NODE', dict(root=v.cap['root'], identity=v.joining))}
            current = ('generations/a/', {}, v.current)
            with self.subTest(profile=profile), patch.object(j.disk, 'current', return_value=current):
                result = j.peers.decode(j.reconcile(raw, local, joined))
            self.assertEqual(state['plan']['peers'], result['plan']['peers'][:-1])
            self.assertEqual(sorted(set(old+new)), [row['identity']['node'] for row in result['plan']['peers']])
            self.assertEqual(v.joining, result['plan']['peers'][-1]['identity'])

    def lifetimes(self, profile):
        fixture = json.loads((Path(__file__).parent/'testdata/joining-initialization-events.json').read_text())
        joining = e.topology(profile)[3][-1]
        return [dict(row, node=joining) for row in fixture['rows']], joining

    def test_complete_local_force_lifetimes_follow_actual_joining_owner(self):
        for profile in e.PROFILES:
            rows, joining = self.lifetimes(profile)
            with self.subTest(profile=profile):j.local_order(rows, joining=joining)

    def test_old_node_four_cannot_supply_joining_five_or_six_force(self):
        for profile in ('4-ADD', '4-REPLACE', '5-REPLACE'):
            rows, joining = self.lifetimes(profile); rows[0]['node'] = 'node-4'
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, '^joining initialization original lifecycle owner$'):
                j.local_order(rows, joining=joining)

    def test_reordered_grant_force_remains_rejected_for_every_profile(self):
        for profile in e.PROFILES:
            rows, joining = self.lifetimes(profile)
            at = next(i for i,v in enumerate(rows) if v['event'] == 'BASIS_FORCED')
            rows[at-1], rows[at] = rows[at], rows[at-1]
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, '^joining initialization original first grant order$'):
                j.local_order(rows, joining=joining)

    def test_unknown_profile_is_rejected_before_reading_originals(self):
        with patch.object(e.s.collection, 'inventory') as inventory:
            with self.assertRaisesRegex(ValueError, '^joining prefix profile$'):e.validate('/unused', '5-ADD')
            inventory.assert_not_called()

    def test_partial_gate_never_promotes_to_complete_qualification(self):
        stages = [(name, SimpleNamespace(run=lambda: {'status':'PASS'})) for name in e.STAGES]
        with patch.object(e.s.collection, 'inventory', return_value={}), patch.object(e, 'stages', return_value=iter(stages)):
            result = e.validate('/original', '4-ADD')
        self.assertEqual('PARTIAL', result['status']); self.assertEqual(e.STAGES, tuple(result['gates']))
        for name in ('completePhysicalQualified', 'forceAndNetworkQualified', 'processDeathQualified', 'phase3Complete'):
            self.assertFalse(result[name])

    def test_invalid_original_cannot_count_as_negative_qualification(self):
        with patch.object(e.s.collection, 'inventory', return_value={}), patch.object(e, 'validate', side_effect=ValueError('bad original')), \
             patch.object(e.shutil, 'copytree') as copytree:
            with self.assertRaisesRegex(ValueError, '^bad original$'):e.qualify('/original', '3-REPLACE')
            copytree.assert_not_called()

    def negative(self, prior_error=None, target_error=None):
        def stages(*_):
            if prior_error:raise prior_error
            yield 'placement', SimpleNamespace(run=lambda: (_ for _ in ()).throw(target_error) if target_error else {})
        with patch.object(e.s.collection, 'inventory', return_value={}), patch.object(e, 'validate', return_value={}), \
             patch.object(e.shutil, 'copytree'), patch.object(e.placement, 'mutate'), patch.object(e, 'stages', side_effect=stages):
            return e.qualify('/original', '3-REPLACE')

    def test_prior_gate_failure_is_not_a_designated_negative(self):
        with self.assertRaisesRegex(ValueError, '^bad prefix$'):self.negative(prior_error=ValueError('bad prefix'))

    def test_unrelated_failure_cannot_count_as_designated_rejection(self):
        with self.assertRaisesRegex(ValueError, '^joining profile initialization unrelated negative:'):
            self.negative(target_error=ValueError('unrelated'))

    def test_accepted_mutation_is_not_a_success(self):
        with self.assertRaisesRegex(ValueError, '^joining profile initialization accepted mutation:'):self.negative()


if __name__ == '__main__':unittest.main()

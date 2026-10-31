"""Continuation reader boundaries; synthetic inputs are not native evidence."""
import base64
import copy
import unittest
from unittest.mock import patch

from . import joining_continuation_evidence as c
from .test_learner_confirmation_evidence import fixture
from .test_joining_retention_evidence import Inputs


def inputs():
    state = fixture(); v = Inputs(); cap = v.current['capsule']
    def identity(value): return dict(value, port=19000+int(value['node'][0]))
    state['owner'] = identity(state['owner']); state['plan']['learner'] = identity(state['plan']['learner'])
    request = state['plan']['request']; request['target'] = [identity(value) for value in request['target']]
    proof = state['plan']['confirmation']
    for field, kind in [('query', 'LEARNER_HEAD_QUERY'), ('ack', 'LEARNER_HEAD_ACK')]:
        value = c.f.decode(base64.b64decode(proof[field]), 'wire', kind)
        for name in ('sender', 'recipient'): value[name] = identity(value[name])
        value['payload']['request'] = request if field == 'query' else c.sha(c.f.canonical(request))
        proof[field] = base64.b64encode(c.f.encode('wire', kind, value)).decode()
    catalog = c.f.decode(v.current['objects'][cap['catalog']], 'records', 'CATALOG')
    identities = {i['node']:i for i in [state['owner'], *state['plan']['request']['target']]}
    catalog['identities'] = [identities[n] for n in sorted(identities)]
    raw = c.f.encode('records', 'CATALOG', catalog)
    packet = dict(capsule=dict(root=state['root'], catalog=c.sha(raw)), objects={c.sha(raw):raw})
    point = copy.deepcopy(state['plan']['possible'][0]); point['cut']['index'] -= 1
    state['plan']['renewals'] = [point]
    return state, packet


class JoiningContinuationEvidenceTest(unittest.TestCase):
    def test_selected_confirmation_releases_only_older_debt_and_keeps_newer_possibility(self):
        state, packet = inputs(); before = c.learner.frame(state)
        result = c.merge_learner(before, [before], packet); after = c.learner.decode(result)
        self.assertNotIn('renewals', after['plan']); self.assertEqual(state['plan']['possible'], after['plan']['possible'])
        self.assertEqual(state['plan']['confirmation'], after['plan']['confirmation'])
        self.assertEqual(state['revision']+1, after['revision']); self.assertEqual(c.sha(before), after['previous'])
        self.assertEqual(state, c.learner.decode(before))

    def test_same_index_conflict_is_rejected_even_below_confirmed_watermark(self):
        state, packet = inputs(); conflicting = copy.deepcopy(state)
        conflicting['plan']['renewals'][0]['catalog'] = 'a'*64
        with self.assertRaisesRegex(ValueError, '^joining continuation conflicting learner endpoint$'):
            c.merge_learner(c.learner.frame(state), [c.learner.frame(conflicting)], packet)

    def test_equivalent_confirmations_choose_canonical_digest_independent_of_order(self):
        state, packet = inputs(); other = copy.deepcopy(state)
        proof = other['plan']['confirmation']
        for field, kind in [('query', 'LEARNER_HEAD_QUERY'), ('ack', 'LEARNER_HEAD_ACK')]:
            value = c.f.decode(base64.b64decode(proof[field]), 'wire', kind); value['trace'] = '00000000-0000-0000-0000-000000000001'
            proof[field] = base64.b64encode(c.f.encode('wire', kind, value)).decode()
        first, second = c.learner.frame(state), c.learner.frame(other)
        a = c.merge_learner(first, [first, second], packet); b = c.merge_learner(first, [second, first], packet)
        self.assertEqual(a, b)
        chosen = min([state['plan']['confirmation'], proof], key=lambda p:c.sha(c.f.canonical(p)))
        self.assertEqual(chosen, c.learner.decode(a)['plan']['confirmation'])

    def test_no_confirmation_cannot_discard_old_debt_to_fit_capacity(self):
        state, packet = inputs(); state['plan'].pop('confirmation'); before = c.learner.frame(state)
        with self.assertRaisesRegex(ValueError, 'endpoint capacity'): c.merge_learner(before, [before], packet)

    def test_unchanged_selected_plan_preserves_bytes_and_revision(self):
        state, packet = inputs(); state['plan'].pop('renewals'); before = c.learner.frame(state)
        self.assertEqual(before, c.merge_learner(before, [before], packet))

    def test_confirmation_must_use_current_permanent_identities(self):
        state, packet = inputs(); cap = packet['capsule']; catalog = c.f.decode(packet['objects'][cap['catalog']], 'records', 'CATALOG')
        catalog['identities'] = [dict(v, port=v['port']-1) for v in catalog['identities']]
        raw = c.f.encode('records', 'CATALOG', catalog); packet = dict(capsule=dict(cap, catalog=c.sha(raw)), objects={c.sha(raw):raw})
        before = c.learner.frame(state)
        with self.assertRaisesRegex(ValueError, '^joining continuation learner confirmation permanent identity$'):
            c.merge_learner(before, [before], packet)

    def test_different_operation_cannot_enter_selected_merge(self):
        state, packet = inputs(); other = copy.deepcopy(state); other['plan'].pop('confirmation'); other['plan']['request']['number'] -= 1
        with self.assertRaisesRegex(ValueError, '^joining continuation learner identity$'):
            c.merge_learner(c.learner.frame(state), [c.learner.frame(other)], packet)

    def test_original_failure_prevents_any_negative_execution(self):
        with patch.object(c, 'validate', side_effect=ValueError('bad original')), patch.object(c.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, '^bad original$'): c.qualify('/absent')
            copied.assert_not_called()

    def test_prior_initialization_failure_is_not_a_successful_negative(self):
        with patch.object(c, 'validate', return_value={'status':'PASS'}), patch.object(c.shutil, 'copytree'), \
                patch.object(c, 'mutate'), patch.object(c.init, 'validate', side_effect=ValueError('prior gate')):
            with self.assertRaisesRegex(ValueError, '^prior gate$'): c.qualify('/absent')

    def test_unrelated_failure_is_not_a_successful_negative(self):
        with patch.object(c, 'validate', side_effect=[{'status':'PASS'}, ValueError('unrelated')]), patch.object(c.shutil, 'copytree'), \
                patch.object(c, 'mutate'), patch.object(c.init, 'validate', return_value={'status':'PASS'}):
            with self.assertRaisesRegex(ValueError, 'unrelated continuation negative'): c.qualify('/absent')

    def test_accepted_mutation_is_not_a_successful_negative(self):
        with patch.object(c, 'validate', return_value={'status':'PASS'}), patch.object(c.shutil, 'copytree'), \
                patch.object(c, 'mutate'), patch.object(c.init, 'validate', return_value={'status':'PASS'}):
            with self.assertRaisesRegex(ValueError, 'mutation accepted'): c.qualify('/absent')


if __name__ == '__main__': unittest.main()

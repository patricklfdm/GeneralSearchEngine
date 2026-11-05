"""Source selector guards, not native protocol or negative qualification."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import phase3_coverage as c


class Phase3CoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = c.p.decode((c.p.ROOT/c.PLAN).read_bytes())
        cls.qualification = c.p.decode((c.p.ROOT/c.p.PLAN).read_bytes())
        cls.acceptance = c.p.decode((c.p.ROOT/c.p.ACCEPTANCE).read_bytes())
        cls.source = c.catalogue()

    def validate(self, value=None, source=None):
        return c.validate(self.value if value is None else value, self.source if source is None else source,
                          self.qualification, self.acceptance)

    def reject(self, mutate, reason):
        value = deepcopy(self.value); mutate(value)
        with self.assertRaisesRegex(ValueError, reason): self.validate(value)

    @staticmethod
    def witness(value, identity):
        return next(w for r in value['requirements'] for w in r['witnesses'] if w['id'] == identity)

    def test_complete_source_partition_has_no_runtime_acceptance(self):
        result = self.validate()
        self.assertEqual(486, sum(map(len, self.source['units'].values())))
        self.assertEqual(552, sum(len(v['histories']) for units in self.source['units'].values() for v in units.values()))
        self.assertEqual(20, len(result['candidateWitnesses']))
        self.assertEqual(4, result['conditionalWitnesses'])
        self.assertTrue(all(w['qualification'] == 'NOT_EVALUATED' for w in result['candidateWitnesses']))
        self.assertEqual(0, result['nativeHistoriesExecuted'])
        self.assertTrue(all(result[k] is False for k in ('phase3Complete', 'runtimeQualified', 'frozenScenarioCoverageQualified')))
        self.assertEqual(dict(requiredPhase=5, coveredScenarioRows=[], coveredNegativeFamilies=[]), result['frozenCoverage'])

    def test_missing_duplicate_and_unknown_requirements_reject(self):
        for action in (lambda v: v['requirements'].pop(),
                       lambda v: v['requirements'].reverse(),
                       lambda v: v['requirements'][1].update(id=v['requirements'][0]['id'])):
            self.reject(action, 'exact requirement order')

    def test_scope_cannot_be_self_promoted(self):
        for key, value in [('status', 'PASS'), ('phase3Complete', True), ('phase3Complete', 0), ('runtimeQualified', True)]:
            self.reject(lambda v: v.update({key: value}), 'coverage plan')
        self.reject(lambda v: v['requirements'][0].update(openWork=''), 'open obligations')
        self.reject(lambda v: v['requirements'][0]['witnesses'][0].update(status='REJECTED'), 'witness fields')
        self.reject(lambda v: v['requirements'][0]['witnesses'][0].update(scope=''), 'explicit selector and scope')

    def test_exact_member_and_negative_names_reject_substrings_and_aliases(self):
        for field, value, reason in [('cohort', 'Phase2-carried-process', 'requirement cohort binding'),
                                     ('unit', '3-', 'exact archive unit')]:
            self.reject(lambda v: v['requirements'][0]['witnesses'][0].update({field: value}), reason)
        for selector in ({'suite': 'ballot', 'case': 'force', 'variant': 'default'},
                         {'suite': 'physical', 'case': 'force-missing', 'variant': 'default'},
                         {'suite': 'ballot', 'case': 'force-missing', 'variant': 'other'},
                         {'suite': 'ballot', 'case': 'force-missing', 'variant': 'default', 'stage': 'unknown'}):
            self.reject(lambda v: v['requirements'][0]['witnesses'][0].update(selector=selector), 'exact negative selector')

    def test_reason_drift_and_conditional_promotion_reject(self):
        self.reject(lambda v: v['requirements'][0]['witnesses'][0].update(reason='any error'), 'exact reason')
        for identity in ('activation-adoption', 'late-unused-prepare', 'joining-seed-transaction'):
            self.reject(lambda v: self.witness(v, identity).update(condition='always'), 'original applicability')

    def test_grouped_original_cannot_be_split_into_convenient_members(self):
        for identity in ('tcp-lifetimes', 'reply-resources'):
            self.reject(lambda v: self.witness(v, identity)['histories'].pop(), 'indivisible history set')
            self.reject(lambda v: self.witness(v, identity)['histories'].reverse(), 'indivisible history set')
        self.assertEqual(48, len(self.source['units']['automatic-histories']['reply-revocation']['histories']))
        self.assertEqual(18, len(self.source['units']['transfer-histories']['process-recovery']['histories']))

    def test_joining_group_contains_three_whole_independent_archives(self):
        units = self.source['units']['joining-process']
        first = next(iter(units.values()))
        group = [v for v in units.values() if v['executionGroup'] == first['executionGroup']]
        self.assertEqual(3, len(group)); self.assertTrue(all(len(v['histories']) == 1 for v in group))

    def test_unknown_duplicate_witnesses_and_orphan_cohort_reject(self):
        self.reject(lambda v: v['requirements'][0]['witnesses'].append(deepcopy(v['requirements'][0]['witnesses'][0])),
                    'unique witness id')
        self.reject(lambda v: v['requirements'][0].update(witnesses=[]), 'candidate witnesses required')
        self.reject(lambda v: v['requirements'][2]['witnesses'][0].update(cohort='automatic-histories'),
                    'requirement cohort binding')
        self.reject(lambda v: v['requirements'][8].update(witnesses=[dict(v['requirements'][0]['witnesses'][0], id='other')]),
                    'orphan hosted cohort')

    def test_entire_unselected_negative_vector_is_pinned(self):
        source = deepcopy(self.source)
        sha = source['units']['round-histories']['slot-certificate']['negativeVectorSha256']
        source['vectors'][sha][0]['reason'] = 'changed unselected rejection'
        with self.assertRaisesRegex(ValueError, 'source catalogue drift'): self.validate(source=source)
        self.reject(lambda v: v.update(acceptancePlanSha256='0'*64), 'frozen plan binding')

    def test_source_partition_drift_rejects_without_replaying_any_original(self):
        from . import transfer_history_hosted as hosted
        groups = deepcopy(hosted.SHARDS); groups['tcp-lifetimes'] = tuple(reversed(groups['tcp-lifetimes']))
        with patch.object(hosted, 'SHARDS', groups), self.assertRaisesRegex(ValueError, 'partition'):
            c.catalogue()

    def test_selectors_do_not_collide_across_stages(self):
        from . import carried_transition_history as transition
        for case in transition.CASES:
            vector = self.source['vectors'][self.source['units']['carried-transition-histories'][case]['negativeVectorSha256']]
            self.assertEqual(c.authored(transition.negative_cases(case)), vector)
            cases = [v['selector']['case'] for v in vector]
            self.assertLess(len(set(cases)), len(cases))
            self.assertEqual(len(vector), len({c.encoded(v['selector']) for v in vector}))

    def test_known_reader_vectors_match_their_own_contracts(self):
        for cohort, module in [('round-histories', 'round_history'), ('carried-data-histories', 'carried_data_history'),
                               ('joint-floor-process', 'process_joint_cohort')]:
            owner = c.module(module)
            for unit in self.source['units'][cohort]:
                self.assertEqual(c.authored(owner.negative_cases(unit)), c.negative_selectors(cohort, unit))
        from . import automatic_history_replay as gate
        for unit in ('higher-ballot-restart', 'reply-revocation'):
            self.assertEqual(c.authored(gate.vector(unit, None)[0]), c.negative_selectors('automatic-histories', unit))

    def test_competition_variants_are_not_elected_using_a_fake_original(self):
        from . import automatic_history_replay as gate
        with patch.object(gate, 'competition_branch', side_effect=AssertionError('no original exists')):
            vector = c.negative_selectors('automatic-histories', 'competition')
        self.assertEqual({'pregrant', 'superseded'}, {v['selector']['variant'] for v in vector})
        self.assertTrue(all(v['condition'] == 'original-competition-' + v['selector']['variant'] for v in vector))
        self.assertTrue(any('{node}' in v['reason'] for v in vector))
        self.assertFalse(any(v['selector']['case'] == 'journal-after-retirement' and
                             v['selector']['variant'] == 'pregrant' for v in vector))

    def test_inspection_is_deterministic_and_read_only(self):
        from . import joining_history_run as h
        with patch.object(h, 'execute', side_effect=AssertionError('audit must not execute')):
            first = c.inspect(); second = c.inspect()
        self.assertEqual(first, second)
        self.assertEqual((486, 552, 246), tuple(first[0][k] for k in
                         ('sourceArchiveUnits', 'plannedHostedHistories', 'plannedExecutionGroups')))
        self.assertIn('scripts/v53/phase3_coverage.py', first[0]['inspectedFiles'])

    def test_output_is_new_only_and_failure_receipt_is_not_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = root/'failed'
            with patch.object(c, 'inspect', side_effect=ValueError('broken selector')):
                with self.assertRaisesRegex(ValueError, 'broken selector'): c.run(output)
            receipt = c.p.decode((output/'receipt.json').read_bytes())
            self.assertEqual('FAIL', receipt['status']); self.assertFalse(receipt['phase3Complete'])
            before = (output/'receipt.json').read_bytes()
            with self.assertRaises(FileExistsError): c.run(output)
            self.assertEqual(before, (output/'receipt.json').read_bytes())

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate key'): c.p.decode('{"status":"PLANNED","status":"PASS"}')


if __name__ == '__main__':
    unittest.main()

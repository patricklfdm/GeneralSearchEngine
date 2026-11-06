"""Synthetic reader-output integration; no test here is native evidence."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from . import phase3_witness_observations as w
from . import phase3_seed_cohort as seeds


def qualification(name, unit):
    if name == 'profiles':
        from .test_profile_matrix import ProfileMatrixTest
        return ProfileMatrixTest.result(unit)
    if name == 'joining-reply-loss':
        from .test_profile_matrix import ProfileMatrixTest
        m = w.c.module('joining_fault_cohort'); ballot = ProfileMatrixTest.result('3-ADD')
        return dict(original=dict(status='PASS', sourceFault=unit, joiningSourceFaultQualified=True,
            fullImplementedCompositionQualified=True, lostReplies=1, recoveredLostReplies=1,
            phase3Complete=False, processDeathQualified=False, ballotPrecondition=ballot['original']),
            originalPreserved=True, ballotQualification=ballot,
            negatives=[dict(case=k, status='REJECTED', reason=v) for k,v in m.gate.NEGATIVES.items()])
    if name == 'remove-process':
        from .test_remove_process_matrix import RemoveProcessMatrixTest
        return RemoveProcessMatrixTest.replay(None, workers=1)
    if name == 'node-renames':
        from .test_node_rename_matrix import NodeRenameMatrixTest
        with tempfile.TemporaryDirectory() as temp:
            raw = Path(temp); (raw/'history').mkdir(); (raw/'history/original-plan.gsbp').write_text(unit)
            return NodeRenameMatrixTest.replay(raw)
    modules = dict(zip(('joining-process','learner-histories','transfer-histories','round-histories',
                       'carried-data-histories','carried-transition-histories','automatic-histories','joint-floor-process'),
                      ('test_joining_process_matrix','test_learner_history_cohort','test_transfer_history','test_round_history',
                       'test_carried_data_history','test_carried_transition_history','test_automatic_history_replay','test_process_joint_cohort')))
    m = w.c.module(modules[name])
    return getattr(m, 'qualification' if name == 'joining-process' else 'result' if name == 'automatic-histories' else 'replay')(unit)


def group_fixture(name, group, ctx, archive_hashes):
    """Known synthetic shapes also used by the 494-archive orchestration test."""
    adapter = seeds.adapters()[name]
    def member(unit):
        field = 'profile' if name == 'profiles' else 'case'
        path = name + '/' + adapter.artifact_name(ctx, 'raw', group)
        if name == 'joining-process': path += '/' + adapter.m.slug(unit)
        return dict(schema=adapter.SCHEMA, context=ctx, **{field: unit}, status='PARTIAL', phase3Complete=False,
            originalFirstDownloadedReplay=True, rawArchiveSha256=archive_hashes[path]['archiveSha256'],
            member=dict(**{field: unit}, status='PASS', phase3Complete=False, qualification=qualification(name, unit)))
    if name == 'joining-process':
        return dict(schema=adapter.SCHEMA, context=ctx, shard=group, stage='verify', status='PARTIAL', phase3Complete=False,
                    cases=[member(unit) for unit in adapter.SHARDS[group]])
    return member(group)


class WitnessObservationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.plan = w.prepare(); cls.adapters = seeds.adapters()
        cls.ctx = dict(run='123', attempt='2', source='a'*40)

    def fixture(self, name, group):
        adapter = self.adapters[name]; root = name + '/' + adapter.artifact_name(self.ctx, 'raw', group)
        paths = [root + '/' + adapter.m.slug(c) for c in adapter.SHARDS[group]] if name == 'joining-process' else [root]
        originals = {path: dict(archiveSha256=w.digest(path.encode())) for path in paths}
        return group_fixture(name, group, self.ctx, originals), originals

    def observe(self, name, group, result=None, originals=None):
        if result is None: result, originals = self.fixture(name, group)
        return w.observe_group(self.plan, name, group, result, self.adapters[name], self.ctx, originals)

    def all_observations(self):
        groups = dict.fromkeys((v['cohort'], v['executionGroup']) for v in self.plan['witnesses'])
        return [v for name, group in groups for v in self.observe(name, group)]

    def test_all_twenty_witnesses_use_actual_owning_output_shapes(self):
        result = w.finish(self.plan, self.all_observations())
        self.assertEqual(20, result['rejected'] + result['notApplicable'])
        self.assertEqual(3, result['notApplicable'])
        self.assertEqual('PARTIAL', result['status'])
        self.assertTrue(all(result[k] is False for k in ('phase3Complete','runtimeQualified','frozenScenarioCoverageQualified')))

    def test_absent_adoption_is_retained_and_never_counted_as_rejection(self):
        result = self.observe('profiles', '3-ADD')
        skipped = [v for v in result if v['outcome'] == 'NOT_APPLICABLE']
        self.assertEqual({'no original adoption transaction','no original adoption promise append'}, {v['reason'] for v in skipped})
        value, originals = self.fixture('profiles', '3-ADD')
        row = next(v for v in value['member']['qualification']['negatives'] if v['case'] == 'adoption-fence-missing')
        row.update(status='REJECTED', reason='joining ballot adoption missing fence')
        with self.assertRaises(ValueError): self.observe('profiles', '3-ADD', value, originals)

    def test_original_first_context_archive_and_owner_are_bound(self):
        changes = [lambda v: v.update(originalFirstDownloadedReplay=False),
                   lambda v: v.update(context=dict(self.ctx, attempt='1')),
                   lambda v: v.update(rawArchiveSha256='0'*64),
                   lambda v: v['member'].update(profile='4-ADD'),
                   lambda v: v.update(status='PASS'), lambda v: v.update(phase3Complete=0)]
        for mutate in changes:
            result, originals = self.fixture('profiles', '3-ADD'); mutate(result)
            with self.assertRaises(ValueError): self.observe('profiles', '3-ADD', result, originals)

    def test_bad_original_and_negative_cannot_be_laundered_by_outer_pass(self):
        for mutate in (lambda q: q['original'].update(ballotCompositionQualified=False),
                       lambda q: q['negatives'].pop(),
                       lambda q: q['negatives'].append(deepcopy(q['negatives'][0])),
                       lambda q: q['negatives'][0].update(reason='unrelated error')):
            value, originals = self.fixture('profiles', '3-ADD'); mutate(value['member']['qualification'])
            with self.assertRaises(ValueError): self.observe('profiles', '3-ADD', value, originals)

    def test_late_prepare_absence_requires_the_original_absence(self):
        name, group = 'node-renames', 'ACCEPT_RENAMED,kill'
        rows = self.observe(name, group)
        self.assertEqual('no original late unused PREPARE', next(v['reason'] for v in rows if v['id'] == 'late-unused-prepare'))
        value, originals = self.fixture(name, group)
        value['member']['qualification']['original']['network']['lateUnusedPrepares'] = [dict(synthetic=True)]
        with self.assertRaises(ValueError): self.observe(name, group, value, originals)
        late = w.c.module('node_late_prepare')
        value['member']['qualification']['negatives'] += [dict(case=k,status='REJECTED',reason=v) for k,v in late.NEGATIVES.items()]
        rows = self.observe(name, group, value, originals)
        self.assertEqual('REJECTED', next(v['outcome'] for v in rows if v['id'] == 'late-unused-prepare'))

    def test_joining_group_never_uses_another_childs_qualification(self):
        witness = next(v for v in self.plan['witnesses'] if v['cohort'] == 'joining-process')
        group = witness['executionGroup']; value, originals = self.fixture('joining-process', group)
        target = next(v for v in value['cases'] if v['case'] == witness['unit'])
        other = next(v for v in value['cases'] if v['case'] != witness['unit'])
        target['member']['qualification'] = deepcopy(other['member']['qualification'])
        with self.assertRaises(ValueError): self.observe('joining-process', group, value, originals)
        value, originals = self.fixture('joining-process', group); value['cases'].pop()
        with self.assertRaisesRegex(ValueError, 'complete joining group'): self.observe('joining-process', group, value, originals)

    def test_missing_duplicate_and_changed_observations_do_not_close(self):
        rows = self.all_observations()
        for changed in (rows[:-1], rows + [rows[0]], [rows[0]] * len(rows)):
            with self.assertRaisesRegex(ValueError, 'complete observed set'): w.finish(self.plan, changed)
        changed = deepcopy(rows); changed[0]['histories'] = []
        with self.assertRaisesRegex(ValueError, 'observed selector binding'): w.finish(self.plan, changed)
        changed = deepcopy(rows); changed[0]['outcome'] = 'PASS'
        with self.assertRaisesRegex(ValueError, 'observed outcome'): w.finish(self.plan, changed)
        changed = deepcopy(rows); changed[0]['reason'] = 'unrelated failure'
        with self.assertRaisesRegex(ValueError, 'final rejection reason'): w.finish(self.plan, changed)
        changed = deepcopy(rows); changed[0]['rawArchiveSha256'] = True
        with self.assertRaisesRegex(ValueError, 'retained reason and provenance'): w.finish(self.plan, changed)


if __name__ == '__main__':
    unittest.main()

import copy
import unittest
from . import initial_current_evidence as c


def fixture(size=3, learner=False):
    rows = []
    for number in range(1, size+1):
        node = 'node-'+str(number)
        for point in ('CURRENT_VALIDATED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED',
                      'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED'):
            rows.append(dict(node=node, event=point))
        if learner: rows.append(dict(node=node, event='LEARNER_RETENTION_RECOVERY_ACTIVE_FORCED'))
        rows.append(dict(node=node, event='RETENTION_RECOVERY_ACTIVE_FORCED'))
    rows.append(dict(node='node-1', event='ALLOCATOR_BEFORE_WRITE'))
    return rows


class InitialCurrentEvidenceTest(unittest.TestCase):
    def test_unused_voters_are_required_in_every_original_size(self):
        for size in (3, 4, 5):
            nodes = tuple('node-'+str(i) for i in range(1, size+1))
            for learner in (False, True):
                with self.subTest(size=size, learner=learner):
                    self.assertEqual(dict(initialVoters=size, currentCallbacks=5*size),
                                     c.validate(fixture(size, learner), nodes))
                    changed = fixture(size, learner)
                    changed.remove(next(v for v in changed if v['node'] == nodes[-1] and v['event'] == 'CURRENT_FILES_FORCED'))
                    with self.assertRaisesRegex(ValueError, '^'+c.ORDER_ERROR+'$'): c.validate(changed, nodes)

    def test_later_complete_installation_cannot_replace_initial_open(self):
        rows = fixture(); missing = [v for v in rows if v['node'] == 'node-1' and v['event'].startswith('CURRENT_')]
        rows = [v for v in rows if v not in missing]
        rows += [dict(node='node-1', event='INSTALL_PARENT_FORCED'), *missing,
                 dict(node='node-1', event='INSTALL_BEFORE_RETURN')]
        with self.assertRaisesRegex(ValueError, '^'+c.ORDER_ERROR+'$'): c.validate(rows, ('node-1','node-2','node-3'))

    def test_original_blocks_can_interleave_without_cross_owner_borrowing(self):
        rows = fixture(); blocks = [rows[i:i+6] for i in (0,6,12)]
        changed = [blocks[n][i] for i in range(6) for n in range(3)]+[rows[-1]]
        c.validate(changed, ('node-1','node-2','node-3'))
        changed[4]['node'] = 'node-1'
        with self.assertRaisesRegex(ValueError, '^'+c.ORDER_ERROR+'$'): c.validate(changed, ('node-1','node-2','node-3'))

    def test_protocol_activity_cannot_start_while_other_voters_are_still_opening(self):
        for activity in ('NETWORK_SEND', 'NETWORK_REQUEST', 'BEFORE_REQUEST_WRITE', 'AFTER_REQUEST_READ',
                         'ALLOCATOR_BEFORE_WRITE', 'CURRENT_BEFORE_CAPTURE'):
            rows = fixture(); rows.insert(6, dict(node='node-1', event=activity))
            with self.subTest(activity=activity), self.assertRaisesRegex(ValueError, '^'+c.READY_ERROR+'$'):
                c.validate(rows, ('node-1','node-2','node-3'))

    def test_exact_scope_and_shape_and_boundary_are_required(self):
        for change in ('scope', 'field', 'missing-boundary', 'entire-owner'):
            rows = fixture()
            if change == 'scope': rows[1]['scope'] = None
            elif change == 'field': rows[1]['files'] = 3
            elif change == 'missing-boundary': rows.pop(5)
            else: rows = [v for v in rows if v['node'] != 'node-2']
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, '^'+c.ORDER_ERROR+'$'):
                c.validate(rows, ('node-1','node-2','node-3'))

    def test_boundaries_cannot_be_satisfied_by_extra_or_unknown_callbacks(self):
        for point in ('CURRENT_FILES_FORCED', 'CURRENT_UNKNOWN', 'CURRENT_BEFORE_CAPTURE'):
            rows = fixture(); rows.insert(4, dict(node='node-1', event=point))
            with self.subTest(point=point), self.assertRaisesRegex(ValueError, '^'+c.ORDER_ERROR+'$'):
                c.validate(rows, ('node-1','node-2','node-3'))

    def test_all_retained_negative_variants_reach_exact_reason(self):
        for learner in (False, True):
            for name, reason in c.NEGATIVES.items():
                rows = fixture(5, learner); before = copy.deepcopy(rows); c.mutate(rows, name)
                with self.subTest(name=name, learner=learner), self.assertRaisesRegex(ValueError, '^'+reason+'$'):
                    c.validate(rows, tuple('node-'+str(i) for i in range(1,6)))
                self.assertNotEqual(before, rows)

    def test_nodes_come_from_original_model_not_from_remaining_callbacks(self):
        for nodes in ((), ('node-1','node-1'), ('node-1',None)):
            with self.subTest(nodes=nodes), self.assertRaisesRegex(ValueError, '^initial current original voters$'):
                c.validate(fixture(), nodes)


if __name__ == '__main__': unittest.main()

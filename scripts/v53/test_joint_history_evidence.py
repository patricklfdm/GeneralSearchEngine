"""Interrupted floor coverage and original-first whole-history qualification."""
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import joint_history_evidence as j


def row(event,node=j.recovered.NODE,**values):return dict(node=node,event=event,**values)


class JointHistoryTest(unittest.TestCase):
    def events(self):
        return [row('FLOOR_RESERVED'),row('FLOOR_COPIES_FORCED'),row('FLOOR_RESERVED'),
                row('FLOOR_BEFORE_RETURN'),row('RETIREMENT_RESERVED'),row('RETIREMENT_BEFORE_RETURN'),
                row('FLOOR_RELEASE_BEFORE_RETURN')]

    def test_only_declared_resume_can_overlap_and_all_retirement_remains_covered(self):
        events=self.events()
        events[1:1]=[row('FLOOR_RESERVED','node-1'),row('SOURCE_RETIREMENT_CREATED','node-1'),
                     row('SOURCE_RETIREMENT_BEFORE_RETURN','node-1'),row('FLOOR_RELEASE_BEFORE_RETURN','node-1')]
        self.assertEqual(4,j.retirement_coverage(events,6))
        for mode,reason in (('extra','unexplained overlapping'),('orphan','unbound retirement'),
                            ('missing','incomplete floor'),('foreign','exact resumed reservation'),
                            ('release','release without reservation')):
            changed=copy.deepcopy(self.events())
            if mode=='extra':changed.insert(4,row('FLOOR_RESERVED'))
            elif mode=='orphan':changed.append(row('RETIREMENT_BEFORE_RETURN'))
            elif mode=='missing':changed.pop()
            elif mode=='foreign':changed[2]['node']='node-1'
            else:changed.append(row('FLOOR_RELEASE_BEFORE_RETURN'))
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,reason):j.retirement_coverage(changed,2)

    def test_resume_requires_the_original_reservation_still_active(self):
        events=self.events();events[0]['event']='REMOVED_RESERVATION'
        with self.assertRaisesRegex(ValueError,'unexplained overlapping'):j.retirement_coverage(events,2)
        events=self.events();events[1]['event']='FLOOR_RELEASE_BEFORE_RETURN'
        with self.assertRaisesRegex(ValueError,'unexplained overlapping'):j.retirement_coverage(events,2)

    def test_recovered_floor_boundary_is_unique(self):
        reader=SimpleNamespace(events=self.events())
        with patch.object(j.recovered,'boundary',return_value=(1,6)):
            actual=j.Replay(reader);self.assertEqual((0,2),(actual.interrupted,actual.resumed))
            for events in (self.events()[1:],self.events()[:4]+[row('FLOOR_RESERVED')]+self.events()[4:]):
                with self.subTest(events=events),self.assertRaisesRegex(ValueError,'exact interrupted floor boundary'):
                    j.Replay(SimpleNamespace(events=events))

    def test_qualification_cannot_count_original_failure_as_negative_success(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(j,'validate',side_effect=ValueError('bad original')),patch.object(j,'mutate') as mutation:
            with self.assertRaisesRegex(ValueError,'^bad original$'):j.qualify(Path(tmp))
            mutation.assert_not_called()

    def test_unknown_mutation_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'unknown mutation'):j.mutate(tmp,'unknown')
            self.assertEqual([],list(Path(tmp).iterdir()))

    def test_negative_requires_its_exact_reason_and_preserves_original(self):
        name='selection-before-cold';reason=j.NEGATIVES[name][1]
        for outcome in (None,ValueError('unrelated'),ValueError(reason)):
            with self.subTest(outcome=outcome),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'events.json').write_bytes(b'[]');(root/'protected').write_bytes(b'original')
                before=j.h.inventory(root)
                def mutation(changed,case):
                    (changed/'events.json').write_bytes(j.f.canonical([row('SELECTED_FORCED',scope='foreign')]))
                with patch.object(j,'mutate',side_effect=mutation),patch.object(j,'lifetimes',return_value={}), \
                     patch.object(j.e.n,'network',side_effect=outcome):
                    if outcome is not None and str(outcome)==reason:
                        self.assertEqual('REJECTED',j.negative(root,name,before)['status'])
                    else:
                        with self.assertRaisesRegex(ValueError,'mutation accepted' if outcome is None else 'unrelated rejection'):
                            j.negative(root,name,before)
                self.assertEqual(before,j.h.inventory(root))

    def test_negative_cannot_edit_other_physical_inputs_or_remain_unchanged(self):
        for change in (False,True):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'events.json').write_bytes(b'[]');(root/'protected').write_bytes(b'original')
                before=j.h.inventory(root)
                def mutation(changed,case):
                    if change:(changed/'protected').write_bytes(b'changed')
                with patch.object(j,'mutate',side_effect=mutation),patch.object(j.e.n,'network') as network:
                    with self.assertRaisesRegex(ValueError,'mutation changed protected inputs'):
                        j.negative(root,'selection-before-cold',before)
                    network.assert_not_called()


if __name__=='__main__':unittest.main()

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import capacity_completion_evidence as q
from . import offline_fixture_image as image


class CapacityCompletionTest(unittest.TestCase):
    def test_invalid_original_never_counts_as_negative_qualification(self):
        with patch.object(q,'validate',side_effect=ValueError('original failure')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original failure'):q.qualify('unused','capacity-231')
            copied.assert_not_called()

    def test_missing_and_linked_original_roots_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'raw'
            with self.assertRaisesRegex(ValueError,'completion original root'):q.validate(root,'replay-smoke-1')
            root.symlink_to(temp,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'completion original root'):q.validate(root,'replay-smoke-1')

    def test_smoke_receipt_cannot_be_admitted_as_capacity_or_select_its_own_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'receipt.json').write_bytes(q.e.f.canonical(q.receipt('replay-smoke-1')))
            with patch.object(q,'Walk') as walk:
                with self.assertRaisesRegex(ValueError,'completion receipt/profile'):q.validate(root,'capacity-231')
                walk.assert_not_called()
            for unknown in ('auto','capacity-1','replay-smoke-231'):
                with self.assertRaisesRegex(ValueError,'completion explicit profile'):q.receipt(unknown)

    def test_legacy_receipt_cannot_qualify_without_new_original_resource_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for version in (2,3):
                value=q.receipt('replay-smoke-1');value['schema']=f'gse-v53-capacity-completion-v{version}'
                (root/'receipt.json').write_bytes(q.e.f.canonical(value))
                with self.subTest(version=version),patch.object(q,'Walk') as walk:
                    with self.assertRaisesRegex(ValueError,'completion receipt/profile'):q.validate(root,'replay-smoke-1')
                    walk.assert_not_called()

    def test_every_call_requires_its_ordered_forces_returns_and_actual_owner(self):
        phases={kind+'-6':q.NODES for kind in q.CRITICAL}
        calls=[dict(operation=label,node=n,events=['OPEN_VALIDATED',*q.CRITICAL[label.rsplit('-',1)[0]],'CLOSED'])
               for label,nodes in phases.items() for n in nodes]
        q.validate_calls(calls,phases)
        for index,call in enumerate(calls):
            for position in range(1,len(call['events'])-1):
                bad=copy.deepcopy(calls);bad[index]['events'].pop(position)
                with self.assertRaisesRegex(ValueError,'completion force before return'):q.validate_calls(bad,phases)
            bad=copy.deepcopy(calls);bad[index]['events'].reverse()
            with self.assertRaisesRegex(ValueError,'completion force before return'):q.validate_calls(bad,phases)
            bad=copy.deepcopy(calls);bad[index]['node']='node-4'
            with self.assertRaisesRegex(ValueError,'completion exact call coverage'):q.validate_calls(bad,phases)
        for bad in (calls[1:],calls+calls[:1],list(reversed(calls))):
            with self.assertRaisesRegex(ValueError,'completion exact call coverage'):q.validate_calls(bad,phases)

    def test_index_expectations_are_explicit_and_keep_kind_field_analyzer_and_order(self):
        def encoded(values):return b''.join(bytes([kind])+image.core.lp(field)+image.core.lp(analyzer) for kind,field,analyzer in values)
        for expected in (((1,'value',''),),q.INITIAL_INDEXES,q.FINAL_INDEXES):
            cursor=image.core.Cursor(encoded(expected));image.fixture_indexes(cursor,len(expected),expected);cursor.finish()
            for changed in (expected[:-1],expected+expected[:1],((4,expected[0][1],''),*expected[1:]),
                            ((expected[0][0],'other',''),*expected[1:]),((expected[0][0],expected[0][1],'other'),*expected[1:])):
                with self.assertRaisesRegex(ValueError,'cross-view application indexes'):
                    image.fixture_indexes(image.core.Cursor(encoded(changed)),len(changed),expected)
        with self.assertRaisesRegex(ValueError,'cross-view application indexes'):
            image.fixture_indexes(image.core.Cursor(encoded(q.INITIAL_INDEXES)),2,q.FINAL_INDEXES)

    def test_existing_cross_view_uses_the_original_single_index_oracle(self):
        walk=q.cross.Walk.__new__(q.cross.Walk);walk.history=q.HISTORY
        with patch.object(q.cross,'application') as original:
            walk.verify_application(b'image',42,[(7,'old')]);original.assert_called_once_with(b'image',q.HISTORY,42,[(7,'old')])

    def test_requested_command_does_not_accept_a_linked_original(self):
        with tempfile.TemporaryDirectory() as temp:
            walk=q.Walk.__new__(q.Walk);walk.root=Path(temp);walk.required=set()
            (walk.root/'other.gsr').write_bytes(b'entry');(walk.root/'entry-6.gsr').symlink_to('other.gsr')
            (walk.root/'payload-6.bin').write_bytes(b'')
            with self.assertRaisesRegex(ValueError,'file type/capacity'):walk.requested(6,b'entry',b'')


if __name__=='__main__':unittest.main()

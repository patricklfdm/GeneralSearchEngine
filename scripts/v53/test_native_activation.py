"""Fail-closed ordering and force evidence checks for native activation replay."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_activation_evidence as q


class NativeActivationEvidenceTest(unittest.TestCase):
    def test_invalid_original_never_counts_as_a_rejected_mutation(self):
        with patch.object(q,'validate',side_effect=ValueError('original failed')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original failed'):q.qualify('missing')
            copied.assert_not_called()

    def test_case_rebuilds_original_history_before_selection_or_network(self):
        with (patch.object(q.b.selection,'layout'),patch.object(q,'original',side_effect=ValueError('original proof')),
              patch.object(q,'installation') as installed,patch.object(q,'network') as network):
            with self.assertRaisesRegex(ValueError,'original proof'):q.case('raw',3,False)
            installed.assert_not_called();network.assert_not_called()

    def test_all_six_profiles_are_required_before_any_profile_replay(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(q,'case') as case:
            root=Path(temp)
            for size,backup in q.PROFILES[:-1]:(root/q.name(size,backup)).mkdir()
            with self.assertRaisesRegex(ValueError,'native activation profiles inventory'):q.validate(root)
            case.assert_not_called()

    def test_read_rejects_linked_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'actual').write_text('{}');(root/'linked').symlink_to(root/'actual')
            with self.assertRaises(ValueError):q.read(root/'linked')

    def test_equal_numeric_flag_is_not_a_boolean_receipt(self):
        with self.assertRaisesRegex(ValueError,'scope'):q.same({'publicRuntime':False},{'publicRuntime':0},'scope')

    @staticmethod
    def force_rows():
        required=['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN','SELECTED_FORCED','SELECTED_BEFORE_RETURN',
                  'INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN']
        rows=[dict(node='node-1',events=['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN']+required),
              dict(node='node-2',events=list(required)),dict(node='node-3',events=['CURRENT_VALIDATED'])]
        reopened=[dict(node=f'node-{n}',operation='native-final',events=['CURRENT_VALIDATED','CURRENT_FILES_FORCED',
            'CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED','ACCEPT_ACTIVE_FORCED',
            'ACCEPT_ACTIVE_PARENT_FORCED']) for n in (1,2,3)]
        return rows,reopened

    def check_forces(self,rows,reopened):
        with patch.object(q,'read',side_effect=[rows,reopened]):q.forces(Path('raw'),['node-1','node-2','node-3'],['node-1','node-2'])

    def test_installation_return_requires_the_original_prior_forces(self):
        rows,reopened=self.force_rows();self.check_forces(rows,reopened)
        for mode in ('missing','reordered','duplicate'):
            changed=copy.deepcopy(rows);events=changed[1]['events']
            if mode=='missing':events.remove('INSTALL_PARENT_FORCED')
            elif mode=='reordered':events[-1],events[-2]=events[-2],events[-1]
            else:events.append('INSTALL_BEFORE_RETURN')
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'force order'):self.check_forces(changed,reopened)

    def test_unselected_voter_cannot_gain_an_installation(self):
        rows,reopened=self.force_rows();rows[2]['events'].append('INSTALL_BEFORE_RETURN')
        with self.assertRaisesRegex(ValueError,'unselected force'):self.check_forces(rows,reopened)

    def test_reopen_cannot_drop_a_node_or_change_its_identity(self):
        rows,reopened=self.force_rows()
        for mode in ('missing','identity','force'):
            changed=copy.deepcopy(reopened)
            if mode=='missing':changed.pop()
            elif mode=='identity':changed[0]['node']='node-2'
            else:changed[0]['events'].remove('CURRENT_DIRECTORY_FORCED')
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'reopen events'):self.check_forces(rows,changed)


if __name__=='__main__':unittest.main()

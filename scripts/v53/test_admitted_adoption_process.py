"""Do not let a malformed original masquerade as a successful crash mutation."""
import unittest
from unittest.mock import patch
from . import admitted_adoption_process_evidence as e


class AdmittedAdoptionProcessTest(unittest.TestCase):
    def test_backup_source_is_not_an_admitted_target_path(self):
        descriptor=dict(source='VERIFIED_DURABLE_BACKUP',identities=[dict(node='node-1'),dict(node='node-2')],
                        paths=[dict(path=p) for p in ('operation','source','one','core-one','two','core-two')])
        self.assertEqual(dict(node='two',materialization='core-two'),e.target_paths(descriptor,'node-2'))
        self.assertEqual(dict(node='one',materialization='core-one'),e.target_paths(descriptor,'node-1'))
        descriptor['source']='EMPTY';descriptor['paths'].pop(1)
        self.assertEqual(dict(node='two',materialization='core-two'),e.target_paths(descriptor,'node-2'))

    def test_original_target_identity_is_required(self):
        with self.assertRaisesRegex(ValueError,'target identity'):
            e.target_paths(dict(identities=[dict(node='node-1')]),'node-2')

    def test_original_matrix_is_required_before_any_negative_copy(self):
        with patch.object(e,'validate',side_effect=ValueError('original incomplete')),patch('shutil.copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original incomplete'):e.qualify('missing')
            copied.assert_not_called()

    def test_transaction_refuses_unrelated_durable_journal_replacement(self):
        before={'selector.gsr':b'old','grants.gsr':b'prior'}
        after={'selector.gsr':b'new','grants.gsr':b'other'}
        with self.assertRaisesRegex(ValueError,'retained journal prefix'):e.transaction(before,after)

    def test_duplicate_cannot_drop_retained_original_authority(self):
        before={'selector.gsr':b'same','grants.gsr':b'prior','root.gsr':b'original'}
        after={'selector.gsr':b'same','grants.gsr':b'prior'}
        with self.assertRaisesRegex(ValueError,'final transaction'):e.transaction(before,after)

    def test_requested_cut_must_actually_be_executed(self):
        same={'selector.gsr':b'same','grants.gsr':b'prior'}
        with self.assertRaisesRegex(ValueError,'missing cut'):e.transaction(same,same,'PROMISE_FORCED')


if __name__=='__main__':unittest.main()

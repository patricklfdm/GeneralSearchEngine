from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import completion_prefix_component as c


class CompletionPrefixComponentTest(unittest.TestCase):
    def test_invalid_original_never_starts_negative_work(self):
        with patch.object(c,'validate',side_effect=ValueError('original failed')),patch.object(c.p,'mutate') as mutate,\
                patch.object(c.p.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'^original failed$'):c.qualify('/unused')
        mutate.assert_not_called();inventory.assert_not_called()

    def test_unrelated_negative_failure_cannot_earn_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'captures').mkdir()
            with patch.object(c,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(c.p,'mutate'),\
                    patch.object(c.p,'PHYSICAL',{'one':None}),patch.object(c.p,'NEGATIVES',{'one':'expected'}):
                with self.assertRaisesRegex(ValueError,'^completion component unrelated negative: one: unrelated$'):c.qualify(temp)

    def test_accepted_mutation_cannot_earn_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'captures').mkdir()
            with patch.object(c,'validate',return_value={}),patch.object(c.p,'mutate'),patch.object(c.p,'PHYSICAL',{'one':None}):
                with self.assertRaisesRegex(ValueError,'^completion component accepted mutation: one$'):c.qualify(temp)

    def test_boolean_case_number_cannot_masquerade_as_data_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'result.json').write_bytes(c.p.f.canonical(dict(schema='gse-v53-completion-prefix-component-v1',at=False,
                pid=1,root='0'*64,protocolAuthority='conditional-initial-history',nativeCarriedProcess=False)))
            with self.assertRaisesRegex(ValueError,'^completion component scope$'):c.validate(root)


if __name__=='__main__':unittest.main()

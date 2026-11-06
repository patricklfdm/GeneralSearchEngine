from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import ledger_prefix_component as c


class LedgerPrefixComponentTest(unittest.TestCase):
    def raw(self,revision=0):
        meta=dict(root='a'*64,owner=dict(node='node-1',storage='00000000-0000-0000-0000-000000000001'),
                  revision=revision,previous=None,parent=None,peers=[])
        return c.p.model.retention.future.future.frame(meta,{})

    def test_empty_future_frame_is_checked_and_roundtrips(self):
        raw=self.raw();self.assertEqual(0,c.metadata(raw,'future')['revision'])
        for changed in (raw[:-1],raw[:12]+b'\0'*32+raw[44:],raw+b'trailing'):
            with self.assertRaises(ValueError):c.metadata(changed,'future')

    def test_boolean_future_revision_is_not_an_integer(self):
        with self.assertRaisesRegex(ValueError,'^ledger component future metadata$'):c.metadata(self.raw(False),'future')

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
                with self.assertRaisesRegex(ValueError,'^ledger component unrelated negative: one: unrelated$'):c.qualify(temp)

    def test_accepted_mutation_cannot_earn_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'captures').mkdir()
            with patch.object(c,'validate',return_value={}),patch.object(c.p,'mutate'),patch.object(c.p,'PHYSICAL',{'one':None}):
                with self.assertRaisesRegex(ValueError,'^ledger component accepted mutation: one$'):c.qualify(temp)

    def test_component_cannot_claim_native_protocol_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'result.json').write_bytes(c.p.f.canonical(dict(schema='gse-v53-ledger-prefix-component-v1',cases=[],pid=1,
                root='0'*64,expectedBytes='conditional-transaction-snapshots',nativeCarriedProcess=True)))
            with self.assertRaisesRegex(ValueError,'^ledger component scope$'):c.validate(root)


if __name__=='__main__':unittest.main()

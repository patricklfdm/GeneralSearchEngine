import unittest
from unittest.mock import patch
from . import native_dispatch_evidence as evidence


class NativeDispatchEvidenceTest(unittest.TestCase):
    def test_only_exact_original_local_image_bytes_allow_omitting_download(self):
        first, second = b'original application one', b'original application two'
        h1, h2 = evidence.e.digest(first), evidence.e.digest(second)
        members = {'source.gscp': b'packet', h1+'.image': first, h2+'.image': second}
        packet = {'images': {h1: len(first), h2: len(second)}}
        for local in ({}, {h1+'.image': b'changed'}, {h1: first}):
            full, borrowed = evidence.prefix_transfers('cut', members, packet, local)
            self.assertEqual(full, borrowed)
        full, borrowed = evidence.prefix_transfers('cut', members, packet, {h1+'.image': first})
        self.assertEqual(3, len(full))
        self.assertEqual([('cut', b'packet', 'CAPSULE'), (h2, second, 'APPLICATION')], borrowed)
        full, borrowed = evidence.prefix_transfers('cut', members, packet, members)
        self.assertEqual([('cut', b'packet', 'CAPSULE')], borrowed)

    def test_invalid_original_stops_before_any_negative_is_generated(self):
        with patch.object(evidence, 'validate', side_effect=ValueError('invalid original')) as original:
            with patch.object(evidence.tempfile, 'TemporaryDirectory') as mutations:
                with self.assertRaisesRegex(ValueError, '^invalid original$'):
                    evidence.qualify('invalid-root')
                original.assert_called_once_with('invalid-root')
                mutations.assert_not_called()


if __name__ == '__main__':
    unittest.main()

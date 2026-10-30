import unittest
from unittest.mock import patch
from . import native_dispatch_evidence as evidence


class NativeDispatchEvidenceTest(unittest.TestCase):
    def test_finite_identical_activation_replies_can_have_different_event_positions(self):
        rows = [('SELECTED', {'trace':'same'}, 'INSTALL_ACK', {'selection':'original'}, at) for at in (10,20,30)]
        self.assertEqual(rows, evidence.activation_attempts(rows))

    def test_missing_and_exhausted_activation_attempts_reject(self):
        for rows in ([], [('SELECTED', {}, 'INSTALL_ACK', {}, 1)]*4):
            with self.assertRaisesRegex(ValueError, '^native dispatch activation controls$'):
                evidence.activation_attempts(rows)

    def test_activation_retry_cannot_change_request_or_acknowledgement(self):
        original = ('SELECTED', {'trace':'original'}, 'INSTALL_ACK', {'selection':'original'}, 10)
        for changed in [('SELECTED', {'trace':'other'}, 'INSTALL_ACK', {'selection':'original'}, 20),
                        ('SELECTED', {'trace':'original'}, 'INSTALL_ACK', {'selection':'other'}, 20)]:
            with self.assertRaisesRegex(ValueError, '^native dispatch activation controls$'):
                evidence.activation_attempts([original, changed])

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

    def test_packet_only_maintenance_requires_every_original_local_image(self):
        images = [b'original one', b'original two']
        members = {'source.gscp': b'original packet', **{evidence.e.digest(raw)+'.image': raw for raw in images}}
        packet = dict(capsule=dict(root='root-a', cut=dict(index=1, entry='entry-a')),
                      images={evidence.e.digest(raw): len(raw) for raw in images})
        reference = evidence.current_reference(packet['capsule'], 'retained-current-packet')
        expected = [(reference, b'original packet', 'CAPSULE')]
        for local in ({}, {evidence.e.digest(images[0])+'.image': images[0]},
                      dict(members, **{evidence.e.digest(images[1])+'.image': b'wrong bytes'})):
            self.assertNotIn(expected, evidence.maintenance_prefixes(members, packet, local))
        self.assertIn(expected, evidence.maintenance_prefixes(members, packet, members))

    def test_generation_metadata_alias_keeps_every_original_metadata_member(self):
        members = {'source.gscp': b'packet', 'ancestry.gsr': b'ancestry', 'promise.gsr': b'promise',
                   'selected.gsr': b'selected', 'application.image': b'image'}
        packet = dict(capsule=dict(root='root-a', cut=dict(index=1, entry='entry-a')))
        variants = evidence.maintenance_generations(b'manifest', members, packet)
        self.assertEqual(2, len(variants))
        self.assertNotEqual(variants[0][0][0], variants[1][0][0])
        for records in variants:
            self.assertEqual([b'manifest', b'ancestry', b'promise', b'selected'], [row[1] for row in records])
            self.assertTrue(all(row[2]=='RECORD' for row in records))
        self.assertEqual(variants[0][1:], variants[1][1:])

    def test_current_lookup_aliases_are_bound_to_root_cut_and_export_scope(self):
        cap = dict(root='root-a', cut=dict(index=1, entry='entry-a'))
        packet = evidence.current_reference(cap, 'retained-current-packet')
        for other in (dict(cap, root='root-b'), dict(cap, cut=dict(index=2, entry='entry-b'))):
            self.assertNotEqual(packet, evidence.current_reference(other, 'retained-current-packet'))
        self.assertNotEqual(packet, evidence.current_reference(cap, 'retained-current-generation-metadata'))


if __name__ == '__main__':
    unittest.main()

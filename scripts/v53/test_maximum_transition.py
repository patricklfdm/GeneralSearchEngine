"""Pressure evidence must preserve the same original and its narrow scope."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import maximum_transition_evidence as m
from .test_source_packet import fixture, frame


def receiver_fixture():
    cap, index, objects = fixture(); packet = frame(cap, m.e.f.canonical(index), objects)
    image = b'independent image'; files = {f'images/{n}.image': image for n in range(7)}
    path = 'generations/a/source.gscp'; files[path] = packet
    files['sources/first/source.gscp'] = packet
    baseline = m.usage(files, len(image)); refused = copy.deepcopy(baseline)
    refused.update(metadata=baseline['metadata'] + len(packet), staging=baseline['staging'] + len(packet), queued=4096, leases=18)
    refused['counts'].update(LEARNER=1, CONTROL=1)
    hashes = [dict(path=n, sha256=m.e.digest(v)) for n, v in sorted(files.items())]
    value = dict(schema='gse-v53-maximum-receiver-v1', reason='resource ownership/count', packet=path,
                 packetSha256=m.e.digest(packet), packetBytes=len(packet), authorityBefore=hashes, authorityAfter=copy.deepcopy(hashes),
                 states=[dict(stage='before', usage=baseline), dict(stage='refused', usage=refused),
                         dict(stage='closed', usage=copy.deepcopy(baseline))], scratchAbsent=True)
    return value, files, len(image)


def source_at(index, cut=None):
    cap, inventory, objects = fixture(); value = m.e.f.decode(cap, 'records', 'CAPSULE')
    catalog = m.e.f.decode(objects.pop(value['catalog']), 'records', 'CATALOG')
    catalog['cut'] = copy.deepcopy(cut or dict(catalog['cut'], index=index)); value['cut'] = catalog['cut']
    raw = m.e.f.encode('records', 'CATALOG', catalog); objects[m.e.digest(raw)] = raw; value['catalog'] = m.e.digest(raw)
    return m.c.packet_bytes(value, objects, {row['sha256']: row['bytes'] for row in inventory['images']})


class MaximumTransitionTest(unittest.TestCase):
    def test_current_install_derives_prefix_without_changing_historical_default(self):
        from .test_native_activation import NativeActivationEvidenceTest
        members, packet, root = NativeActivationEvidenceTest.materialization_fixture(); before = copy.deepcopy((members, packet))
        current = m.Walk.__new__(m.Walk); historical = m.q.Walk.__new__(m.q.Walk)
        self.assertEqual(members['source.gscp'], historical.installed_packet(members, packet, root))
        derived = m.c.p.decode(current.installed_packet(members, packet, root))
        self.assertEqual(set(packet['objects']) - {m.e.digest(b'')}, set(derived['objects']))
        self.assertEqual(packet['images'], derived['images']); self.assertEqual(before, (members, packet))

    def test_current_install_cannot_get_missing_authority_from_output(self):
        from .test_native_activation import NativeActivationEvidenceTest
        members, packet, root = NativeActivationEvidenceTest.materialization_fixture()
        for key in (packet['capsule']['catalog'], packet['capsule']['initial'], m.e.digest(root)):
            changed = copy.deepcopy(packet); del changed['objects'][key]
            with self.assertRaises(ValueError): m.Walk.__new__(m.Walk).installed_packet(members, changed, root)

    def test_publication_uses_survivor_sources_and_both_first_slot_endpoints(self):
        walk = m.Walk.__new__(m.Walk); walk.active = ['node-1', 'node-5']
        one, two = source_at(1), source_at(2)
        walk.group = {'node-1': {'sources/a/source.gscp': one}, 'node-5': {'sources/b/source.gscp': source_at(0)}}
        walk.first = dict(parent=m.c.anchor(m.c.p.decode(one)['capsule']), end=m.c.anchor(m.c.p.decode(two)['capsule']))
        self.assertEqual([1, 2], [v['cut']['index'] for v in walk.required_anchors()])
        walk.first['parent']['catalog'] = 'ff'*32
        with self.assertRaisesRegex(ValueError, 'conflicting retained anchor'): walk.required_anchors()

    def test_removed_owner_retains_its_own_hidden_source_not_new_owner_obligations(self):
        from .test_admitted_campaign_ancestry import fixture as ancestry_fixture
        packet, hidden, bridge = ancestry_fixture(); files = {'sources/a/source.gscp': source_at(1, hidden)}
        members = {'ancestry.gsr': bridge}; walk = m.Walk.__new__(m.Walk)
        self.assertEqual(bridge, walk.adoption_ancestry(files, members, packet))
        self.assertEqual(b'', m.q.Walk.__new__(m.q.Walk).adoption_ancestry(files, members, packet))
        for bad in ({}, {'ancestry.gsr': bridge[:-1]}, {'ancestry.gsr': bridge+bridge}):
            with self.assertRaises(ValueError): walk.adoption_ancestry(files, bad, packet)

    def test_real_packet_declares_image_extent_and_exact_failed_receive_charges(self):
        value, files, extent = receiver_fixture()
        self.assertEqual(files[value['packet']], m.receiver(value, files, extent))
        before, refused, closed = [row['usage'] for row in value['states']]
        self.assertEqual(before, closed); self.assertEqual(before['staging'] + value['packetBytes'], refused['staging'])
        self.assertEqual(4096, refused['queued']); self.assertEqual(7, refused['counts']['APPLICATION'])

    def test_all_sixteen_negatives_reject_without_mutating_originals(self):
        value, files, extent = receiver_fixture(); saved = copy.deepcopy((value, files))
        result = m.receiver_negatives(value, files, extent)
        self.assertEqual(16, len(result)); self.assertEqual(16, len({v['case'] for v in result}))
        self.assertTrue(all(v['status'] == 'REJECTED' for v in result)); self.assertEqual(saved, (value, files))

    def test_invalid_original_never_counts_as_rejections(self):
        value, files, extent = receiver_fixture(); value['scratchAbsent'] = False
        with self.assertRaisesRegex(ValueError, 'maximum transition exact receiver refusal'):
            m.receiver_negatives(value, files, extent)
        with patch.object(m, '_validate', side_effect=ValueError('original failed')), patch.object(m, 'receiver_negatives') as negatives:
            with self.assertRaisesRegex(ValueError, 'original failed'): m.qualify('absent')
            negatives.assert_not_called()

    def test_unrelated_negative_failure_does_not_pass(self):
        value, files, extent = receiver_fixture(); original = m.receiver
        def wrong(changed, *args):
            if changed != value: raise ValueError('unrelated failure')
            return original(changed, *args)
        with patch.object(m, 'receiver', side_effect=wrong):
            with self.assertRaisesRegex(ValueError, 'unrelated negative'): m.receiver_negatives(value, files, extent)

    def test_accepted_mutation_fails_qualification(self):
        value, files, extent = receiver_fixture()
        with patch.object(m, 'receiver', return_value=b'ignored'):
            with self.assertRaisesRegex(ValueError, 'accepted mutation'): m.receiver_negatives(value, files, extent)

    def test_packet_bytes_not_a_receipt_claim_control_image_requirement(self):
        value, files, extent = receiver_fixture()
        with self.assertRaisesRegex(ValueError, 'receiver image binding'): m.receiver(value, files, extent + 1)
        bad = dict(files); bad[value['packet']] = bad[value['packet']][:-1]
        with self.assertRaises(ValueError): m.receiver(value, bad, extent)

    def test_seven_complete_images_are_required_not_reserved_byte_claims(self):
        _, files, extent = receiver_fixture()
        for changed in ({k: v for k, v in files.items() if k != 'images/0.image'},
                        dict(files, **{'extra.image': b'x'*extent}), dict(files, **{'images/1.image': b'x'})):
            with self.assertRaisesRegex(ValueError, 'seven images'): m.usage(changed, extent)

    def test_diagnostic_receipt_cannot_claim_maximum_or_runtime(self):
        value = dict(schema='gse-v53-maximum-transition-v1', status='DIAGNOSTIC', mode='diagnostic', imageBytes=123,
                     finalValueBytes=-1, slots=10, voters=4, generation=1, peakImages=7, publicRuntime=False, phase3Complete=False)
        m.receipt(value, 'diagnostic', 123, -1)
        for key, replacement in [('status', 'PASS'), ('mode', 'maximum'), ('publicRuntime', True), ('phase3Complete', True),
                                 ('slots', 9), ('voters', 5), ('generation', 0), ('imageBytes', m.maximum.NATIVE_MAXIMUM)]:
            with self.assertRaisesRegex(ValueError, 'maximum transition receipt'):
                m.receipt(dict(value, **{key: replacement}), 'diagnostic', 123, -1)

    def test_default_mode_refuses_small_diagnostic_layout_before_replay(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'publication') as replay:
            root = Path(tmp)
            for name in ('source.image', 'source-backup', 'publication', 'seven-image-floor', 'peak.json', 'typed-final',
                         'receipt.json', 'receiver.json', 'receiver-refused'): (root/name).touch()
            with self.assertRaises(ValueError): m.validate(root)
            replay.assert_not_called()

    def test_exact_calls_reject_missing_extra_or_reordered_operations(self):
        rows = [dict(node=n, operation=o, events=['OPEN']) for n, o in m.call_order()]
        m.calls(rows, {})
        for changed in (rows[:-1], rows + rows[-1:], [rows[1], rows[0], *rows[2:]]):
            with self.assertRaisesRegex(ValueError, 'maximum transition (complete call inventory|call order)'): m.calls(changed, {})
        without_ancestry = [v for v in rows if v['operation'] != 'publication-original-ancestry']
        with self.assertRaisesRegex(ValueError, 'complete call inventory'): m.calls(without_ancestry, {})

    def test_force_return_is_not_a_substitute_for_durability(self):
        rows = [dict(node=n, operation=o, events=['OPEN']) for n, o in m.call_order()]
        selected = next(v for v in rows if v['operation'] == 'removed-adopt-1')
        selected['events'] = m.CRITICAL['removed-adopt'].copy(); m.calls(rows, {'removed-adopt-1': ['node-5']})
        selected['events'].remove('PROMISE_FORCED')
        with self.assertRaisesRegex(ValueError, 'force order'): m.calls(rows, {'removed-adopt-1': ['node-5']})
        refused = next(v for v in rows if v['operation'] == 'removed-refusal-1'); refused['events'] = ['PROMISE_FORCED']
        with self.assertRaisesRegex(ValueError, 'removed grant'): m.calls(rows, {'removed-refusal-1': ['node-5']})


if __name__ == '__main__': unittest.main()

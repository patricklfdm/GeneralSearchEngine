import base64
import copy
import hashlib
import struct
import unittest
from . import public_bounds_evidence as e
from .public_bounds_harness import encode_wire


class PublicBoundsEvidenceTest(unittest.TestCase):
    def admission(self):
        before = {'node-1': {'manifest.gsr': dict(size=1, sha256='a')}}
        attempts = [dict(pid=i, case='disk-v11', state='FAILED', outcome='NOT_APPLICABLE', reasonCode='PROTOCOL_MISMATCH') for i in (10, 11)]
        return ['disk-v11', before, [copy.deepcopy(before), copy.deepcopy(before)], attempts]

    def test_admission_requires_the_exact_classified_rejection(self):
        args = self.admission(); self.assertEqual('PASS', e.admission(*args)['status'])
        for change in (dict(outcome='SUCCESS'), dict(state='FOLLOWER'), dict(reasonCode='STORAGE_FAILURE'), dict(case='disk-v10')):
            with self.subTest(change=change):
                changed = copy.deepcopy(args); changed[3][0].update(change)
                with self.assertRaisesRegex(ValueError, 'wrong admission rejection'): e.admission(*changed)

    def test_each_admission_attempt_must_preserve_bytes(self):
        for i in (0, 1):
            args = self.admission(); args[2][i]['node-1']['manifest.gsr']['sha256'] = 'changed'
            with self.assertRaisesRegex(ValueError, 'mutated authority'): e.admission(*args)

    def test_two_distinct_startup_processes_are_required(self):
        args = self.admission(); args[3][1]['pid'] = 10
        with self.assertRaisesRegex(ValueError, 'process identity'): e.admission(*args)
        args = self.admission(); args[3].pop()
        with self.assertRaisesRegex(ValueError, 'two retained'): e.admission(*args)

    def test_disk_probe_changes_only_the_framing_version(self):
        for minor in (0, 1):
            header = struct.pack('>4sHHHHi', b'GSER', 1, minor, 1, 0, 4)
            raw = header+hashlib.sha256(header+b'body').digest()+b'body'
            restored = e.disk_header_fault(raw, minor)
            self.assertEqual(b'body', restored[48:]); self.assertEqual(2, int.from_bytes(restored[6:8], 'big'))
            with self.assertRaisesRegex(ValueError, 'wrong disk version'): e.disk_header_fault(raw, 2)
            bad = bytearray(raw); bad[16] ^= 1
            with self.assertRaisesRegex(ValueError, 'checksum'): e.disk_header_fault(bytes(bad), minor)

    def capacity(self):
        denied = dict(opId='denied', node='node-1', pid=10, kind='addAll', documents=[dict(id=90, value='denied')],
                      outcome='NOT_SUBMITTED', reasonCode='CAPACITY_EXCEEDED', startNanos=2, endNanos=3)
        denied_read = dict(denied, opId='denied-read', kind='read', outcome='NOT_APPLICABLE')
        write = dict(denied, opId='later-write', outcome='SUCCESS', startNanos=5, endNanos=6)
        read = dict(denied_read, opId='later-read', outcome='SUCCESS', startNanos=7, endNanos=8)
        rows = [dict(event='READ_CAPTURED', pid=10, order=1),
                dict(event='CUT_REACHED', pid=10, order=2, cut='READ_CAPTURED'),
                dict(denied, event='CLIENT_FAILURE', order=3), dict(denied_read, event='CLIENT_FAILURE', order=4),
                dict(event='CUT_RELEASED', pid=10, order=5)]
        return [[denied, denied_read, write, read], {'node-1': rows}, 'pending-read', ['denied', 'denied-read']]

    def test_capacity_rejection_is_inside_actual_held_boundary(self):
        args = self.capacity(); self.assertEqual('PASS', e.rejection_history(*args)['status'])
        for removed in ('READ_CAPTURED', 'CUT_REACHED', 'CUT_RELEASED', 'CLIENT_FAILURE'):
            changed = copy.deepcopy(args); changed[1]['node-1'] = [v for v in changed[1]['node-1'] if v['event'] != removed]
            with self.subTest(removed=removed), self.assertRaises(ValueError): e.rejection_history(*changed)

    def test_rejection_after_release_does_not_prove_capacity(self):
        args = self.capacity(); args[1]['node-1'][-1]['order'] = 3
        with self.assertRaisesRegex(ValueError, 'outside held capacity'): e.rejection_history(*args)

    def test_rejection_requires_correct_read_and_write_outcomes(self):
        for index, outcome in ((0, 'INDETERMINATE'), (1, 'NOT_SUBMITTED')):
            args = self.capacity(); args[0][index]['outcome'] = outcome
            with self.assertRaisesRegex(ValueError, 'rejection outcome'): e.rejection_history(*args)

    def test_capacity_must_recover_for_both_reads_and_writes(self):
        for index in (2, 3):
            args = self.capacity(); args[0].pop(index)
            with self.assertRaisesRegex(ValueError, 'never recovered'): e.rejection_history(*args)

    def test_missing_rejection_target_cannot_reduce_the_matrix(self):
        args = self.capacity(); args[3].pop()
        with self.assertRaisesRegex(ValueError, 'missing rejection targets'): e.rejection_history(*args)

    def wire(self):
        manifest = dict(groupId='11111111-1111-1111-1111-111111111111', configurationId='fixture', digest='a'*64,
                        members=[dict(node='node-'+str(i)) for i in (1, 2, 3)])
        request = dict(protocol='gse-replication/1.2', groupId=manifest['groupId'], configurationId='fixture', manifestDigest='a'*64,
                       epoch=1, proposer=None, incarnationId='00000000-0000-0000-0000-000000000000', sender='node-2', recipient='node-1',
                       type='HANDSHAKE', traceId='22222222-2222-2222-2222-222222222222', eventSequence=1, payload=dict(mode='AUTOMATIC'))
        def b64(value): return base64.b64encode(value).decode()
        good = b64(encode_wire(request)); response = b64(encode_wire(dict(request, sender='node-1', recipient='node-2')))
        probes = []
        for name in ('wire-v10', 'wire-v11', 'wire-mode', 'wire-protocol', 'wire-group', 'wire-manifest', 'wire-oversize'):
            changed = copy.deepcopy(request); minor = 2
            if name in ('wire-v10', 'wire-v11'): minor = 0 if name == 'wire-v10' else 1
            elif name == 'wire-mode': changed['payload']['mode'] = 'CONFIGURED'
            elif name == 'wire-protocol': changed['protocol'] = 'gse-replication/1.1'
            elif name == 'wire-group': changed['groupId'] = '33333333-3333-3333-3333-333333333333'
            elif name == 'wire-manifest': changed['manifestDigest'] = 'b'*64
            frame = encode_wire(changed, minor)
            if name == 'wire-oversize':
                frame = struct.pack('>4sHHHHi', b'GSRP', 1, 2, 1, 0, 1<<20)+bytes(32)
            probes.append(dict(case=name, request=b64(frame), response='', terminal='EOF', before={'ledger': 'hash'}, after={'ledger': 'hash'},
                               controlRequest=good, initialResponse=response, controlResponse=response, maxFrameBytes=1<<20))
        return [manifest, probes]

    def test_wire_requires_all_invalid_frames_and_live_controls(self):
        args = self.wire(); self.assertEqual(7, e.wire(*args)['rejectedFrames'])
        args[1].pop()
        with self.assertRaisesRegex(ValueError, 'incomplete'): e.wire(*args)

    def test_wire_timeout_is_not_a_rejection(self):
        args = self.wire(); args[1][0]['terminal'] = 'TIMEOUT'
        with self.assertRaisesRegex(ValueError, 'timed out'): e.wire(*args)

    def test_wire_control_must_be_a_correlated_reply(self):
        args = self.wire(); args[1][0]['controlResponse'] = args[1][0]['controlRequest']
        with self.assertRaisesRegex(ValueError, 'uncorrelated'): e.wire(*args)

    def test_wire_changes_must_preserve_checksum_and_isolate_the_fault(self):
        args = self.wire(); raw = bytearray(base64.b64decode(args[1][2]['request'])); raw[16] ^= 1
        args[1][2]['request'] = base64.b64encode(raw).decode()
        with self.assertRaisesRegex(ValueError, 'checksum'): e.wire(*args)
        args = self.wire(); args[1][2]['request'] = args[1][2]['controlRequest']
        with self.assertRaisesRegex(ValueError, 'isolate'): e.wire(*args)

    def test_oversized_wire_header_cannot_also_have_a_wrong_version(self):
        args = self.wire(); raw = bytearray(base64.b64decode(args[1][-1]['request'])); raw[7] = 1
        args[1][-1]['request'] = base64.b64encode(raw).decode()
        with self.assertRaisesRegex(ValueError, 'oversized declaration'): e.wire(*args)
